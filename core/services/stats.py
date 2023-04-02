from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item
from django.db.models import F, Subquery, Sum, OuterRef, Count, ExpressionWrapper, Q, Avg, Value, When, Case
from django.db.models.functions import Concat
from decimal import Decimal
from core.services import objects
from rest_framework import serializers
import json
import copy
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


def calc_totals_by_regarding(regarding_id, items):
    regarding = objects.get_regarding_by_id(regarding_id)
    memberships = regarding.expense_group.memberships.all()
    memberships = memberships.annotate(full_name=Concat(F("user__first_name"), Value(' '), F("user__last_name")))
    members = {}
    for membership in memberships:
        members[membership.user.id] = {"weight": membership.average_weight}
    print(members)
    members_ids = members.keys()
    group_weighed_n = memberships.aggregate(n=Sum("average_weight"))['n']
    shared_and_individual = {i: {"shared": Decimal(0), "partial_shared": Decimal(0), "individual": Decimal(0), "total_paid_shared": Decimal(0)} for i in members_ids}
    expenses = objects.get_expenses_by_regarding(regarding_id)
    totals_by_payer = expenses.values("payments__payer").annotate(**TOTAL_ANNOTATION)
    totals_by_regarding = expenses.values("regarding").annotate(**TOTAL_ANNOTATION)
    totals_by_day_of_regarding = {}
    for expense in expenses:
        if expense.date.day not in totals_by_day_of_regarding:
            totals_by_day_of_regarding[expense.date.day] = expense.cost
        else:
            totals_by_day_of_regarding[expense.date.day] += expense.cost

    total_paid_shared = 0
    total_member_vs_member = {}
    for x_member_id in members_ids:
        total_member_vs_member[x_member_id] = {}
        for y_member_id in members_ids:
            if x_member_id != y_member_id:
                total_member_vs_member[x_member_id][y_member_id] = Decimal(0)

    for item in items:
        #print(item['id'], item['price'], item['consumers'])
        expense = item["expense"]
        payments = expense["payments"]
        print(item['price'], item['consumers'], payments[0]['payer'])

        for payment in payments:
            payer = payment['payer']['id']
            if set(item["consumers"]) == set(members_ids):  # Shared between all members
                for consumer in members_ids:
                    shared_and_individual[consumer]["shared"] += Decimal(item["price"])
                shared_and_individual[payer]['total_paid_shared'] += Decimal(item["price"])
                for consumer in item["consumers"]:
                    if consumer != payer:
                        total_member_vs_member[payer][consumer] += (Decimal(item["price"]) * members[consumer]['weight'] / group_weighed_n)
            elif len(item["consumers"]) == 1:  # Individual
                consumer = item["consumers"][0]
                shared_and_individual[consumer]["individual"] += Decimal(item["price"])
                if consumer != payer:
                    total_member_vs_member[payer][consumer] += Decimal(item["price"])
            else:  # Partial shared
                n_consumers = len(item["consumers"])
                for consumer in item["consumers"]:
                    shared_and_individual[consumer]["partial_shared"] += Decimal(item["price"])
                    if consumer != payer:
                        total_member_vs_member[payer][consumer] += (Decimal(item["price"])/n_consumers)

    for payer, data in shared_and_individual.items():
        member_weight = members[payer]['weight']
        total_paid_shared = shared_and_individual[payer]['total_paid_shared']
        expected_total_paid = data["shared"]*member_weight / group_weighed_n
        shared_and_individual[payer]['expected_total_paid'] = expected_total_paid
        print(total_paid_shared, expected_total_paid)
        shared_and_individual[payer]["balance"] = round(total_paid_shared - expected_total_paid, 4)

    for i, item in enumerate(totals_by_payer):
        payer = item["payments__payer"]
        if payer:
            totals_by_payer[i].update(shared_and_individual[payer])


    print(total_member_vs_member)
    total_member_vs_member2 = copy.deepcopy(total_member_vs_member)
    for x_member_id in members_ids:
        for y_member_id in members_ids:
            if x_member_id != y_member_id:
                value = total_member_vs_member[x_member_id][y_member_id] - total_member_vs_member[y_member_id][x_member_id]
                if value > 0:
                    total_member_vs_member2[x_member_id][y_member_id] = value
                else:
                    del total_member_vs_member2[x_member_id][y_member_id]
    print(total_member_vs_member2)
    total_member_vs_member_with_names = {}
    for x_member_id in members_ids:
        debts_data = total_member_vs_member2[x_member_id]
        x_member_name_x = memberships.get(user__id=x_member_id).full_name
        total_member_vs_member_with_names[x_member_name_x] = {}
        for y_member_id in debts_data.keys():
            y_member_name_x = memberships.get(user__id=y_member_id).full_name
            total_member_vs_member_with_names[x_member_name_x][y_member_name_x] = debts_data[y_member_id]

    print(total_member_vs_member2)
    print(total_member_vs_member_with_names)
    #print(totals_by_regarding)
    #print("\nzn")
    #print(totals_by_payer)
    return totals_by_regarding[0], totals_by_payer, totals_by_day_of_regarding, total_member_vs_member_with_names
    # payments = objects.get_payments_by_expenses(regarding_id)
