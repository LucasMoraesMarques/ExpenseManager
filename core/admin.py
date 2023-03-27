from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, Validation, \
    Notification, Membership



@admin.register(ExpenseGroup)
class ExpenseGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "hash_id")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    pass


@admin.register(Regarding)
class RegardingGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    pass


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    pass


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    pass


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    pass


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    pass


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    pass


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    pass

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    pass


@admin.register(Validation)
class ValidationAdmin(admin.ModelAdmin):
    pass
