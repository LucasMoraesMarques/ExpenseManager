from core.models import (
    ExpenseGroup,
    Regarding,
    Wallet,
    PaymentMethod,
    Payment,
    Expense,
    Tag,
    Item,
)
from django.db.models import F, Sum, Value, When, Case
from django.db.models.functions import Concat
from decimal import Decimal
import copy

TOTAL_ANNOTATION = {
    "total_payments": Sum("payments__value"),
    "total_validation": Sum(
        Case(
            When(
                payments__payment_status=Payment.PaymentStatuses.AWAITING_VALIDATION,
                then="payments__value",
            ),
            default=Decimal(0),
        )
    ),
    "total_open": Sum(
        Case(
            When(
                payments__payment_status=Payment.PaymentStatuses.AWAITING_PAYMENT,
                then="payments__value",
            ),
            default=Decimal(0),
        )
    ),
    "total_paid": Sum(
        Case(
            When(
                payments__payment_status=Payment.PaymentStatuses.PAID,
                then="payments__value",
            ),
            default=Decimal(0),
        )
    ),
    "total_overdue": Sum(
        Case(
            When(
                payments__payment_status=Payment.PaymentStatuses.OVERDUE,
                then="payments__value",
            ),
            default=Decimal(0),
        )
    ),
}


def calculate_total_by_day_in_regarding(expenses):
    totals_by_day_of_regarding = {}
    values_and_days = expenses.values_list("cost", "date")
    for value, date in map(lambda item: item, values_and_days):
        if date.day not in totals_by_day_of_regarding:
            totals_by_day_of_regarding[date.day] = value
        else:
            totals_by_day_of_regarding[date.day] += value
    return totals_by_day_of_regarding


def calculate_general_totals(expenses):
    general_totals = dict(expenses.values("regarding").annotate(**TOTAL_ANNOTATION)[0])
    general_totals["total_expenses"] = expenses.values("regarding").aggregate(
        total_cost=Sum("cost")
    )["total_cost"]
    return general_totals


def calculate_balance_by_member(totals_by_member, total_member_vs_member, expenses, group_total_weight):
    for creditor in total_member_vs_member.keys():
        for debtor in total_member_vs_member[creditor].keys():
            totals_by_member[creditor]["total_to_receive"] += total_member_vs_member[creditor][debtor]
            totals_by_member[debtor]["total_to_pay"] += total_member_vs_member[creditor][debtor]
    for member, totals in totals_by_member.items():
        total_paid_shared = totals_by_member[member]["total_paid_shared"]
        expected_total_paid = totals["shared"] * totals["weight"] / group_total_weight
        totals_by_member[member]["expected_total_paid"] = expected_total_paid
        totals_by_member[member]["balance"] = round(
            total_paid_shared - expected_total_paid, 2
        )
        totals_by_member[member]["total_paid"] = expenses.filter(payments__payer_id=member).aggregate(total_paid=Sum("payments__value"))["total_paid"] or Decimal(0)
        totals_by_member[member]["final_balance"] = round(totals_by_member[member]["total_to_receive"] - totals_by_member[member]["total_to_pay"], 2)
        totals_by_member[member]["total_to_receive"] = round(totals_by_member[member]["total_to_receive"], 2)
        totals_by_member[member]["total_to_pay"] = round(totals_by_member[member]["total_to_pay"], 2)
    return totals_by_member


def calculate_totals_by_member_and_member_versus_member(expense_items, memberships, group_total_weight):
    totals_by_member = {
        membership.user.id: {
            "shared": Decimal(0),
            "partial_shared": Decimal(0),
            "individual": Decimal(0),
            "total_paid_shared": Decimal(0),
            "weight": membership.average_weight,
            "full_name": membership.full_name,
            "total_to_receive": Decimal(0),
            "total_to_pay": Decimal(0),
            "final_balance": Decimal(0),
            "total_paid": Decimal(0)
        }
        for membership in memberships
    }
    members_ids = totals_by_member.keys()

    total_member_vs_member = {}
    for x_member_id in members_ids:
        total_member_vs_member[x_member_id] = {}
        for y_member_id in members_ids:
            if x_member_id != y_member_id:
                total_member_vs_member[x_member_id][y_member_id] = Decimal(0)

    for item in expense_items:
        expense = item["expense"]
        payments = expense["payments"]
        payer = payments[0]["payer"]["id"]
        if set(item["consumers"]) == set(members_ids):  # Shared between all members
            for consumer in members_ids:
                totals_by_member[consumer]["shared"] += Decimal(item["price"])
            totals_by_member[payer]["total_paid_shared"] += Decimal(item["price"])
            for consumer in item["consumers"]:
                if consumer != payer:
                    total_member_vs_member[payer][consumer] += (
                            Decimal(item["price"])
                            * totals_by_member[consumer]["weight"]
                            / group_total_weight
                    )
        elif len(item["consumers"]) == 1:  # Individual
            consumer = item["consumers"][0]
            totals_by_member[consumer]["individual"] += Decimal(item["price"])
            if consumer != payer:
                total_member_vs_member[payer][consumer] += Decimal(item["price"])
        else:  # Partial shared
            n_consumers = len(item["consumers"])
            for consumer in item["consumers"]:
                totals_by_member[consumer]["partial_shared"] += Decimal(
                    item["price"]
                )
                if consumer != payer:
                    total_member_vs_member[payer][consumer] += (
                            Decimal(item["price"]) / n_consumers
                    )

    return totals_by_member, total_member_vs_member


def adjust_total_member_vs_member(total_member_vs_member, totals_by_member):
    members_ids = totals_by_member.keys()
    total_member_vs_member2 = copy.deepcopy(total_member_vs_member)
    for x_member_id in members_ids:
        for y_member_id in members_ids:
            if x_member_id != y_member_id:
                value = (
                    total_member_vs_member[x_member_id][y_member_id]
                    - total_member_vs_member[y_member_id][x_member_id]
                )
                if value > 0:
                    total_member_vs_member2[x_member_id][y_member_id] = value
                else:
                    del total_member_vs_member2[x_member_id][y_member_id]

    total_member_vs_member_with_names = {}
    for x_member_id in members_ids:
        debts_data = total_member_vs_member2[x_member_id]
        x_member_name_x = totals_by_member[x_member_id]['full_name']
        total_member_vs_member_with_names[x_member_name_x] = {}
        for y_member_id in debts_data.keys():
            y_member_name_x = totals_by_member[y_member_id]['full_name']
            total_member_vs_member_with_names[x_member_name_x][y_member_name_x] = round(
                debts_data[y_member_id], 2
            )
    return total_member_vs_member_with_names


def calculate_totals_of_regarding(regarding, items):
    expenses = regarding.expenses.prefetch_related("payments", "validations", "validations__validator").all()
    memberships = (
        regarding.expense_group.memberships.all()
        .select_related("user")
        .annotate(
            full_name=Concat(F("user__first_name"), Value(" "), F("user__last_name"))
        )
    )
    group_total_weight = sum(memberships.values_list("average_weight", flat=True))
    general_totals = calculate_general_totals(expenses)
    totals_by_day_of_regarding = calculate_total_by_day_in_regarding(expenses)
    (
        totals_by_member,
        total_member_vs_member,
    ) = calculate_totals_by_member_and_member_versus_member(items, memberships, group_total_weight)
    totals_by_member = calculate_balance_by_member(totals_by_member, total_member_vs_member, expenses, group_total_weight)
    total_member_vs_member = adjust_total_member_vs_member(
        total_member_vs_member, totals_by_member
    )
    return (
        general_totals,
        totals_by_member,
        totals_by_day_of_regarding,
        total_member_vs_member,
    )
