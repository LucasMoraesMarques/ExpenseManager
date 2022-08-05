from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import datetime


class User(AbstractUser):
    pass


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ExpenseGroup(BaseModel):
    name = models.CharField("Name", max_length=128)
    description = models.TextField("Description", null=True, blank=True)
    members = models.ManyToManyField("User", related_name="expenses_groups")
    is_active = models.BooleanField("Is active?", default=True)


class Regarding(BaseModel):
    name = models.CharField("Name", max_length=128)
    description = models.TextField("Description", null=True, blank=True)
    start_date = models.DateField("Start Date", default=datetime.today().date())
    end_date = models.DateField("End Date", null=True)
    expense_group = models.ForeignKey("ExpenseGroup", related_name="regardings", on_delete=models.PROTECT)
    is_closed = models.BooleanField("Is closed?", default=False)
    balance_json = models.JSONField("Balance Data", default=dict, null=True)


class Wallet(BaseModel):
    owner = models.OneToOneField("User", related_name="wallet", on_delete=models.PROTECT)


class PaymentMethod(BaseModel):
    class Types(models.TextChoices):
        DEBIT_CARD = ("DEBIT", "CARTÃO DE DÉBITO")
        CREDIT_CARD = ("CREDIT", "CARTÃO DE CRÉDITO")
        CASH = ("CASH", "DINHEIRO")
    type = models.TextField("Payment Type", choices=Types.choices)
    description = models.TextField("Description", null=True, blank=True)
    wallet = models.ForeignKey("Wallet", related_name="payment_methods", on_delete=models.PROTECT)
    limit = models.DecimalField("Payment Limit Value", null=True, max_digits=14, decimal_places=4)
    compensation_date = models.DateField("Payment Due Date", default=datetime.today().date())
    is_active = models.BooleanField("Payment Method is active?", default=True)


class Payment(BaseModel):
    class PaymentStatuses(models.TextChoices):
        AWAITING_VALIDATION = ("VALIDATION", "EM VALIDAÇÃO")
        AWAITING_PAYMENT = ("AWAITING", "AGUARDANDO PAGAMENTO")
        PAID = ("PAID", "PAGO")
        OVERDUE = ("OVERDUE", "VENCIDO")
    payer = models.ForeignKey("User", related_name="paid_expenses", on_delete=models.PROTECT)
    payment_method = models.ForeignKey("PaymentMethod", related_name="payments", on_delete=models.PROTECT)
    value = models.DecimalField("Payment Value", max_digits=14, decimal_places=4)
    expense = models.ForeignKey("Expense", related_name="payments", on_delete=models.PROTECT)
    payment_status = models.CharField("Payment Status", default=PaymentStatuses.AWAITING_VALIDATION, max_length=128, choices=PaymentStatuses.choices)


class Expense(BaseModel):
    name = models.CharField("Name", max_length=128)
    description = models.TextField("Description", null=True, blank=True)
    regarding = models.ForeignKey("Regarding", related_name="expenses", on_delete=models.PROTECT)
    date = models.DateField("Expense Date", default=datetime.today().date())
    cost = models.DecimalField("Expense Cost", max_digits=14, decimal_places=4)
    validated_by = models.ManyToManyField("User", related_name="validated_expenses")
    is_validated = models.BooleanField("Is validated?", default=False)


class Tag(BaseModel):
    owner = models.ForeignKey("User", related_name="created_tags", on_delete=models.PROTECT)
    expenses_groups = models.ManyToManyField("ExpenseGroup", related_name="items_tags")


class Item(BaseModel):
    name = models.CharField("Name", max_length=128)
    tags = models.ForeignKey("Tag", related_name="items", on_delete=models.PROTECT)
    price = models.DecimalField("Price", max_digits=14, decimal_places=4)
    expense = models.ForeignKey("Expense", related_name="items", on_delete=models.PROTECT)
    consumers = models.ManyToManyField("User", related_name="items_purchased")



