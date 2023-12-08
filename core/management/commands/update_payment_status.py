from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Payment, Expense, PaymentMethod
from core.services.expenses import update_expenses_payment_status, update_payments_payment_status


class Command(BaseCommand):
    help = "Update the payment status checking if the expense is valid"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, *args, **options):
        payments = self.get_payments()
        expenses = self.get_expenses()
        update_expenses_payment_status(expenses)
        update_payments_payment_status(payments)

    def get_payments(self):
        payments = Payment.objects.select_related("payment_method", "expense")
        payments = payments.exclude(payment_status=Payment.PaymentStatuses.PAID)
        return payments

    def get_expenses(self):
        expenses = Expense.objects.prefetch_related("payments")
        expenses = expenses.exclude(payment_status=Payment.PaymentStatuses.PAID)
        return expenses

