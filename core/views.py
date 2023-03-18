from rest_framework import viewsets, response, status, views
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, User
from core.serializers import ExpenseSerializer, RegardingSerializerWriter, RegardingSerializerReader, WalletSerializer, PaymentMethodSerializer, \
    PaymentSerializer, ExpenseGroupSerializerWriter, ExpenseGroupSerializerReader, TagSerializer, ItemSerializer, UserSerializer
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
    serializer_class = PaymentSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer

    def destroy(self, request, *args, **kwargs):
        if "ids" in request.query_params:
            ids = request.query_params.get('ids').split(',')
            instances = Expense.objects.filter(id__in=ids)
            instances.delete()
            print(request.query_params.get('ids'))
            return response.Response(status=status.HTTP_204_NO_CONTENT)
        super().destroy(request, *args, **kwargs)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer


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





