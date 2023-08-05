from rest_framework import serializers
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, \
    User, Notification, Validation, ActionLog, Membership, GroupInvitation
from datetime import datetime
from django.db.models import Sum
from core.services import stats
from babel.numbers import format_decimal
from decimal import Decimal
import json


class PaymentMethodSerializer(serializers.ModelSerializer):
    has_payments = serializers.SerializerMethodField()
    number_of_payments = serializers.SerializerMethodField()
    class Meta:
        model = PaymentMethod
        fields = "__all__"

    def get_has_payments(self, obj):
        return obj.payments.count() > 0

    def get_number_of_payments(self, obj):
        return obj.payments.count()


class WalletSerializer(serializers.ModelSerializer):
    payment_methods = PaymentMethodSerializer(read_only=True, many=True)
    class Meta:
        model = Wallet
        fields = ("id", "payment_methods")
        depth = 1


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    wallet = WalletSerializer(read_only=True)
    class Meta:
        model = User
        fields = "__all__"

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"



class MemberSerializer(UserSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "full_name")


class MembershipSerializer(serializers.ModelSerializer):
    user = MemberSerializer(read_only=True)
    class Meta:
        model = Membership
        fields = "__all__"


    def to_representation(self, instance):
        ret = super().to_representation(instance)
        level_index = Membership.Levels.values.index(ret['level'])
        ret['level'] = Membership.Levels.labels[level_index].capitalize()
        return ret


class GroupInvitationSerializer(serializers.ModelSerializer):
    sent_by = MemberSerializer(read_only=True)
    invited = MemberSerializer(read_only=True)
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = GroupInvitation
        fields = "__all__"

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['created_at'] = instance.created_at.strftime("%d/%m/%Y")
        status_index = GroupInvitation.InvitationStatus.values.index(ret['status'])
        ret['status'] = GroupInvitation.InvitationStatus.labels[status_index].capitalize()
        return ret

    def get_group_name(self, obj):
        return obj.expense_group.name


class ExpenseGroupSerializerReader(serializers.ModelSerializer):
    number_of_regardings = serializers.SerializerMethodField()
    number_of_expenses = serializers.SerializerMethodField()
    members = MemberSerializer(many=True, read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)
    invitations = GroupInvitationSerializer(many=True, read_only=True)

    class Meta:
        model = ExpenseGroup
        fields = "__all__"

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['created_at'] = instance.created_at.strftime("%d/%m/%Y")
        return ret

    def get_number_of_regardings(self, obj):
        return obj.regardings.count()

    def get_number_of_expenses(self, obj):
        count = 0
        for regarding in obj.regardings.all():
            count += regarding.expenses.count()
        return count


class ExpenseGroupSerializerWriter(serializers.ModelSerializer):
    class Meta:
        model = ExpenseGroup
        fields = ('name', 'description', 'members')


class RegardingSerializerWriter(serializers.ModelSerializer):
    class Meta:
        model = Regarding
        fields = "__all__"


class RegardingSerializerReader(serializers.ModelSerializer):
    group_name = serializers.SerializerMethodField()
    has_expenses = serializers.SerializerMethodField()
    general_total = serializers.SerializerMethodField()
    consumer_total = serializers.SerializerMethodField()
    personal_total = serializers.SerializerMethodField()
    total_by_day = serializers.SerializerMethodField()
    total_member_vs_member = serializers.SerializerMethodField()

    class Meta:
        model = Regarding
        fields = "__all__"

    def get_group_name(self, obj):
        return obj.expense_group.name

    def get_general_total(self, obj):
        self.user = self.context["request"].user
        if obj.is_closed:
            totals = json.loads(obj.balance_json)
            self.general_total = totals.get('general_total', {})
            self.consumer_total = totals.get('consumer_total', {})
            self.total_by_day = totals.get('total_by_day', {})
            self.total_member_vs_member = totals.get('total_member_vs_member', {})
        else:
            self.general_total = {
                "regarding": obj.id,
                "total_expenses": 0,
                "total_payments": 0,
                "total_validation": 0.0,
                "total_open": 0,
                "total_paid": 0,
                "total_overdue": 0.0
            }
            self.personal_total = {}
            self.consumer_total = {}
            self.total_by_day = {}
            self.total_member_vs_member = {}
            if obj.expenses.count():
                items = ItemSerializerReader(Item.objects.filter(expense__regarding__id=obj.id), many=True).data
                self.general_total, self.consumer_total, self.total_by_day, self.total_member_vs_member = stats.calc_totals_by_regarding(obj.id, items)
        print("dsfds", self.consumer_total)
        user_data = list(filter(lambda x: x["payments__payer"] == self.user.id, self.consumer_total))
        if user_data:
            self.personal_total = user_data[0]
        return self.general_total

    def get_consumer_total(self, obj):
        return list(self.consumer_total)

    def get_personal_total(self, obj):
        if not self.has_expenses:
            return {
                "payments__payer": self.user.id,
                "total_expenses": 0,
                "total_payments": 0,
                "total_validation": 0,
                "total_open": 0,
                "total_paid": 0,
                "total_overdue": 00,
                "shared": 0,
                "partial_shared": 0,
                "individual": 0,
                "total_paid_shared": 0,
                "balance": 0
            }
        return self.personal_total

    def get_total_by_day(self, obj):
        return self.total_by_day

    def get_total_member_vs_member(self, obj):
        return self.total_member_vs_member

    def get_has_expenses(self, obj):
        self.has_expenses = obj.expenses.count() > 0
        return self.has_expenses

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['start_date'] = instance.start_date.strftime("%d/%m/%Y")
        ret['end_date'] = instance.end_date.strftime("%d/%m/%Y")

        return ret


class PaymentSerializerWriter(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"

class PaymentSerializerReader(serializers.ModelSerializer):
    payer = serializers.SerializerMethodField(read_only=True)
    payer_name = serializers.SerializerMethodField()
    class Meta:
        model = Payment
        fields = "__all__"
        depth = 1

    def get_payer_name(self, obj):
        return f"{obj.payer.first_name} {obj.payer.last_name}"

    def get_payer(self, obj):
        return {"id":obj.payer.id, "name": self.get_payer_name(obj)}

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['value'] = format_decimal(instance.value, locale="pt_BR", format="#.###,00")
        return ret


class ItemSerializerForExpense(serializers.ModelSerializer):
    consumers_names = serializers.SerializerMethodField()
    consumers = serializers.SerializerMethodField()
    class Meta:
        model = Item
        fields = ["id", "name", "price", "expense", "consumers_names", "consumers", "created_at"]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['price'] = format_decimal(instance.price, locale="pt_BR", format="#.###,00")
        return ret

    def get_consumers_names(self, obj):
        names = ''
        for consumer in obj.consumers.all():
            names += consumer.first_name
            if consumer.last_name:
                names += " " + consumer.last_name
            names += ', '
        return names[:-2]

    def get_consumers(self, obj):
        data = []
        for consumer in obj.consumers.all():
            data.append({"id": consumer.id, "name": consumer.first_name + " " + consumer.last_name})
        return data

class ExpenseSerializerWriter(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ("name", "description", "regarding", "cost", "date", "created_by")

class ValidationSerializerReader(serializers.ModelSerializer):
    requested_by = serializers.SerializerMethodField()
    is_validated = serializers.SerializerMethodField()
    validator = UserSerializer()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Validation
        fields = "__all__"
        depth = 1

    def get_requested_by(self, obj):
        creator = obj.expense.created_by
        return creator.first_name + ' ' + creator.last_name

    def get_is_validated(self, obj):
        if obj.validated_at:
            return True
        return False

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['created_at'] = instance.created_at.strftime("%d/%m/%Y")
        return ret

    def get_status(self, obj):
        if obj.is_active:
            return "AGUARDANDO"
        elif self.get_is_validated(obj):
            return "VALIDOU"
        else:
            return "REJEITOU"


class ValidationSerializerWriter(serializers.ModelSerializer):
    class Meta:
        model = Validation
        fields = "__all__"

class ExpenseSerializerReader(serializers.ModelSerializer):
    payments = PaymentSerializerReader(many=True)
    items = ItemSerializerForExpense(many=True)
    regarding_name = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    shared_total = serializers.SerializerMethodField()
    individual_total = serializers.SerializerMethodField()
    validations = ValidationSerializerReader(many=True)
    validation_status = serializers.SerializerMethodField()
    regarding_is_closed = serializers.SerializerMethodField()
    expense_group = serializers.SerializerMethodField()
    class Meta:
        model = Expense
        fields = "__all__"

    def get_regarding_name(self, obj):
        return obj.regarding.name

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['cost'] = format_decimal(instance.cost, locale="pt_BR", format="#.###,00")
        ret['date'] = instance.date.strftime("%d/%m/%Y")
        return ret

    def get_payment_status(self, obj):
        payments_statuses = list(obj.payments.values_list("payment_status", flat=True))
        if "VALIDATION" in payments_statuses:
            return "Em validação"
        elif "AWAITING" in payments_statuses:
            return "Aguardando"
        elif "OVERDUE" in payments_statuses:
            return "Vencido"
        elif "PAID" in payments_statuses:
            return "Pago"

    def get_validation_status(self, obj):
        if obj.validation_status == Expense.ValidationStatuses.AWAITING:
            return "Pendente"
        elif obj.validation_status == Expense.ValidationStatuses.VALIDATED:
            return "Validada"
        elif obj.validation_status == Expense.ValidationStatuses.REJECTED:
            return "Rejeitada"

    def get_shared_total(self, obj):  # Bug no individual
        items = ItemSerializerReader(obj.items.all(), many=True).data
        individual = 0
        shared = 0
        members = obj.regarding.expense_group.members.all()
        members_ids = list(members.values_list("id", flat=True))
        for item in items:
            if set(item["consumers"]) == set(members_ids):
                shared += Decimal(item["price"])
            elif len(item["consumers"]) == 1 and item["consumers"][0] == self.context["request"].user.id:
                individual += Decimal(item["price"])
        self.shared = shared
        self.individual = individual
        return self.shared

    def get_individual_total(self, obj):
        return self.individual

    def get_regarding_is_closed(self, obj):
        return obj.regarding.is_closed

    def get_expense_group(self, obj):
        return obj.regarding.expense_group.id


class ExpenseSerializerForItem(serializers.ModelSerializer):
    payments = PaymentSerializerReader(many=True)
    class Meta:
        model = Expense
        fields = "__all__"


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"


class ItemSerializerReader(serializers.ModelSerializer):
    expense = ExpenseSerializerForItem()
    class Meta:
        model = Item
        fields = "__all__"


class ItemSerializerWriter(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['created_at'] = instance.created_at.strftime("%d/%m/%Y")
        return ret


class ActionLogSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    class Meta:
        model = ActionLog
        fields = "__all__"

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['created_at'] = instance.created_at.strftime("%d/%m/%Y %H:%M")
        ret['expense_group'] = instance.expense_group.name
        return ret
