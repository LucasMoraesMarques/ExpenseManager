from rest_framework import routers
from core import views
router = routers.DefaultRouter()
router.register("expense-groups", views.ExpenseGroupViewSet)
router.register("regardings", views.RegardingViewSet)
router.register("wallets", views.WalletViewSet)
router.register("payments-methods", views.PaymentMethodViewSet)
router.register("payments", views.PaymentViewSet)
router.register("expenses", views.ExpenseViewSet)
router.register("tags", views.TagViewSet)
router.register("items", views.ItemViewSet)
router.register("users", views.UserViewSet)

urlpatterns = router.urls