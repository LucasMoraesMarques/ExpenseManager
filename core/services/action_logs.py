from core.models import GroupInvitation, Notification, ActionLog, User, Membership
from core.services import push_notifications, expense_groups
from core.serializers import UserSerializer


FIELDS_NAMES_PT = {
    'start_date': 'data inicial',
    'end_date': 'data final',
    'is_closed': 'status',
    'date': 'data',
    'cost': 'custo',
    'payments': 'pagamentos',
    'members': 'membros',
    'invitations': 'convites'
}


def new_group(request, group):
    changes = {"convites": []}
    invitations = request.data.get("invitations", [])
    for invitation in invitations:
        changes["convites"].append(f"Convidou o usuário {invitation['invited']['full_name']}")

    ActionLog.objects.create(user=request.user, expense_group_id=group.id,
                             type=ActionLog.ActionTypes.CREATE,
                             description=f"Criou o grupo {group.name}", changes_json=changes)


def update_group(request, group, removed_members, invitations):
    changes = {'nome': [], "descrição": [], "membros": [], "convites": []}
    for field in request.data.keys():
        if field == 'name':
            if (old := getattr(group, field)) != (new := request.data.get(field)):
                changes["nome"].append(f"Mudou o nome de {old} para {new}")
        elif field == 'description':
            if (old := getattr(group, field)) != (new := request.data.get(field)):
                changes["nome"].append(f"Mudou a descrição de {old} para {new}")
        elif field == 'members':
            for member in removed_members:
                changes["members"].append(f"Removeu o membro {member['full_name']}.")
        elif field == "memberships":
            for membership_data in request.data.get("memberships", []):
                if membership_data.get('updated', False):
                    membership = group.memberships.get(id=membership_data.get('id'))
                    old_level_index = Membership.Levels.values.index(membership.level)
                    old_level = Membership.Levels.labels[old_level_index]
                    changes["membros"].append(f"Mudou o membro {membership.user.full_name} de {old_level} para {membership_data.get('level').upper()}")
        elif field == "invitations":
            for invitation in invitations:
                changes["convites"].append(f"Convidou o usuário {invitation.invited.full_name}")
    ActionLog.objects.create(user=request.user, expense_group_id=group.id,
                             type=ActionLog.ActionTypes.UPDATE,
                             description=f"Atualizou o grupo {group.name}",
                             changes_json=changes)


def new_regarding(request):
    ActionLog.objects.create(user=request.user, expense_group_id=request.data['expense_group'],
                             type=ActionLog.ActionTypes.CREATE,
                             description=f"Criou a referência {request.data['name']}")


def update_regarding(request, regarding):
    changes = {"nome": [], "description": [], "status": [], "start_date": [], "end_date": []}
    for field in request.data.keys():
        if field == 'name':
            if (old := getattr(regarding, field)) != (new := request.data.get(field)):
                changes["nome"].append(f"Mudou o nome de {old} para {new}")
        elif field == 'description':
            if (old := getattr(regarding, field)) != (new := request.data.get(field)):
                changes["nome"].append(f"Mudou a descrição de {old} para {new}")
        elif field in ['start_date', 'end_date']:
            field_name = "início" if field == "start_date" else "fim"
            if (old := str(getattr(regarding, field))) != (new := request.data.get(field)):
                changes[field_name].append(f"Mudou o {field_name} de {old[8:10]}/{old[5:7]}/{old[:4]} para {new[8:10]}/{new[5:7]}/{new[:4]}")
        elif field == 'is_closed':
            if (old := getattr(regarding, field)) != (new := request.data.get(field)):
                old = 'finalizada' if old else 'em andamento'
                new = 'finalizada' if new else 'em andamento'
                changes["status"].append(f"Mudou o status de '{old}' para '{new}'")
    ActionLog.objects.create(user=request.user, expense_group_id=regarding.expense_group.id,
                             type=ActionLog.ActionTypes.UPDATE,
                             description=f"Atualizou a referência {regarding.name}",
                             changes_json=changes)


def regarding_deletion(request, regarding):
    ActionLog.objects.create(user=request.user, expense_group_id=regarding.expense_group.id,
                             type=ActionLog.ActionTypes.DELETE,
                             description=f"Deletou a referência {regarding.name}")
