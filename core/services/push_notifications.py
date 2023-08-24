import requests
import json
from django.conf import settings


def send_notification(notification):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'key=' + settings.FCM_SERVER_KEY,
    }
    try:
        body = {
            'notification': {'title': notification.title,
                             'body': notification.body,
                             },
            'to':
                notification.user.fcm_token,
            'priority': 'high',
            'data': {},
        }
        response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, data=json.dumps(body))

        if response.status_code == 200:
            response = response.json()
            if response.get("failure", 1) == 0 and response.get("success", 0) == 1:
                notification.was_sent = True
            else:
                raise Exception(f"Firebase returned failure: {response.get('results', [])}")
        else:
            raise Exception(f"Error in request: {response.status_code} - {response.text}")
    except Exception as exc:
        notification.user.fcm_token = None
        notification.user.save()
        print(f"[NOTIFICATION] Error sending notification {notification.id} - {exc}")
