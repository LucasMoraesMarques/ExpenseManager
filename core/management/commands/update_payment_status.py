from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Payment, Expense, PaymentMethod
from django.db.models import Q, When, Case


class Command(BaseCommand):
    help = "Update the payment status checking if the expense is valid"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.today = timezone.now().date()

    def handle(self, *args, **options):
        payments = self.get_payments()
        self.update_payments(payments)

    def get_payments(self):
        payments = Payment.objects.select_related("payment_method", "expense")
        payments = payments.exclude(payment_status__in=[Payment.PaymentStatuses.PAID])
        return payments

    def update_payments(self, payments):
        validated_payments = payments.filter(expense__validation_status=Expense.ValidationStatuses.VALIDATED)
        validated_payments = validated_payments.annotate(is_paid=Case(
            When(
                payment_method__type__in=[PaymentMethod.Types.CASH, PaymentMethod.Types.DEBIT_CARD],
                then=True,
            ),
            When(
                Q(payment_method__type__in=PaymentMethod.Types.CREDIT_CARD) & Q(payment_method__compensation_day__gte=self.today.day),
                then=True,
            ),
            default=False,
        ))
        payments_paid = validated_payments.filter(is_paid=True)
        print(f"{payments_paid.count()} payments changed to PAID")
        payments_paid.update(payment_status=Payment.PaymentStatuses.PAID)
