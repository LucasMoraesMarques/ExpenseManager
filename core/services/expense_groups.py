from core.models import Notification, GroupInvitation, User, Membership
from core.services import push_notifications
from datetime import datetime, timedelta

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


def notify_group_was_created(membership):
    notification = Notification.objects.create(
        title=f"Novo grupo criado",
        body=f"O grupo {membership.group.name} foi criado com sucesso!",
        user=membership.user,
    )
    push_notifications.send_notification(notification)


def create_invitations(request, group):
    invitations = request.data.get("invitations", [])
    now = datetime.now() - timedelta(seconds=5)
    for invitation in invitations:
        if invitation.get('create', False):
            group_invitation = GroupInvitation.objects.create(sent_by_id=invitation['sent_by']['id'],
                                                              invited_id=invitation['invited']['id'],
                                                              expense_group_id=group.id)
            group_invitation.save()
    invitations = GroupInvitation.objects.filter(expense_group=group, created_at__gte=now).select_related("sent_by", "invited")
    return invitations


def notify_users_invited(invitations):
    for invitation in invitations:
        notification = Notification.objects.create(
            title=f"Convite para o grupo {invitation.expense_group.name}",
            body=f"{invitation.sent_by.full_name} te convidou para entrar no grupo {invitation.expense_group.name}",
            user_id=invitation.invited.id,
            payload={"notification_type": "invitation", "data": {"group_id": invitation.expense_group.id}}
        )
        push_notifications.send_notification(notification)


def notify_users_removed(removed_members, group, user):
    for member in removed_members:
        notification = Notification.objects.create(
            title=f"Você foi removido(a) do grupo {group.name}",
            body=f"O membro {user.full_name} removeu você do grupo. Se acha que isso foi um engano, contate-o.",
            user=member,
        )
        push_notifications.send_notification(notification)


def remove_members(request, group):
    removed_ids = request.data.get("removed", [])
    removed_members = User.objects.filter(id__in=removed_ids)
    memberships_to_remove = group.memberships.filter(user__in=removed_members)
    memberships_to_remove.delete()
    return removed_members


def update_memberships(request, group):
    memberships = request.data.get("memberships", [])
    for membership_data in memberships:
        if membership_data.get('updated', False):
            membership = group.memberships.get(id=membership_data.get('id'))
            new_level_index = Membership.Levels.labels.index(membership_data.get('level').upper())
            new_level = Membership.Levels.values[new_level_index]
            membership.level = new_level
            membership.save(update_fields=['level'])

