from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Payment, Expense
from core.services.expenses import update_expenses_validation_status


class Command(BaseCommand):
    help = "Update the expense validation status checking if all validations were validated"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.today = timezone.now().date()

    def handle(self, *args, **options):
        expenses = self.get_expenses()
        self.update_expenses(expenses)

    def get_expenses(self):
        expenses = Expense.objects.select_related("regarding").prefetch_related("validations")
        expenses = expenses.filter(validation_status=Expense.ValidationStatuses.AWAITING)
        return expenses

    def update_expenses(self, expenses):
        update_expenses_validation_status(expenses)
