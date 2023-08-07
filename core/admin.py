from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, Validation, \
    Notification, Membership, ActionLog, GroupInvitation



@admin.register(ExpenseGroup)
class ExpenseGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "hash_id")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("group", "user", "joined_at", "average_weight", "level")


@admin.register(Regarding)
class RegardingGroupAdmin(admin.ModelAdmin):
    list_display = ("__str__", "start_date", "end_date", "is_closed")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    pass


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    pass


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payer', 'payment_method', 'expense', 'payment_status']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'payer', "validation_status"]


    def payer(self, obj):
        payers = []
        if obj.payments.count() > 0:
            for payment in obj.payments.all():
                payers.append(payment.payer.username)
        return ", ".join(payers)


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


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'type', "expense_group"]


@admin.register(GroupInvitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ['__str__', "expense_group", 'sent_by', "invited", "status"]