from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Notification
from django.db.models import F
from core.services import push_notifications

class Command(BaseCommand):
    help = "Send notifications through FCM Api"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.today = timezone.now().date()

    def handle(self, *args, **options):
        notifications = self.get_notifications()
        print(f"{notifications.count()} push notifications sent.")
        self.send_notifications(notifications)

    def get_notifications(self):
        notifications = Notification.objects.select_related("user").exclude(was_sent=True).exclude(user__fcm_token__isnull=True)
        return notifications

    def send_notifications(self, notifications):
        notifications_to_update = []
        for notification in notifications:
            notifications_to_update.append(notification)
            push_notifications.send_notification(notification)

        Notification.objects.bulk_update(notifications_to_update, fields=["was_sent", "updated_at"])
