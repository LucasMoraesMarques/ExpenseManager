from core.models import GroupInvitation, Notification, ActionLog, User, Membership
from core.services import push_notifications, expense_groups
from core.serializers import UserSerializer
from babel.numbers import format_currency

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


def update_validation(request, validation):
    msg = f"Está tudo certo com a despesa {validation.expense.name}"
    f"{request.user.full_name} validou uma despesa"
    if not validation.validated_at:
        msg = f"A despesa {validation.expense.name} foi rejeitada." + f"O motivo da rejeição foi {validation.note}" if validation.note else ""
    ActionLog.objects.create(user=request.user, expense_group_id=validation.expense.regarding.expense_group.id,
                             type=ActionLog.ActionTypes.UPDATE,
                             description=msg)


def update_invitation(request, invitation):
    if invitation.status == GroupInvitation.InvitationStatus.ACCEPTED:
        ActionLog.objects.create(user=request.user, expense_group=invitation.expense_group,
                                 type=ActionLog.ActionTypes.UPDATE,
                                 description=f"{invitation.invited.full_name} aceitou o convite de {invitation.sent_by.full_name}",
                                 changes_json={}
                                 )


def batch_delete_expense(request, delete_by_groups):
    log_description = 'Deletou várias despesas'
    for group, deleted_expenses in delete_by_groups.items():
        changes = {"despesas": deleted_expenses}
        ActionLog.objects.create(user=request.user, expense_group_id=group, type=ActionLog.ActionTypes.DELETE,
                                 description=log_description, changes_json=changes)


def delete_expense(request, expense):
    ActionLog.objects.create(user=request.user, expense_group_id=expense.regarding.expense_group.id,
                             type=ActionLog.ActionTypes.DELETE,
                             description=f"Deletou a despesa {expense.name} de valor R$ {format_currency(expense.cost, 'BRL', '#,##0.00', locale='pt_BR')}")


def new_expense(request, expense):
    ActionLog.objects.create(user=request.user, expense_group_id=expense.regarding.expense_group.id,
                             type=ActionLog.ActionTypes.CREATE,
                             description=f"Criou a despesa {expense.name} de valor R$ {format_currency(expense.cost, 'BRL', '#,##0.00', locale='pt_BR')}")


def update_expense(request, expense, deleted_items=[], deleted_payments=[]):
    changes = {'nome': [], "descrição": [], "valor": [], "data": [], "items": [], "pagamentos": []}
    items_to_create = list(filter(lambda x: x.get("create", False), request.data.get("items")))
    items_to_update = list(filter(lambda x: x.get("edited", False), request.data.get("items")))
    payments_to_create = list(filter(lambda x: x.get("create", False), request.data.get("payments")))
    payments_to_update = list(filter(lambda x: x.get("edited", False), request.data.get("payments")))
    for field in request.data.keys():
        if field == 'name':
            if (old := getattr(expense, field)) != (new := request.data.get(field)):
                changes["nome"].append(f"Mudou o nome de {old} para {new}")
        elif field == 'description':
            print(getattr(expense, field), request.data.get(field))
            if (old := getattr(expense, field)) != (new := request.data.get(field)):
                changes["descrição"].append(f"Mudou a descrição de {old} para {new}")
        elif field == "cost":
            old = format_currency(getattr(expense, field), 'BRL', '#,##0.00', locale='pt_BR')
            new = format_currency(float(request.data.get(field)), 'BRL', '#,##0.00',
                                  locale='pt_BR')
            if old != new:
                changes["valor"].append(f"Mudou o valor de R$ {old} para R$ {new}")
        elif field == 'date':
            if (old := str(getattr(expense, field))) != (new := request.data.get(field)):
                changes["data"].append(f"Mudou a data de '{old[8:10]}/{old[5:7]}/{old[:4]}' para '{new[8:10]}/{new[5:7]}/{new[:4]}'")
        elif field == 'items':
            for item in items_to_create:
                changes["items"].append(f"Criou o item {item.get('name')} R${format_currency(item.get('price'), 'BRL', '#,##0.00', locale='pt_BR')}")
            for item in items_to_update:
                changes["items"].append(f"Atualizou o item {item.get('name')} R${format_currency(item.get('price'), 'BRL', '#,##0.00', locale='pt_BR')}")
            for item in deleted_items:
                changes["items"].append(f"Deletou o item {item.get('name')} R${format_currency(item.get('price'), 'BRL', '#,##0.00', locale='pt_BR')}")
        elif field == 'payments':
            for payment in payments_to_create:
                changes["pagamentos"].append(f"Criou o pagamento {payment['payer_name']} R${format_currency(payment['value'], 'BRL', '#,##0.00', locale='pt_BR')}")
            for payment in payments_to_update:
                changes["pagamentos"].append(f"Atualizou o pagamento {payment['payer_name']} R${format_currency(payment['value'], 'BRL', '#,##0.00', locale='pt_BR')}")
            for payment in deleted_payments:
                changes["pagamentos"].append(f"Deletou o pagamento {payment['payer__first_name']} R${format_currency(payment['value'], 'BRL', '#,##0.00', locale='pt_BR')}")

    ActionLog.objects.create(user=request.user, expense_group_id=expense.regarding.expense_group.id,
                             type=ActionLog.ActionTypes.UPDATE,
                             description=f"Atualizou a despesa {expense.name}", changes_json=changes)
    print(changes)
