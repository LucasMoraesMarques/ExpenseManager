from core.services import expense_groups
from core.serializers import RegardingSerializerReader
import json


def notify_members_about_new_regarding(request, group):
    notification_data = {"title": "Referência adicionada",
                         "body": f"O membro {request.user.full_name} adicionou a referência {request.data['name']}"
                         }
    members = expense_groups.get_members(group, request, exclude_current_user=True)
    expense_groups.notify_members(members, notification_data)


def notify_members_about_regarding_update(request, regarding):
    notification_data = {"title": "Referência atualizada",
                         "body": f"O membro {request.user.full_name} atualizou a referência {regarding.name}"}
    members = expense_groups.get_members(regarding.expense_group, request, exclude_current_user=True)
    expense_groups.notify_members(members, notification_data)


def update_balance_json(request, regarding):
    if request.data.get("is_closed", False):
        regarding_serializer = RegardingSerializerReader(regarding, context={"request": request})
        totals = regarding_serializer.data
        regarding.balance_json = json.dumps({
            "general_total": totals.get('general_total', {}),
            "consumer_total": totals.get('consumer_total', []),
            "total_by_day": totals.get('total_by_day', {}),
            "total_member_vs_member": totals.get('total_member_vs_member', {}),
        }, default=str)
        regarding.save(update_fields=["balance_json"])


def notify_members_about_regarding_deletion(request, regarding):
    notification_data = {"title": "Referência deletada",
                         "body": f"O membro {request.user.full_name} deletou a referência {regarding.name}. Todas as despesas, items e pagamentos também foram excluídos."}
    members = expense_groups.get_members(regarding.expense_group, request, exclude_current_user=True)
    expense_groups.notify_members(members, notification_data)