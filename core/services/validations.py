from core.models import Validation, Notification, Expense
from core.services import push_notifications


def ask_for_revalidation(request, validation):
    notification = Notification.objects.create(
        title=f"Validação solicitada novamente",
        body=f"{request.user.full_name} solicitou sua validação novamente." + f"Você rejeitou a despesa com a seguinte nota:{validation.note}" if validation.note else "",
        user=validation.validator,
    )
    validation.is_active = True
    validation.validated_at = None
    validation.note = ""
    validation.save()
    push_notifications.send_notification(notification)


def notify_creator_about_validation_change(request, validation):
    expense_creator = validation.expense.created_by
    if validation.validated_at:
        notification = Notification.objects.create(
            title=f"{request.user.full_name} validou uma despesa",
            body=f"Está tudo certo com a despesa {validation.expense.name}",
            user=expense_creator,
        )
    else:
        notification = Notification.objects.create(
            title=f"{request.user.full_name} rejeitou uma despesa",
            body=f"A despesa {validation.expense.name} foi rejeitada." + f"O motivo da rejeição foi {validation.note}" if validation.note else "",
            user=expense_creator,
        )
    push_notifications.send_notification(notification)


def update_validation_status_and_notify_creator(expense):
    expense_validations = Validation.objects.filter(expense=expense)
    validated = expense_validations.filter(validated_at__isnull=False)
    rejected = expense_validations.filter(validated_at__isnull=True, is_active=False)
    if expense_validations.count() == validated.count():
        expense.validation_status = Expense.ValidationStatuses.VALIDATED
    elif expense_validations.count() == rejected.count():
        expense.validation_status = Expense.ValidationStatuses.REJECTED
    else:
        expense.validation_status = Expense.ValidationStatuses.AWAITING
    expense.save(update_fields=['validation_status', 'updated_at'])
    if expense.validation_status == Expense.ValidationStatuses.VALIDATED:
        notification = Notification.objects.create(
            title=f"Despesa validada",
            body=f"Todos as validações solicitadas para a despesa {expense.name} foram aprovadas",
            user=expense.created_by,
        )
        push_notifications.send_notification(notification)
