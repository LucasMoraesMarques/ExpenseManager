from rest_framework import routers
from core import views
from django.urls import path, include

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
router.register("notifications", views.NotificationViewSet)
router.register("validations", views.ValidationViewSet)
router.register("actions-log", views.ActionsLogViewSet)

urlpatterns = router.urls

urlpatterns = [
    path('', include(router.urls)),
    #path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    #path('login/', views.Login.as_view()),
    #path('register/', views.Register.as_view())
    path('join-group/<str:hash>', views.JoinGroup.as_view())
]