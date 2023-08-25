from core.models import Notification
from core.services import push_notifications


def get_members(expense_group, request, exclude_current_user=False):
    members = expense_group.members.all()
    if exclude_current_user:
        members = members.exclude(id=request.user.id)
    return members


def notify_members(members, notification_data):
    notifications_to_update = []
    for member in members:
        notification = Notification.objects.create(**notification_data, user=member)
        push_notifications.send_notification(notification)
        notifications_to_update.append(notification)
    Notification.objects.bulk_update(notifications_to_update, fields=["was_sent", "updated_at"])

