from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item
from django.db.models import F, Subquery, Sum, OuterRef, Count, ExpressionWrapper, Q, Avg, BooleanField, When, Case
from decimal import Decimal
from core.services import objects
from core.serializers import ItemSerializer
from rest_framework import serializers
import json

TOTAL_ANNOTATION = {"total_expenses": Sum("cost"),
                    "total_payments": Sum("payments__value"),
                    "total_validation": Sum(Case(When(
                        payments__payment_status=Payment.PaymentStatuses.AWAITING_VALIDATION,
                        then="payments__value"), default=Decimal(0))),
                    "total_open": Sum(Case(When(
                        payments__payment_status=Payment.PaymentStatuses.AWAITING_PAYMENT,
                        then="payments__value"), default=Decimal(0))),
                    "total_paid": Sum(Case(When(
                        payments__payment_status=Payment.PaymentStatuses.PAID,
                        then="payments__value"), default=Decimal(0))),
                    "total_overdue": Sum(Case(When(
                        payments__payment_status=Payment.PaymentStatuses.OVERDUE,
                        then="payments__value"), default=Decimal(0))),

                    }


def calc_totals_by_regarding(regarding_id):
    regarding = objects.get_regarding_by_id(regarding_id)
    items = Item.objects.all()
    members = regarding.expense_group.members.all()
    members_ids = list(members.values_list("id", flat=True))
    shared_and_individual = {i: {"shared": Decimal(0), "individual": {i:Decimal(0) for i in members_ids}} for i in members_ids}
    expenses = objects.get_expenses_by_regarding(regarding_id)
    totals_by_payer = expenses.values("payments__payer").annotate(**TOTAL_ANNOTATION)
    totals_by_regarding = expenses.values("regarding").annotate(**TOTAL_ANNOTATION)
    items = ItemSerializer(items, many=True).data
    total_paid_shared = 0
    for item in items:
        expense = item["expense"]
        payments = expense["payments"]

        for payment in payments:
            payer = payment["payer"]
            if item["consumers"] == members_ids:
                shared_and_individual[payer]["shared"] += Decimal(item["price"])
                total_paid_shared += Decimal(item["price"])
            else:
                for consumer in item["consumers"]:
                    shared_and_individual[payer]["individual"][consumer] += Decimal(item["price"])

    for payer, data in shared_and_individual.items():
        shared_and_individual[payer]["balance"] = round(data["shared"] - total_paid_shared / 3, 4)

    for i, item in enumerate(totals_by_payer):
        payer = item["payments__payer"]
        totals_by_payer[i].update(shared_and_individual[payer])


    print(totals_by_regarding)
    print(totals_by_payer)
    # payments = objects.get_payments_by_expenses(regarding_id)
