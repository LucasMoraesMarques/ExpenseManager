from rest_framework import viewsets, status, views
from rest_framework.response import Response
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, User, Notification, \
    Validation, Membership, ActionLog
from core.serializers import ExpenseSerializerReader, ExpenseSerializerWriter, RegardingSerializerWriter, RegardingSerializerReader, WalletSerializer, PaymentMethodSerializer, \
    PaymentSerializerWriter, PaymentSerializerReader, ExpenseGroupSerializerWriter, ExpenseGroupSerializerReader, TagSerializer, ItemSerializerReader, ItemSerializerWriter, UserSerializer, \
    NotificationSerializer, ValidationSerializerWriter, ValidationSerializerReader, ActionLogSerializer
from core.services import stats

class ExpenseGroupViewSet(viewsets.ModelViewSet):
    queryset = ExpenseGroup.objects.all()
    serializer_class = ExpenseGroupSerializerReader

    def get_queryset(self):
        #self.queryset = self.queryset.filter(user=self.request.user)
        self.queryset = self.queryset.prefetch_related("regardings", "regardings__expenses")
        return self.queryset

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ExpenseGroupSerializerWriter
        else:
            return ExpenseGroupSerializerReader

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            group = ExpenseGroup.objects.filter(name=request.data['name']).last()
            ActionLog.objects.create(user_id=1, expense_group_id=group.id,
                                     type=ActionLog.ActionTypes.CREATE,
                                     description=f"Criou o grupo {group.name}")
        return response

    def update(self, request, *args, **kwargs):
        obj = ExpenseGroup.objects.get(pk=kwargs['pk'])
        response = super().update(request, *args, **kwargs)
        if response.status_code == 200:
            changes = {}
            print(request.data)
            for field in request.data.keys():
                if field in ['name', 'description']:
                    readable_name = 'nome' if field == 'name' else 'descrição'
                    if (old := getattr(obj, field)) != (new := request.data.get(field)):
                        print(old, new)
                        changes[field] = f"Mudou o {readable_name} de '{old}' para '{new}'"
                elif field == 'members':
                    old_members = set(obj.members.values_list("id", flat=True))
                    new_members = set(request.data.get(field))
                    if old_members != new_members:
                        changes["members"] = ''
                        removed_members = old_members.difference(new_members)
                        new_members = new_members.difference(old_members)
                        removed_members = User.objects.filter(id__in=removed_members)
                        new_members = User.objects.filter(id__in=new_members)
                        removed_members_data = UserSerializer(removed_members, many=True).data
                        new_members_data = UserSerializer(new_members, many=True).data

                        if removed_members:
                            changes['members'] = "Removeu o(s) membro(s) "
                            for member in removed_members_data:
                                changes['members'] += member['full_name'] + ', '
                            changes['members'] = changes['members'][:-2] + '.'
                        if new_members:
                            changes['members'] = "Adicionou o(s) membro(s) "
                            for member in new_members_data:
                                changes['members'] += member['full_name'] + ', '
                            changes['members'] = changes['members'][:-2] + '.'


            print(changes)
            ActionLog.objects.create(user_id=1, expense_group_id=obj.id,
                                     type=ActionLog.ActionTypes.UPDATE,
                                     description=f"Atualizou o grupo {obj.name}",
                                     changes_json=changes)
        return response



class RegardingViewSet(viewsets.ModelViewSet):
    queryset = Regarding.objects.all()
    serializer_class = RegardingSerializerWriter

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return RegardingSerializerWriter
        else:
            return RegardingSerializerReader

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == 201:
            ActionLog.objects.create(user_id=1, expense_group_id=request.data['expense_group'],
                                     type=ActionLog.ActionTypes.CREATE,
                                     description=f"Criou a referência {request.data['name']}")
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        if response.status_code == 200:
            obj = Regarding.objects.get(pk=kwargs['pk'])
            ActionLog.objects.create(user_id=1, expense_group_id=obj.expense_group.id,
                                     type=ActionLog.ActionTypes.UPDATE,
                                     description=f"Atualizou a referência {obj.name}")
        return response
class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer


class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializerReader


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by("date")
    serializer_class = ExpenseSerializerReader
    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ExpenseSerializerWriter
        else:
            return ExpenseSerializerReader
    def destroy(self, request, *args, **kwargs):
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
                ActionLog.objects.create(user_id=1, expense_group_id=group.id, type=ActionLog.ActionTypes.DELETE, description=log_description)
            instances.delete()
            print(request.query_params.get('ids'))
            return Response(status=status.HTTP_204_NO_CONTENT)
        expense = Expense.objects.get(pk=kwargs['pk'])
        response = super().destroy(request, *args, **kwargs)
        if response.status_code == 204:
            ActionLog.objects.create(user_id=1, expense_group_id=expense.regarding.expense_group.id,
                                     type=ActionLog.ActionTypes.DELETE,
                                     description=f"Deletou a despesa {expense.name}")
        return response

    def create(self, request, *args, **kwargs):
        print(request.data)
        expense_data = {**request.data, "created_by_id": 1}
        expense_data["cost"] = expense_data["cost"].replace(".", "").replace(",", ".")
        expense_data['created_by'] = 1
        expense_serializer = self.get_serializer(data=expense_data)
        expense_serializer.is_valid(raise_exception=True)
        self.perform_create(expense_serializer)
        regarding = Regarding.objects.get(id=expense_data['regarding'])
        ActionLog.objects.create(user_id=1, expense_group_id=regarding.expense_group.id, type=ActionLog.ActionTypes.CREATE,
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
        headers = self.get_success_headers(expense_serializer.data)
        return Response(expense_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, pk=None, *args, **kwargs):
        print(request.data)
        expense = Expense.objects.get(id=pk)
        expense_data = {**request.data}
        expense_data["cost"] = expense_data["cost"].replace(".", "").replace(",", ".")
        expense_serializer = self.get_serializer(expense, data=expense_data, partial=True)
        expense_serializer.is_valid(raise_exception=True)
        expense_serializer.save()

        ActionLog.objects.create(user_id=1, expense_group_id=expense.regarding.expense_group.id,
                                 type=ActionLog.ActionTypes.UPDATE,
                                 description=f"Atualizou a despesa {expense_data['name']}")
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
        Item.objects.filter(expense=expense.id).exclude(id__in=[payment['id'] for payment in items_to_update]).delete()

        item_serializer_create.save()


        for item in items_to_update:
            obj = Item.objects.get(pk=item['id'])
            item_serializer_update = ItemSerializerWriter(obj, data=item, partial=True)
            item_serializer_update.is_valid(raise_exception=True)
            item_serializer_update.save()



        payments_to_create = []
        payments_to_update = []
        for payment in request.data.get("payments"):
            payer = payment["payer"]
            payment = {**payment, "expense": expense.id, "payer": payer['id'], "payment_method": payment["payment_method"]["id"]}
            payment["value"] = payment["value"].replace(".", "").replace(",", ".")
            if "created_at" in payment.keys():
                payments_to_update.append(payment)
            else:
                payments_to_create.append(payment)

        payment_serializer_create = PaymentSerializerWriter(data=payments_to_create, many=True)
        payment_serializer_create.is_valid(raise_exception=True)

        for payment in payments_to_update:
            obj = Payment.objects.get(pk=payment['id'])
            payment_serializer_update = PaymentSerializerWriter(obj, data=payment, partial=True)
            payment_serializer_update.is_valid(raise_exception=True)
            payment_serializer_update.save()
        Payment.objects.filter(expense=expense.id).exclude(id__in=[payment['id'] for payment in payments_to_update]).delete()
        payment_serializer_create.save()

        print("here")
        headers = self.get_success_headers(expense_serializer.data)
        return Response(expense_serializer.data, status=status.HTTP_200_OK, headers=headers)

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializerReader


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class JoinGroup(views.APIView):
    authentication_classes = []
    def get(self, request, hash, format=None):
        try:
            group = ExpenseGroup.objects.get(hash_id=hash)
            user = User.objects.get(id=1)
            if group not in user.expenses_groups.all():
                membership = Membership.objects.create(group=group, user=user)
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


class ValidationViewSet(viewsets.ModelViewSet):
    queryset = Validation.objects.all()
    serializer_class = ValidationSerializerReader

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ValidationSerializerWriter
        else:
            return ValidationSerializerReader


class ActionsLogViewSet(viewsets.ModelViewSet):
    queryset = ActionLog.objects.all()
    serializer_class = ActionLogSerializer

    def get_queryset(self):
        #self.queryset = self.queryset.filter(user=self.request.user)
        self.queryset = self.queryset.order_by("-created_at")
        return self.queryset