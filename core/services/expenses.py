from core.models import Expense, ActionLog, Validation, Notification, Item, Payment
from core.services import expense_groups, push_notifications, validations
from babel.numbers import format_currency
from core.serializers import ItemSerializerWriter, PaymentSerializerWriter


def batch_delete_expense(expenses_ids):
    instances = Expense.objects.filter(id__in=expenses_ids).select_related("regarding__expense_group")
    delete_by_groups = {}
    for instance in instances:
        if instance.regarding.expense_group.id not in delete_by_groups.keys():
            delete_by_groups[instance.regarding.expense_group.id] = [instance.name]
        else:
            delete_by_groups[instance.regarding.expense_group.id].append(instance.name)
    instances.delete()
    return delete_by_groups


def notify_members_about_expense_deletion(request, expense):
    notification_data = {"title": "Despesa deletada",
                         "body": f"O membro {request.user.full_name} deletou a despesa {expense.name} de valor R$ {format_currency(expense.cost, 'BRL', '#,##0.00', locale='pt_BR')}"}
    members = expense_groups.get_members(expense.regarding.expense_group, request, exclude_current_user=True)
    expense_groups.notify_members(members, notification_data)


def create_items_for_new_expense(items, expense):
    for item in items:
        consumers = []
        for consumer in item['consumers']:
            consumers.append(consumer['id'])
        item.update({
            "consumers": consumers, "expense": expense.id, "price": item["price"].replace(".", "").replace(",", ".")
        })
    print(items)
    item_serializer = ItemSerializerWriter(data=items, many=True)
    item_serializer.is_valid(raise_exception=True)
    item_serializer.save()


def create_payments_for_new_expense(payments, expense):
    for payment in payments:
        payment.update({"expense": expense.id, "payer": payment["payer"]["id"],
                        "payment_method": payment["payment_method"]["id"],
                        "value": payment["value"].replace(".", "").replace(",", ".")})
    payment_serializer = PaymentSerializerWriter(data=payments, many=True)
    payment_serializer.is_valid(raise_exception=True)
    payment_serializer.save()


def notify_expense_validators(request, expense):
    for validator in request.data.get('validators', []):
        Validation.objects.create(validator_id=validator['id'], expense_id=expense.id)
        notification = Notification.objects.create(
            title=f"Validação solicitada",
            body=f"{request.user.full_name} solicitou sua validação na despesa {expense.name}",
            user_id=validator['id'],
        )
        push_notifications.send_notification(notification)


def notify_members_about_new_expense(request, expense):
    notification_data = {"title": "Despesa adicionada",
                         "body": f"O membro {request.user.full_name} adicionou a despesa {expense.name} de valor R$ {format_currency(expense.cost, 'BRL', '#,##0.00', locale='pt_BR')}"}
    members = expense_groups.get_members(expense.regarding.expense_group, request, exclude_current_user=True)
    expense_groups.notify_members(members, notification_data)


def notify_members_about_expense_update(request, expense):
    notification_data = {"title": "Despesa editada",
                         "body": f"O membro {request.user.full_name} editou a despesa {expense.name} de valor R$ {format_currency(expense.cost, 'BRL', '#,##0.00', locale='pt_BR')}"}
    members = expense_groups.get_members(expense.regarding.expense_group, request, exclude_current_user=True)
    expense_groups.notify_members(members, notification_data)


def update_items(items, expense):
    items_serializers_to_save = []
    for item in items:
        consumers = []
        for consumer in item['consumers']:
            consumers.append(consumer['id'])
        item.update({
            "consumers": consumers, "expense": expense.id, "price": item["price"].replace(".", "").replace(",", ".")
        })
        instance = Item.objects.get(pk=item['id'])
        item_serializer_update = ItemSerializerWriter(instance, data=item, partial=True)
        item_serializer_update.is_valid(raise_exception=True)
        items_serializers_to_save.append(item_serializer_update)
    for item_serializer in items_serializers_to_save:
        item_serializer.save()


def update_payments(payments, expense):
    payments_serializers_to_save = []
    for payment in payments:
        instance = Payment.objects.get(pk=payment['id'])
        payment.update({"expense": expense.id, "payer": payment["payer"]["id"],
                        "payment_method": payment["payment_method"]["id"],
                        "value": payment["value"].replace(".", "").replace(",", ".")})
        payment_serializer_update = PaymentSerializerWriter(instance, data=payment, partial=True)
        payment_serializer_update.is_valid(raise_exception=True)
        payments_serializers_to_save.append(payment_serializer_update)
    for payment_serializer in payments_serializers_to_save:
        payment_serializer.save()


def handle_items_edition(items, expense):
    all_ids = [item.get("id", 0) for item in items]
    items_to_create = list(filter(lambda x: x.get("create", False), items))
    items_to_update = list(filter(lambda x: x.get("edited", False) and x.get("created_at"), items))
    items_to_delete = expense.items.exclude(id__in=all_ids)
    items_to_delete_names = list(items_to_delete.values("name", "price"))
    items_to_delete.delete()
    create_items_for_new_expense(items_to_create, expense)
    update_items(items_to_update, expense)
    return items_to_delete_names


def handle_payments_edition(payments, expense):
    payments_to_create = list(filter(lambda x: x.get("create", False), payments))
    payments_to_update = list(filter(lambda x: x.get("edited", False) and x.get("created_at"), payments))
    payments_to_delete = expense.payments.exclude(id__in=[item['id'] for item in payments])
    payments_to_delete_data = list(payments_to_delete.values("payer__first_name", "value"))
    payments_to_delete.delete()
    create_payments_for_new_expense(payments_to_create, expense)
    update_payments(payments_to_update, expense)
    return payments_to_delete_data


def ask_validators_to_revalidate(request, expense):
    expense.validations.update(is_active=True, validated_at=None, note="")
    for validation in expense.validations.all():
        validations.ask_for_revalidation(request, validation)