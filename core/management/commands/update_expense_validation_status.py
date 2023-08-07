from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Payment, Expense


class Command(BaseCommand):
    help = "Update the expense validation status checking if all validations were validated"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.today = timezone.now().date()

    def handle(self, *args, **options):
        payments = self.get_expenses()
        self.update_expenses(payments)

    def get_expenses(self):
        expenses = Expense.objects.select_related("regarding").prefetch_related("validations")
        expenses = expenses.filter(validation_status=Expense.ValidationStatuses.AWAITING)
        return expenses

    def update_expenses(self, expenses):
        for expense in expenses:
            expense_validations = expense.validations.all()
            validated = expense_validations.filter(validated_at__isnull=False)
            rejected = expense_validations.filter(validated_at__isnull=True, is_active=False)
            if expense_validations.count() == validated.count():
                expense.validation_status = Expense.ValidationStatuses.VALIDATED
            elif expense_validations.count() == rejected.count():
                expense.validation_status = Expense.ValidationStatuses.REJECTED
            else:
                expense.validation_status = Expense.ValidationStatuses.AWAITING
        Expense.objects.bulk_update(expenses, ['validation_status'], batch_size=2000)
        print(f"{expenses.count()} expenses checked")
