from rest_framework import serializers
from core.models import ExpenseGroup, Regarding, Wallet, PaymentMethod, Payment, Expense, Tag, Item, \
    User, Notification, Validation, ActionLog
from datetime import datetime
from django.db.models import Sum
from core.services import stats
from babel.numbers import format_decimal
from decimal import Decimal


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("payment_methods",)
        depth = 1


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    wallet = WalletSerializer(read_only=True)
    class Meta:
        model = User
        fields = "__all__"

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class ExpenseGroupSerializerReader(serializers.ModelSerializer):
    number_of_regardings = serializers.SerializerMethodField()
    number_of_expenses = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseGroup
        fields = "__all__"
        depth = 2

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
    general_total = serializers.SerializerMethodField()
    consumer_total = serializers.SerializerMethodField()
    total_by_day = serializers.SerializerMethodField()
    total_member_vs_member = serializers.SerializerMethodField()

    class Meta:
        model = Regarding
        fields = "__all__"

    def get_group_name(self, obj):
        return obj.expense_group.name

    def get_general_total(self, obj):
        self.total_data = {
            "regarding": obj.id,
            "total_expenses": 0,
            "total_payments": 0,
            "total_validation": 0.0,
            "total_open": 0,
            "total_paid": 0,
            "total_overdue": 0.0
        }
        self.personal_data = {
            "payments__payer": 1,
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
        self.total_by_day = {}
        self.user = self.context["request"].user
        if obj.expenses.count():
            items = ItemSerializerReader(Item.objects.filter(expense__regarding__id=obj.id), many=True).data
            self.total_data, user_data, self.total_by_day, self.total_member_vs_member = stats.calc_totals_by_regarding(obj.id, items)
            user_data = list(filter(lambda x: x["payments__payer"] == 1, user_data))
            if user_data:
                self.personal_data = user_data[0]
        return self.total_data

    def get_consumer_total(self, obj):
        return self.personal_data

    def get_total_by_day(self, obj):
        return self.total_by_day

    def get_total_member_vs_member(self, obj):
        return self.total_member_vs_member

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['start_date'] = instance.start_date.strftime("%d/%m/%Y")
        ret['end_date'] = instance.end_date.strftime("%d/%m/%Y")

        return ret



class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = "__all__"


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
        ret['created_at'] = instance.created_at.strftime("%d/%m/%Y")
        ret['expense_group'] = instance.expense_group.name
        return ret
