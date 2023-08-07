from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Notification
from django.db.models import F
from django.conf import settings
import requests
import json


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
        notifications = Notification.objects.select_related("user").exclude(was_sent=True)
        notifications = notifications.annotate(device_token=F('user__fcm_token'))
        return notifications

    def send_notifications(self, notifications):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'key=' + settings.FCM_SERVER_KEY,
        }
        notifications_to_update = []
        for notification in notifications:
            try:
                body = {
                    'notification': {'title': notification.title,
                                     'body': notification.body,
                                     #'image': notification.payload.get("image", None),
                                     "android_channel_id": "smart_buy_notifications_channel",
                                     "channel_id":"smart_buy_notifications_channel",
                                     "sound": "default"
                                     },
                    'to':
                        notification.device_token,
                    'priority': 'high',
                    'data': {},
                }
                print(body)
                response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))

                if response.status_code == 200:
                    response = response.json()
                    if response.get("failure", 1) == 0 and response.get("success", 0) == 1:
                        notification.was_sent = True
                        notifications_to_update.append(notification)
                    else:
                        raise Exception(f"Firebase returned failure: {response.get('results', [])}")
                else:
                    raise Exception(f"Error in request: {response.status_code} - {response.text}")
            except Exception as exc:
                print(f"[NOTIFICATION] Error sending notification {notification.id} - {exc}")
        Notification.objects.bulk_update(notifications_to_update, fields=["was_sent", "updated_at"])
