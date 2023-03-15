from rest_framework import viewsets
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, User
from core.serializers import ExpenseGroupSerializer, RegardingSerializer, WalletSerializer, PaymentMethodSerializer, \
    PaymentSerializer, ExpenseSerializer, TagSerializer, ItemSerializer, UserSerializer
from core.services import stats


class ExpenseGroupViewSet(viewsets.ModelViewSet):
    queryset = ExpenseGroup.objects.all()
    serializer_class = ExpenseGroupSerializer

    def get_queryset(self):
        #self.queryset = self.queryset.filter(user=self.request.user)
        self.queryset = self.queryset.prefetch_related("regardings", "regardings__expenses")
        return self.queryset



class RegardingViewSet(viewsets.ModelViewSet):
    queryset = Regarding.objects.all()
    serializer_class = RegardingSerializer



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



class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
