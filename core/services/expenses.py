from django.utils import timezone
from core.models import Expense, ActionLog, Validation, Notification, Item, Payment
from core.services import expense_groups, push_notifications, validations, google_drive
from babel.numbers import format_currency
from core.serializers import ItemSerializerWriter, PaymentSerializerWriter
import base64
import io
import re
from django.conf import settings
import pandas as pd
from dateutil.relativedelta import relativedelta


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


def create_gallery(expense):
    gallery_folder = {
        "metadata":{
            "name": f"{expense.regarding.name} - {expense.name}",
        }
    }
    if expense.regarding.expense_group.drive_id:
        drive_id = expense.regarding.expense_group.drive_id
    else:
        group_folder = {
            "metadata": {
                "name": expense.regarding.expense_group.name,
                "parents": [settings.GOOGLE_DRIVE_BASE_FOLDER_ID]
            },
            "data": None
        }
        drive_id = google_drive.create_folder(group_folder)
        expense.regarding.expense_group.drive_id = drive_id
        expense.regarding.expense_group.save(update_fields=["drive_id"])

    gallery_folder["metadata"]["parents"] = [drive_id]
    return google_drive.create_folder(gallery_folder)


def upload_images(gallery, expense):
    images_to_upload = []
    old_images = []
    if gallery:
        images_to_upload = list(filter(lambda x: x.get("create", False), gallery.get("photos", [])))
    if expense.gallery is not None:
        gallery_id = expense.gallery.get("id", "")
        old_images = list(filter(lambda x: not x.get("create", False), gallery.get("photos", [])))
    else:
        gallery_id = create_gallery(expense)
    images_to_save = []
    for image in images_to_upload:
        image_type = image['src'].split(';')[0].split('/')[1]
        file = {"metadata": {'name': f'image.{image_type}', "parents": [gallery_id]}, "data": io.BytesIO(base64.b64decode(re.sub("data:image\/.*?;base64", '', image['src']))), "mimetype": f"image/{image_type}"}
        file_id = google_drive.upload_media_file(file)

        if file_id:
            images_to_save.append({"id": file_id, "src": f"https://drive.google.com/uc?export=view&id={file_id}"})
    new_gallery = {"id": gallery_id, "photos": old_images + images_to_save}
    expense.gallery = new_gallery
    expense.save(update_fields=["gallery"])


def update_expenses_validation_status(expenses):
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


def update_expenses_payment_status(expenses):
    for expense in expenses:
        payments_statutes = list(expense.payments.values_list("payment_status", flat=True))
        if Payment.PaymentStatuses.AWAITING_PAYMENT in payments_statutes:
            expense.payment_status = Payment.PaymentStatuses.AWAITING_PAYMENT
        elif payments_statutes.count(Payment.PaymentStatuses.PAID) == len(payments_statutes):
            expense.payment_status = Payment.PaymentStatuses.PAID
        else:
            expense.payment_status = Payment.PaymentStatuses.AWAITING_VALIDATION
    Expense.objects.bulk_update(expenses, ['payment_status'], batch_size=2000)


def update_payments_payment_status(payments):
    today = timezone.now().date()
    validated_payments = payments.filter(
        expense__validation_status=Expense.ValidationStatuses.VALIDATED
    )
    not_validated_payments = payments.exclude(
        expense__validation_status=Expense.ValidationStatuses.VALIDATED
    )
    if validated_payments.count():
        df = pd.DataFrame(
            validated_payments.values(
                "id",
                "payment_method__type",
                "payment_method__compensation_day",
                "expense__date",
            )
        )
        df.fillna(1, inplace=True)
        df.astype({"payment_method__compensation_day": "int32"})
        df["current_compensation_date"] = df["payment_method__compensation_day"].map(
            lambda x: today + relativedelta(day=int(x))
        )
        print(df)
        df["last_compensation_date"] = df["current_compensation_date"] + relativedelta(
            months=-1
        )
        df["is_paid"] = df.apply(
            lambda x: (x["payment_method__type"] in ["DEBIT", "CASH"])
                      | (
                              (
                                      (
                                              x["last_compensation_date"]
                                              <= x["expense__date"]
                                              <= x["current_compensation_date"]
                                      )
                                      | (x["expense__date"] < x["last_compensation_date"])
                              )
                              & (today >= x["current_compensation_date"])
                      ),
            axis=1,
        )
        payments_paid_ids = df[df["is_paid"]].loc[:, "id"].tolist()
        payments_paid = validated_payments.filter(id__in=payments_paid_ids)
        payments_not_paid = validated_payments.exclude(id__in=payments_paid_ids)
        payments_paid.update(payment_status=Payment.PaymentStatuses.PAID)
        payments_not_paid.update(payment_status=Payment.PaymentStatuses.AWAITING_PAYMENT)
    not_validated_payments.update(payment_status=Payment.PaymentStatuses.AWAITING_VALIDATION)
