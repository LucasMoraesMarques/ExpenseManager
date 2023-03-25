from rest_framework import viewsets, response, status, views
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, User, Notification, Validation
from core.serializers import ExpenseSerializerReader, ExpenseSerializerWriter, RegardingSerializerWriter, RegardingSerializerReader, WalletSerializer, PaymentMethodSerializer, \
    PaymentSerializerWriter, PaymentSerializerReader, ExpenseGroupSerializerWriter, ExpenseGroupSerializerReader, TagSerializer, ItemSerializerReader, ItemSerializerWriter, UserSerializer, \
    NotificationSerializer, ValidationSerializerWriter, ValidationSerializerReader
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



class RegardingViewSet(viewsets.ModelViewSet):
    queryset = Regarding.objects.all()
    serializer_class = RegardingSerializerWriter

    def get_serializer_class(self):
        method = self.request.method
        if method == 'PATCH' or method == 'POST':
            return RegardingSerializerWriter
        else:
            return RegardingSerializerReader


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
    queryset = Expense.objects.all()
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
            instances = Expense.objects.filter(id__in=ids)
            instances.delete()
            print(request.query_params.get('ids'))
            return response.Response(status=status.HTTP_204_NO_CONTENT)
        super().destroy(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        print(request.data.keys())
        expense_data = {**request.data}
        expense_data["cost"] = expense_data["cost"].replace(".", "").replace(",", ".")
        expense_serializer = self.get_serializer(data=expense_data)
        expense_serializer.is_valid(raise_exception=True)
        self.perform_create(expense_serializer)
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
        headers = self.get_success_headers(expense_serializer.data)
        return response.Response(expense_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, pk=None, *args, **kwargs):
        print(request.data)
        expense = Expense.objects.get(id=pk)
        expense_data = {**request.data}
        expense_data["cost"] = expense_data["cost"].replace(".", "").replace(",", ".")
        expense_serializer = self.get_serializer(expense, data=expense_data, partial=True)
        expense_serializer.is_valid(raise_exception=True)
        expense_serializer.save()
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
        return response.Response(expense_serializer.data, status=status.HTTP_200_OK, headers=headers)

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
        group = ExpenseGroup.objects.filter(hash_id=hash)
        if group.exists():
            group.first().members.add(User.objects.get(id=1))
            return response.Response(status=status.HTTP_200_OK)
        else:
            return response.Response(status=status.HTTP_404_NOT_FOUND)


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