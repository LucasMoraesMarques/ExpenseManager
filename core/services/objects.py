from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item


def get_regarding_by_id(regarding_id):
    try:
        regarding = Regarding.objects.select_related("expense_group").prefetch_related("expenses").get(id=regarding_id)
    except Regarding.DoesNotExist:
        return []
    else:
        return regarding


def get_expenses_by_regarding(regarding_id):
    try:
        regarding = Regarding.objects.select_related("expense_group").prefetch_related("expenses").get(id=regarding_id)
        expenses = regarding.expenses.all()
    except Regarding.DoesNotExist:
        return []
    else:
        return expenses


def get_expense_payments(expense_id):
    try:
        expense = Expense.objects.select_related("regarding").prefetch_related("validated_by", "payments").get(id=expense_id)
        payments = expense.expenses.all()
    except Expense.DoesNotExist:
        return []
    else:
        return payments


