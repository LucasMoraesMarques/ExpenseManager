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
from core.services import push_notifications, expense_groups, action_logs, regardings, validations, expenses

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
        self.queryset = self.queryset.prefetch_related("regardings", "regardings__expenses", "members", "memberships",
                                                       "memberships__user", "invitations", "invitations__sent_by",
                                                       "invitations__invited")
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
        if response.status_code == status.HTTP_201_CREATED:
            group = ExpenseGroup.objects.filter(name=request.data.get("name", "")).last()
            new_membership = Membership.objects.create(group=group, user=request.user, level=Membership.Levels.ADMIN)
            expense_groups.notify_group_was_created(new_membership)
            invitations = expense_groups.create_invitations(request, group)
            expense_groups.notify_users_invited(invitations)
            action_logs.new_group(request, group)
        return response

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        group = ExpenseGroup.objects.get(pk=kwargs['pk'])
        response = super().update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            removed_members = expense_groups.remove_members(request, group)
            invitations = expense_groups.create_invitations(request, group)
            expense_groups.notify_users_removed(removed_members, group, request.user)
            expense_groups.notify_users_invited(invitations)
            action_logs.update_group(request, group, removed_members, invitations)
            expense_groups.update_memberships(request, group)
        return response

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        group = ExpenseGroup.objects.get(pk=kwargs['pk'])
        members = expense_groups.get_members(group, request, exclude_current_user=True)
        notification_data = {"title": "Grupo deletado",
                             "body": f"O membro {request.user.full_name} excluiu o grupo {group.name} e você foi removido."}
        expense_groups.notify_members(members, notification_data)
        response = super().destroy(request, *args, **kwargs)
        return response


class RegardingViewSet(viewsets.ModelViewSet):
    queryset = Regarding.objects.all()
    serializer_class = RegardingSerializerWriter
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        self.queryset = self.queryset.select_related("expense_group").prefetch_related("expenses", "expenses__validations", "expenses__validations__validator")
        return self.queryset.filter(expense_group__in=self.request.user.expenses_groups.all()).order_by('-start_date', '-end_date')

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return RegardingSerializerWriter
        else:
            return RegardingSerializerReader

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            group = ExpenseGroup.objects.get(id=request.data['expense_group'])
            regardings.notify_members_about_new_regarding(request, group)
            action_logs.new_regarding(request)
        return response

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        regarding = Regarding.objects.get(pk=kwargs['pk'])
        response = super().update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            action_logs.update_regarding(request, regarding)
            regardings.notify_members_about_regarding_update(request, regarding)
            regardings.update_balance_json(request, regarding)
        return response

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        regarding = Regarding.objects.get(pk=kwargs['pk'])
        response = super().destroy(request, *args, **kwargs)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            regardings.notify_members_about_regarding_deletion(request, regarding)
            action_logs.regarding_deletion(request, regarding)
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
        return self.queryset.order_by("-date")

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ExpenseSerializerWriter
        else:
            return ExpenseSerializerReader

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        if "ids" in request.query_params:
            delete_by_groups = expenses.batch_delete_expense(request.query_params.get('ids').split(','))
            action_logs.batch_delete_expense(request, delete_by_groups)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            expense = Expense.objects.get(pk=kwargs['pk'])
            response = super().destroy(request, *args, **kwargs)
            if response.status_code == status.HTTP_204_NO_CONTENT:
                expenses.notify_members_about_expense_deletion(request, expense)
                action_logs.delete_expense(request, expense)
            return response

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            expense = request.user.created_expenses.last()
            expenses.create_items_for_new_expense(request.data.get("items"), expense)
            expenses.create_payments_for_new_expense(request.data.get("payments"), expense)
            expenses.notify_expense_validators(request, expense)
            expenses.notify_members_about_new_expense(request,expense)
            action_logs.new_expense(request, expense)
        return response

    @transaction.atomic
    def partial_update(self, request, pk=None, *args, **kwargs):
        expense = Expense.objects.get(id=pk)
        response = super().partial_update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            deleted_items = expenses.handle_items_edition(request.data.get("items"), expense)
            deleted_payments = expenses.handle_payments_edition(request.data.get("payments"), expense)
            if request.data.get("revalidate", False):
                expenses.ask_validators_to_revalidate(request, expense)
            expenses.notify_members_about_expense_update(request, expense)
            action_logs.update_expense(request, expense, deleted_items, deleted_payments)
        return response


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
            if group not in request.user.expenses_groups.all():
                expense_groups.join_group_by_code(request, group)
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
        return self.queryset.order_by("-created_at")

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return ValidationSerializerWriter
        else:
            return ValidationSerializerReader

    @transaction.atomic
    def partial_update(self, request, pk=None, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            validation = Validation.objects.get(pk=pk)
            if request.data.get("revalidate", False):
                validations.ask_for_revalidation(request, validation)
            else:
                validations.notify_creator_about_validation_change(request, validation)
            validations.update_validation_status_and_notify_creator(validation.expense)
            action_logs.update_validation(request, validation)
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
        response = super().update(request, *args, **kwargs)
        invitation = GroupInvitation.objects.get(pk=pk)
        if response.status_code == status.HTTP_200_OK:
            expense_groups.handle_invitation_answer(request, invitation)
            action_logs.update_invitation(request, invitation)
        return Response(data=GroupInvitationSerializer(invitation).data, status=status.HTTP_200_OK)


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

