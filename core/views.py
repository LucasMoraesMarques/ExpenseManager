import datetime

from rest_framework import viewsets, status, views, permissions
from rest_framework.response import Response
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, User, Notification, \
    Validation, Membership, ActionLog, GroupInvitation
from core.serializers import ExpenseSerializerReader, ExpenseSerializerWriter, RegardingSerializerWriter, RegardingSerializerReader, WalletSerializer, PaymentMethodSerializer, \
    PaymentSerializerWriter, PaymentSerializerReader, ExpenseGroupSerializerWriter, ExpenseGroupSerializerReader, TagSerializer, ItemSerializerReader, ItemSerializerWriter, UserSerializer, \
    NotificationSerializer, ValidationSerializerWriter, ValidationSerializerReader, ActionLogSerializer, GroupInvitationSerializer
from django.contrib.auth import authenticate
from django.db.models import F, Q
from knox.models import AuthToken
from datetime import datetime, timedelta
from django.db import transaction
import json
from core.services import push_notifications, expense_groups
FIELDS_NAMES_PT = {
    'name': 'nome',
    'description': 'descrição',
    'start_date': 'data inicial',
    'end_date': 'data final',
    'is_closed': 'status',
    'date': 'data',
    'cost': 'custo',
    'payments': 'pagamentos',
    'members': 'membros',
    'invitations': 'convites'
}
class ExpenseGroupViewSet(viewsets.ModelViewSet):
    queryset = ExpenseGroup.objects.all()
    serializer_class = ExpenseGroupSerializerReader
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.request.user.expenses_groups.all()
        self.queryset = self.queryset.prefetch_related("regardings", "regardings__expenses", "members", "memberships", "memberships__user", "invitations", "invitations__sent_by", "invitations__invited")
        return self.queryset

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ExpenseGroupSerializerWriter
        else:
            return ExpenseGroupSerializerReader

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            group = ExpenseGroup.objects.filter(name=request.data['name']).last()
            Membership.objects.create(group=group, user=request.user, level=Membership.Levels.ADMIN)

            notification = Notification.objects.create(
                title=f"Novo grupo criado",
                body=f"O grupo {group.name} foi criado com sucesso!",
                user=request.user,
            )
            push_notifications.send_notification(notification)
            changes = {}
            invitations = request.data.get("invitations", [])
            field_name_pt = FIELDS_NAMES_PT["invitations"]
            changes[field_name_pt] = ''
            for invitation in invitations:
                group_invitation = GroupInvitation.objects.create(sent_by_id=invitation['sent_by']['id'],
                                                                  invited_id=invitation['invited']['id'],
                                                                  expense_group_id=group.id)
                group_invitation.save()
                changes[field_name_pt] += f"\nConvidou o usuário {invitation['invited']['full_name']}"
                notification = Notification.objects.create(
                    title=f"Convite para o grupo {group.name}",
                    body=f"{invitation['sent_by']['full_name']} te convidou para entrar no grupo {group.name}",
                    user_id=invitation['invited']['id'],
                )
                push_notifications.send_notification(notification)
            ActionLog.objects.create(user=request.user, expense_group_id=group.id,
                                     type=ActionLog.ActionTypes.CREATE,
                                     description=f"Criou o grupo {group.name}", changes_json=changes)
        return response

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        obj = ExpenseGroup.objects.get(pk=kwargs['pk'])
        response = super().update(request, *args, **kwargs)
        print(request.data)
        if response.status_code == 200:
            changes = {}
            for field in request.data.keys():
                field_name_pt = FIELDS_NAMES_PT.get(field, field)
                if field in ['name', 'description']:
                    if (old := getattr(obj, field)) != (new := request.data.get(field)):
                        changes[field_name_pt] = f"Mudou o(a) {FIELDS_NAMES_PT[field]} de '{old}' para '{new}'"
                elif field == 'members':
                    old_members = set(obj.members.values_list("id", flat=True))
                    new_members = set(request.data.get(field))
                    if old_members != new_members:
                        changes[field_name_pt] = ''
                        removed_members = old_members.difference(new_members)
                        new_members = new_members.difference(old_members)
                        removed_members = User.objects.filter(id__in=removed_members)
                        new_members = User.objects.filter(id__in=new_members)
                        removed_members_data = UserSerializer(removed_members, many=True).data
                        new_members_data = UserSerializer(new_members, many=True).data
                        obj.refresh_from_db()
                        user_editor_full_name = f"{request.user.first_name + ' ' + request.user.last_name}".strip()
                        for member in removed_members:
                            notification = Notification.objects.create(
                                title=f"Você foi removido(a) do grupo {obj.name}",
                                body=f"O membro {user_editor_full_name} removeu você do grupo. Se acha que isso foi um engano, contate-o.",
                                user=member,
                            )
                            push_notifications.send_notification(notification)
                            obj.memberships.filter(user=member).delete()
                        for member in new_members:
                            Membership.objects.create(group=obj, user=member)
                        if removed_members:
                            changes[field_name_pt] = "\nRemoveu o(s) membro(s) "
                            for member in removed_members_data:
                                changes[field_name_pt] += member['full_name'] + ', '
                            changes[field_name_pt] = changes[field_name_pt][:-2] + '.'
                        if new_members:
                            changes[field_name_pt] = "\nAdicionou o(s) membro(s) "
                            for member in new_members_data:
                                changes[field_name_pt] += member['full_name'] + ', '
                            changes[field_name_pt] = changes[field_name_pt][:-2] + '.'
                elif field == "memberships":
                    memberships = request.data.get("memberships", [])
                    changes["membros"] = ''
                    for membership_data in memberships:
                        if membership_data.get('updated', False):
                            membership = obj.memberships.get(id=membership_data.get('id'))
                            user_full_name = f"{membership.user.first_name} {membership.user.last_name}".strip()
                            new_level_index = Membership.Levels.labels.index(membership_data['level'].upper())
                            old_level_index = Membership.Levels.values.index(membership.level)
                            new_level = Membership.Levels.values[new_level_index]
                            old_level = Membership.Levels.labels[old_level_index]
                            changes["membros"] += f"\nMudou o membro {user_full_name} de {old_level} para {membership_data['level'].upper()}"
                            membership.level = new_level
                            membership.save(update_fields=['level'])
                elif field == "invitations":
                    invitations = request.data.get("invitations", [])
                    changes[field_name_pt] = ''
                    for invitation in invitations:
                        if invitation.get('create', False):
                            group_invitation = GroupInvitation.objects.create(sent_by_id=invitation['sent_by']['id'],
                                                           invited_id=invitation['invited']['id'],
                                                           expense_group_id=invitation['expense_group'])
                            group_invitation.save()
                            changes[field_name_pt] += f"\nConvidou o usuário {invitation['invited']['full_name']}"
                            notification = Notification.objects.create(
                                title=f"Convite para o grupo {invitation['group_name']}",
                                body=f"{invitation['sent_by']['full_name']} te convidou para entrar no grupo {invitation['group_name']}",
                                user_id=invitation['invited']['id'],
                            )
                            push_notifications.send_notification(notification)
            ActionLog.objects.create(user=request.user, expense_group_id=obj.id,
                                     type=ActionLog.ActionTypes.UPDATE,
                                     description=f"Atualizou o grupo {obj.name}",
                                     changes_json=changes)
        return response

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        group = ExpenseGroup.objects.get(pk=kwargs['pk'])
        members = expense_groups.get_members(group, request, exclude_current_user=True)
        notification_data = {"title": "Grupo deletado",
                             "body": f"O membro {current_user_full_name} excluiu o grupo {group.name} e você foi removido."}
        expense_groups.notify_members(members, notification_data)
        response = super().destroy(request, *args, **kwargs)
        return response



class RegardingViewSet(viewsets.ModelViewSet):
    queryset = Regarding.objects.all()
    serializer_class = RegardingSerializerWriter
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.select_related("expense_group").prefetch_related("expenses", "expenses__validations", "expenses__validations__validator")
        return self.queryset.filter(expense_group__in=self.request.user.expenses_groups.all())


    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return RegardingSerializerWriter
        else:
            return RegardingSerializerReader

    def create(self, request, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            ActionLog.objects.create(user=request.user, expense_group_id=request.data['expense_group'],
                                     type=ActionLog.ActionTypes.CREATE,
                                     description=f"Criou a referência {request.data['name']}")
            expense_group = ExpenseGroup.objects.get(id=request.data['expense_group'])
            notification_data = {"title": "Referência adicionada",
                                 "body": f"O membro {current_user_full_name} adicionou a referência {request.data['name']}"}
            members = expense_groups.get_members(expense_group, request, exclude_current_user=True)
            expense_groups.notify_members(members, notification_data)
        return response

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        obj = Regarding.objects.get(pk=kwargs['pk'])
        response = super().update(request, *args, **kwargs)
        if response.status_code == 200:
            changes = {}
            for field in request.data.keys():
                field_name_pt = FIELDS_NAMES_PT.get(field, field)
                if field in ['name', 'description']:
                    if (old := getattr(obj, field)) != (new := request.data.get(field)):
                        changes[field_name_pt] = f"Mudou a(o) {FIELDS_NAMES_PT[field]} de '{old}' para '{new}'"
                elif field in ['start_date', 'end_date']:
                    if (old := str(getattr(obj, field))) != (new := request.data.get(field)):
                        changes[field_name_pt] = f"Mudou a(o) {FIELDS_NAMES_PT[field]} de '{old[8:10]}/{old[5:7]}/{old[:4]}' para '{new[8:10]}/{new[5:7]}/{new[:4]}'"
                elif field == 'is_closed':
                    if (old := getattr(obj, field)) != (new := request.data.get(field)):
                        old = 'finalizada' if old else 'em andamento'
                        new = 'finalizada' if new else 'em andamento'
                        changes[field_name_pt] = f"Mudou a(o) {FIELDS_NAMES_PT[field]} de '{old}' para '{new}'"

            ActionLog.objects.create(user=request.user, expense_group_id=obj.expense_group.id,
                                     type=ActionLog.ActionTypes.UPDATE,
                                     description=f"Atualizou a referência {obj.name}",
                                     changes_json=changes)
            notification_data = {"title": "Referência atualizada",
                                 "body": f"O membro {current_user_full_name} atualizou a referência {obj.name}"}
            members = expense_groups.get_members(obj.expense_group, request, exclude_current_user=True)
            expense_groups.notify_members(members, notification_data)
        if request.data.get("is_closed", False):
            regarding_serializer = RegardingSerializerReader(obj, context={"request": request})
            totals = regarding_serializer.data
            obj.balance_json = json.dumps({
                "general_total": totals.get('general_total', {}),
                "consumer_total": totals.get('consumer_total', []),
                "total_by_day": totals.get('total_by_day', {}),
                "total_member_vs_member": totals.get('total_member_vs_member', {}),
            }, default=str)
            obj.save(update_fields=["balance_json"])
        return response

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        regarding = Regarding.objects.get(pk=kwargs['pk'])
        response = super().destroy(request, *args, **kwargs)
        if response.status_code == 204:
            ActionLog.objects.create(user=request.user, expense_group_id=regarding.expense_group.id,
                                     type=ActionLog.ActionTypes.DELETE,
                                     description=f"Deletou a referência {regarding.name}")
            notification_data = {"title": "Refrência deletada",
                                 "body": f"O membro {current_user_full_name} deletou a referência {regarding.name}. Todas as despesas, items e pagamentos também foram excluídos."}
            members = expense_groups.get_members(regarding.expense_group, request, exclude_current_user=True)
            expense_groups.notify_members(members, notification_data)
        return response

class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(owner=self.request.user).prefetch_related("payment_methods", "payment_methods__payments")
        return self.queryset



class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(wallet=self.request.user.wallet).prefetch_related("payments")
        return self.queryset



class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related("expense", "expense__regarding__expense_group", "payment_method", "payer").prefetch_related("expense__validations", "expense__validations__validator", "expense__validated_by")
    serializer_class = PaymentSerializerReader
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(expense__regarding__expense_group__in=self.request.user.expenses_groups.all())
        return self.queryset



class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().select_related("regarding", "regarding__expense_group", "created_by").prefetch_related("payments", "payments__payer", "payments__payment_method", "payments__expense", "validations", "validations__validator", "validations__validator__wallet", "validations__validator__wallet__payment_methods", "validations__validator__wallet__payment_methods__payments", "validated_by", "items", "items__consumers", "regarding__expense_group__members")
    serializer_class = ExpenseSerializerReader
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(regarding__expense_group__in=self.request.user.expenses_groups.all())
        return self.queryset.order_by("date")

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ExpenseSerializerWriter
        else:
            return ExpenseSerializerReader

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        if "ids" in request.query_params:
            ids = request.query_params.get('ids').split(',')
            instances = Expense.objects.filter(id__in=ids).select_related("regarding__expense_group")

            delete_by_groups = {}
            for instance in instances:
                if instance.regarding.expense_group not in delete_by_groups.keys():
                    delete_by_groups[instance.regarding.expense_group] = [instance.name]
                else:
                    delete_by_groups[instance.regarding.expense_group].append(instance.name)
            print(delete_by_groups)
            for group, deleted_expenses in delete_by_groups.items():
                log_description = 'Deletou em massas as depesas '
                for expense_name in deleted_expenses:
                    log_description += expense_name + ', '
                ActionLog.objects.create(user=request.user, expense_group_id=group.id, type=ActionLog.ActionTypes.DELETE, description=log_description)
            instances.delete()
            print(request.query_params.get('ids'))
            return Response(status=status.HTTP_204_NO_CONTENT)
        expense = Expense.objects.get(pk=kwargs['pk'])
        response = super().destroy(request, *args, **kwargs)
        if response.status_code == 204:
            ActionLog.objects.create(user=request.user, expense_group_id=expense.regarding.expense_group.id,
                                     type=ActionLog.ActionTypes.DELETE,
                                     description=f"Deletou a despesa {expense.name}")
            notification_data = {"title": "Despesa deletada",
                                 "body": f"O membro {current_user_full_name} deletou a despesa {expense.name} de valor R$ {expense.cost}"}
            members = expense_groups.get_members(expense.regarding.expense_group, request, exclude_current_user=True)
            expense_groups.notify_members(members, notification_data)
        return response

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        print(request.data)
        expense_data = {**request.data, "created_by_id": request.user.id}
        expense_data["cost"] = expense_data["cost"].replace(".", "").replace(",", ".")
        expense_data['created_by'] = request.user.id
        expense_serializer = self.get_serializer(data=expense_data)
        expense_serializer.is_valid(raise_exception=True)
        self.perform_create(expense_serializer)
        regarding = Regarding.objects.get(id=expense_data['regarding'])
        ActionLog.objects.create(user=request.user, expense_group_id=regarding.expense_group.id, type=ActionLog.ActionTypes.CREATE,
                                 description=f"Criou a despesa {expense_data['name']} de valor R$ {expense_data['cost']}")

        expense = Expense.objects.last()
        print(expense)
        items = []
        for item in request.data.get("items"):
            consumers = []
            for consumer in item['consumers']:
                consumers.append(consumer['id'])
            item['consumers'] = consumers
            item['expense'] = expense.id
            item["price"] = item["price"].replace(".", "").replace(",", ".")
            items.append(item)
        item_serializer = ItemSerializerWriter(data=items, many=True)
        item_serializer.is_valid(raise_exception=True)
        payments = []
        for payment in request.data.get("payments"):
            payment = {**payment, "expense": expense.id, "payer": payment["payer"]["id"], "payment_method": payment["payment_method"]["id"]}
            payment["value"] = payment["value"].replace(".", "").replace(",", ".")
            payments.append(payment)
        print("here")
        payment_serializer = PaymentSerializerWriter(data=payments, many=True)
        payment_serializer.is_valid(raise_exception=True)
        item_serializer.save()
        payment_serializer.save()
        for validator in expense_data['validators']:
            Validation.objects.create(validator_id=validator['id'], expense_id=expense.id)
            notification = Notification.objects.create(
                title=f"Validação solicitada",
                body=f"{current_user_full_name} solicitou sua validação na despesa {expense.name}",
                user_id=validator['id'],
            )
            push_notifications.send_notification(notification)
        headers = self.get_success_headers(expense_serializer.data)
        notification_data = {"title": "Despesa adicionada",
                             "body": f"O membro {current_user_full_name} adicionou a despesa {expense.name} de valor R$ {expense.cost}"}
        members = expense_groups.get_members(expense.regarding.expense_group, request, exclude_current_user=True)
        expense_groups.notify_members(members, notification_data)
        return Response(expense_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @transaction.atomic
    def partial_update(self, request, pk=None, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        print(request.data)
        expense = Expense.objects.get(id=pk)
        expense_data = {**request.data}
        expense_data["cost"] = expense_data["cost"].replace(".", "").replace(",", ".")
        expense_serializer = self.get_serializer(expense, data=expense_data, partial=True)
        expense_serializer.is_valid(raise_exception=True)


        print(expense)
        items_to_create = []
        items_to_update = []
        for item in request.data.get("items"):
            consumers = []
            for consumer in item['consumers']:
                consumers.append(consumer['id'])
            item['consumers'] = consumers
            item['expense'] = expense.id
            item["price"] = item["price"].replace(".", "").replace(",", ".")
            if "created_at" in item.keys():
                items_to_update.append(item)
            else:
                items_to_create.append(item)
        item_serializer_create = ItemSerializerWriter(data=items_to_create, many=True)
        item_serializer_create.is_valid(raise_exception=True)
        items_to_delete = Item.objects.filter(expense=expense.id).exclude(id__in=[item['id'] for item in items_to_update])
        items_to_delete_names = list(items_to_delete.values_list("name", flat=True))


        items_serializers_to_save = []
        for item in items_to_update:
            print(item)
            obj = Item.objects.get(pk=item['id'])
            item_serializer_update = ItemSerializerWriter(obj, data=item, partial=True)
            item_serializer_update.is_valid(raise_exception=True)
            items_serializers_to_save.append(item_serializer_update)



        payments_to_create = []
        payments_to_update = []
        for payment in request.data.get("payments"):
            payer = payment["payer"]
            payment = {**payment, "expense": expense.id, "payer": payer['id'], "payment_method": payment["payment_method"]["id"], 'payer_name': payer.get('name', None) or payer.get('full_name', None)}
            payment["value"] = payment["value"].replace(".", "").replace(",", ".")
            if "created_at" in payment.keys():
                payments_to_update.append(payment)
            else:
                payments_to_create.append(payment)

        payment_serializer_create = PaymentSerializerWriter(data=payments_to_create, many=True)
        payment_serializer_create.is_valid(raise_exception=True)

        payments_serializers_to_save = []
        for payment in payments_to_update:
            obj = Payment.objects.get(pk=payment['id'])
            payment_serializer_update = PaymentSerializerWriter(obj, data=payment, partial=True)
            payment_serializer_update.is_valid(raise_exception=True)
            payments_serializers_to_save.append(payment_serializer_update)

        payments_to_delete = Payment.objects.filter(expense=expense.id).exclude(id__in=[payment['id'] for payment in payments_to_update])
        payments_to_delete_data = payments_to_delete.values("payer__first_name", "value")

        expense_serializer.save()
        items_to_delete.delete()
        item_serializer_create.save()
        payments_to_delete.delete()
        payment_serializer_create.save()
        for item_serializer in items_serializers_to_save:
            item_serializer.save()
        for payment_serializer in payments_serializers_to_save:
            payment_serializer.save()

        if request.data.get("revalidate", False):
            expense.validations.update(is_active=True, validated_at=None, note="")
            for validation in expense.validations.all():
                notification = Notification.objects.create(
                    title=f"Validação solicitada novamente",
                    body=f"{current_user_full_name} editou a despesa {expense.name} e solicitou sua validação novamente",
                    user=validation.validator,
                )
                push_notifications.send_notification(notification)

        print("here")
        headers = self.get_success_headers(expense_serializer.data)
        changes = {}
        for field in request.data.keys():
            field_name_pt = FIELDS_NAMES_PT.get(field, field)
            if field in ['name', 'description']:
                if (old := getattr(expense, field)) != (new := request.data.get(field)):
                    changes[field_name_pt] = f"Mudou a(o) {FIELDS_NAMES_PT[field]} de '{old}' para '{new}'"
            elif field == "cost":
                old = getattr(expense, field)
                new = float(request.data.get(field).replace('.', "").replace(",", "."))
                if old != new:
                    changes[field_name_pt] = f"Mudou a(o) {FIELDS_NAMES_PT[field]} de R${old} para R${new}"
            elif field == 'date':
                if (old := str(getattr(expense, field))) != (new := request.data.get(field)):
                    changes[
                        field_name_pt] = f"Mudou a(o) {FIELDS_NAMES_PT[field]} de '{old[8:10]}/{old[5:7]}/{old[:4]}' para '{new[8:10]}/{new[5:7]}/{new[:4]}'"
            elif field == 'items':
                message = '\nDeletou os itens '
                changes[field_name_pt] = ''
                if len(items_to_delete_names):
                    changes[field_name_pt] = message
                    for item in items_to_delete_names:
                        changes[field_name_pt] += f"{item}, "
                    changes[field_name_pt] = changes[field_name_pt][:-2] + '.'
                """message = '\nAtualizou os itens '
                if len(items_to_update):
                    changes[field] += message
                    for item in items_to_update:
                        changes[field] += f"{item['name']}, "
                    changes[field] = changes[field][:-2] + '.'"""
                message = '\nCriou os itens '
                if len(items_to_create):
                    changes[field_name_pt] += message
                    for item in items_to_create:
                        changes[field_name_pt] += f"{item['name']}, "
                    changes[field_name_pt] = changes[field_name_pt][:-2] + '.'
                if not changes[field_name_pt]:
                    del changes[field_name_pt]
            elif field == 'payments':
                message = '\nDeletou os pagamentos '
                changes[field_name_pt] = ''
                if len(payments_to_delete_data):
                    changes[field_name_pt] = message
                    for payment in payments_to_delete_data:
                        changes[field_name_pt] += f"{payment['payer__first_name']} R${payment['value']}, "
                    changes[field_name_pt] = changes[field_name_pt][:-2] + '.'
                """message = '\nAtualizou os pagamentos '
                if len(payments_to_update):
                    changes[field] += message
                    for payment in payments_to_update:
                        changes[field] += f"{payment['payer_name']} - R${payment['value']}, "
                    changes[field] = changes[field][:-2] + '.'"""
                message = '\nCriou os pagamentos '
                if len(payments_to_create):
                    changes[field_name_pt] += message
                    for payment in payments_to_create:
                        changes[field_name_pt] += f"{payment['payer_name']} R${payment['value']}, "
                    changes[field_name_pt] = changes[field_name_pt][:-2] + '.'
                if not changes[field_name_pt]:
                    del changes[field_name_pt]
        ActionLog.objects.create(user=request.user, expense_group_id=expense.regarding.expense_group.id,
                                 type=ActionLog.ActionTypes.UPDATE,
                                 description=f"Atualizou a despesa {expense_data['name']}", changes_json=changes)
        notification_data = {"title": "Despesa editada",
                             "body": f"O membro {current_user_full_name} editou a despesa {expense.name} de valor R$ {expense.cost}"}
        members = expense_groups.get_members(expense.regarding.expense_group, request, exclude_current_user=True)
        expense_groups.notify_members(members, notification_data)

        return Response(expense_serializer.data, status=status.HTTP_200_OK, headers=headers)



class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.request.user.created_tags.all()
        return self.queryset



class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all().select_related("expense", "expense__regarding", "expense__regarding__expense_group").prefetch_related("expense__validated_by", "expense__payments", "expense__payments__payment_method", "expense__payments__payer",  "consumers")
    serializer_class = ItemSerializerReader
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(expense__regarding__expense_group__in=self.request.user.expenses_groups.all())
        return self.queryset



class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().select_related("wallet").prefetch_related("wallet__payment_methods", "wallet__payment_methods__payments", "expenses_groups")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        users_data = serializer.data
        for user in users_data:
            invitations = GroupInvitation.objects.select_related("invited", "sent_by", "expense_group").filter(invited_id=user['id'], status=GroupInvitation.InvitationStatus.AWAITING)
            user['invitations_received'] = GroupInvitationSerializer(invitations, many=True).data
        return Response(serializer.data)



class JoinGroup(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    @transaction.atomic
    def get(self, request, hash, format=None):
        try:
            group = ExpenseGroup.objects.get(hash_id=hash)
            user = request.user
            new_user_full_name = f"{user.first_name} {user.last_name}".strip()
            if group not in user.expenses_groups.all():
                for membership in group.memberships.all():
                    notification = Notification.objects.create(
                        title=f"Novo membro no grupo {group.name}",
                        body=f"O usuário {new_user_full_name} entrou no grupo",
                        user=membership.user,
                    )
                    push_notifications.send_notification(notification)
                Membership.objects.create(group=group, user=user)
                notification = Notification.objects.create(
                    title=f"Bem vindo ao grupo {group.name}",
                    body=f"Agora você já pode ver e criar despesas nesse grupo.",
                    user=user,
                )
                push_notifications.send_notification(notification)

            else:
                return Response(status=status.HTTP_400_BAD_REQUEST, data={"detail": "Você já faz parte desse grupo"})
        except ExpenseGroup.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND, data={"detail": "Grupo não encontrado"})
        except Exception as ex:
            print(ex)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR, data={"detail": "Tivemos problemas ao adicioná-lo ao grupo. Tente novamente!"})
        else:
            return Response(status=status.HTTP_200_OK, data={"detail": "Você entrou no grupo!"})



class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.request.user.notifications.all()
        return self.queryset.order_by("-created_at")



class ValidationViewSet(viewsets.ModelViewSet):
    queryset = Validation.objects.all().select_related("expense", "expense__regarding","expense__regarding__expense_group", "validator", "validator__wallet").prefetch_related("expense__validated_by", "expense__created_by", "validator__wallet__payment_methods", "validator__wallet__payment_methods__payments")
    serializer_class = ValidationSerializerReader
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(validator=self.request.user)
        return self.queryset


    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ValidationSerializerWriter
        else:
            return ValidationSerializerReader

    @transaction.atomic
    def partial_update(self, request, pk=None, *args, **kwargs):
        current_user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        print(request.data, pk)
        response = super().update(request, *args, **kwargs)
        obj = Validation.objects.get(pk=pk)
        expense_validations = Validation.objects.filter(expense=obj.expense)
        expense_creator = obj.expense.created_by
        if obj.validated_at:
            notification = Notification.objects.create(
                title=f"{current_user_full_name} validou uma despesa",
                body=f"Está tudo certo com a despesa {obj.expense.name}",
                user=expense_creator,
            )
        else:
            notification = Notification.objects.create(
                title=f"{current_user_full_name} rejeitou uma despesa",
                body=f"A despesa {obj.expense.name} foi rejeitada." + f"O motivo da rejeição foi {obj.note}" if obj.note else "",
                user=expense_creator,
            )
        push_notifications.send_notification(notification)
        validated = expense_validations.filter(validated_at__isnull=False)
        rejected = expense_validations.filter(validated_at__isnull=True, is_active=False)
        if expense_validations.count() == validated.count():
            obj.expense.validation_status = Expense.ValidationStatuses.VALIDATED
        elif expense_validations.count() == rejected.count():
            obj.expense.validation_status = Expense.ValidationStatuses.REJECTED
        else:
            obj.expense.validation_status = Expense.ValidationStatuses.AWAITING
        obj.expense.save(update_fields=['validation_status'])
        if obj.expense.validation_status == Expense.ValidationStatuses.VALIDATED:
            notification = Notification.objects.create(
                title=f"Despesa validada",
                body=f"Todos as validações solicitadas para a despesa {obj.expense.name} foram aprovadas",
                user=expense_creator,
            )
            push_notifications.send_notification(notification)

        return response


class ActionsLogViewSet(viewsets.ModelViewSet):
    queryset = ActionLog.objects.all().select_related("expense_group", "user", "user__wallet").prefetch_related("user__wallet__payment_methods", "user__wallet__payment_methods__payments")
    serializer_class = ActionLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.filter(expense_group__in=self.request.user.expenses_groups.all())
        return self.queryset.order_by("-created_at")


class GroupInvitationViewSet(viewsets.ModelViewSet):
    queryset = GroupInvitation.objects.all().select_related("sent_by", "invited", "expense_group")
    serializer_class = GroupInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        self.queryset = self.queryset.filter((Q(sent_by_id=user.id) | Q(invited_id=user.id)) & Q(status=GroupInvitation.InvitationStatus.AWAITING))
        return self.queryset.order_by("-created_at")

    @transaction.atomic
    def partial_update(self, request, pk=None, *args, **kwargs):
        print(request.data, pk)
        obj = GroupInvitation.objects.get(pk=pk)
        obj.status = request.data.get("status", obj.status)
        obj.save(update_fields=['status'])
        invited = f"{obj.invited.first_name + ' ' + obj.invited.last_name}".strip()
        sent_by = f"{obj.sent_by.first_name + ' ' + obj.sent_by.last_name}".strip()
        if obj.status == GroupInvitation.InvitationStatus.ACCEPTED:
            ActionLog.objects.create(user=request.user, expense_group=obj.expense_group,
                                     type=ActionLog.ActionTypes.UPDATE,
                                     description=f"{invited} aceitou o convite de {sent_by}", changes_json={})
            notification = Notification.objects.create(
                title="Convite aceito",
                body=f"{invited} aceitou o seu convite para se juntar ao grupo {obj.expense_group.name}",
                user=obj.sent_by,
            )
            push_notifications.send_notification(notification)
            for membership in obj.expense_group.memberships.all():
                notification = Notification.objects.create(
                    title=f"Novo membro no grupo {obj.expense_group.name}",
                    body=f"O usuário {invited} entrou no grupo",
                    user=membership.user,
                )
                push_notifications.send_notification(notification)
            Membership.objects.create(group=obj.expense_group, user=request.user)

        else:
            notification = Notification.objects.create(
                title="Convite rejeitado",
                body=f"{invited} rejeitou o seu convite para se juntar ao grupo {obj.expense_group.name}",
                user=obj.sent_by,
            )
            push_notifications.send_notification(notification)
        return Response(data=GroupInvitationSerializer(obj).data, status=status.HTTP_200_OK)


class Login(views.APIView):
    authentication_classes = []

    @transaction.atomic
    def post(self, request, format=None):
        data = request.data

        email = data.get('email', None)
        password = data.get('password', None)
        google_account_id = data.get('accountId', None)
        print(data)
        if google_account_id:
            try:
                user = User.objects.get(Q(google_id=google_account_id) | Q(email=email))
                if user.email == email and user.google_id != google_account_id:
                    return Response(
                        data={'detail': "Conta com esse email não foi cadastrada pelo Google. Tente entrar com sua senha!"},
                        status=status.HTTP_404_NOT_FOUND)
            except User.DoesNotExist:
                return Response(data={'detail': "Conta com esse email não existe. Tente registrar-se com o google "
                                                    "antes de fazer login."},
                                    status=status.HTTP_404_NOT_FOUND)
            else:
                pass
        else:
            user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.is_active:
                # login(request, user)
                serializer = UserSerializer(user)
                instance, token = AuthToken.objects.create(user)
                instance.expiry = datetime.now() + timedelta(days=+30)
                instance.save()

                return Response(data={'user': serializer.data, 'api_token': token, 'fcm_token': user.fcm_token}, status=status.HTTP_200_OK)
            else:
                return Response(data={'detail': 'Usuário não confirmou ou desativou a conta.'}, status=status.HTTP_400_BAD_REQUEST)
        elif user:=User.objects.filter(email=email).first():
            if user.google_id:
                return Response(data={'detail': "Email cadastrado pelo google. Tente entrar com o google!"}, status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response(data={'detail': "Email e/ou senha inválidos. Tente novamente!"}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response(data={'detail': "Conta com esse email não existe"}, status=status.HTTP_404_NOT_FOUND)


class Register(views.APIView):
    authentication_classes = []
    @transaction.atomic
    def post(self, request, format=None):
        data = request.data
        user_data = {
            "first_name": data.get('firstName', None),
            "last_name": data.get('lastName', None),
            "email": data.get('email', None),
            "password": data.get('password', None),
            "username": data.get('email', None),
            "google_id": data.get('googleId', None)
        }
        print(user_data)
        if user:=User.objects.filter(email=user_data['email']).first():
            if user.google_id:
                return Response(data={
                    'detail': "Já existe uma conta com esse email cadastrada pelo google. Tente cadastrar outro ou faça login com o google."},
                    status=status.HTTP_401_UNAUTHORIZED)
            return Response(data={
                'detail': "Já existe uma conta com esse email. Tente cadastrar outro ou faça login com o email fornecido!"},
                status=status.HTTP_401_UNAUTHORIZED)
        else:
            try:
                user = User.objects.create_user(**user_data)
            except Exception as e:
                print(e)
                return Response(data={
                    'detail': "Erro inesperado ao salvar o cadastro. Tente novamente!"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                serializer = UserSerializer(user)
                instance, token = AuthToken.objects.create(user)
                instance.expiry = datetime.now() + timedelta(days=+30)
                instance.save()
                Wallet.objects.create(owner=user)
                notification = Notification.objects.create(
                    title="Bem vindo(a) ao App",
                    body=f"Confira o tour pelo aplicativo para conhecer nossas funcionalidades",
                    user=user,
                )
                push_notifications.send_notification(notification)

                return Response(data={'user': serializer.data, 'api_token': token, 'fcm_token': user.fcm_token},
                                status=status.HTTP_200_OK)

