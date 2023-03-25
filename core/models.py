from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import datetime
import hashlib
from phonenumber_field.modelfields import PhoneNumberField

STATES = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA',
    'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']

STATES_CHOICES = [(state, state) for state in STATES]

class User(AbstractUser):
    phone = PhoneNumberField('Phone Number', null=True, blank=True)
    street = models.CharField("Street", max_length=128, null=True, blank=True)
    district = models.CharField("District", max_length=128, null=True, blank=True)
    address_number = models.IntegerField("Number", null=True, blank=True)
    zip_code = models.CharField("Zip Code", max_length=8, blank=True)
    city = models.CharField("City", max_length=128, null=True, blank=True)
    state = models.CharField("State", max_length=2, null=True, choices=STATES_CHOICES, blank=True)
    fcm_token = models.CharField("Firebase Token", max_length=255, blank=True, null=True)
    google_id = models.CharField("Google Account Id", max_length=128, null=True, blank=True)


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
    hash_id = models.CharField("Hash ID", max_length=16, blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.hash_id:
            self.hash_id = hashlib.sha1(bytes(f"{self.name}-{self.description}-{self.pk}", encoding="utf-8")).hexdigest()[:16]
        super(ExpenseGroup, self).save(*args, **kwargs)



class Regarding(BaseModel):
    name = models.CharField("Name", max_length=128)
    description = models.TextField("Description", null=True, blank=True)
    start_date = models.DateField("Start Date", default=datetime.today().date())
    end_date = models.DateField("End Date", null=True)
    expense_group = models.ForeignKey("ExpenseGroup", related_name="regardings", on_delete=models.PROTECT)
    is_closed = models.BooleanField("Is closed?", default=False)
    balance_json = models.JSONField("Balance Data", default=dict, null=True)

    def __str__(self):
        return f"{self.expense_group.name} - {self.name} - ({self.description})"


class Wallet(BaseModel):
    owner = models.OneToOneField("User", related_name="wallet", on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.owner}"


class PaymentMethod(BaseModel):
    class Types(models.TextChoices):
        DEBIT_CARD = ("DEBIT", "CARTÃO DE DÉBITO")
        CREDIT_CARD = ("CREDIT", "CARTÃO DE CRÉDITO")
        CASH = ("CASH", "DINHEIRO")
    type = models.TextField("Payment Type", choices=Types.choices)
    description = models.TextField("Description", null=True, blank=True)
    wallet = models.ForeignKey("Wallet", related_name="payment_methods", on_delete=models.PROTECT)
    limit = models.DecimalField("Payment Limit Value", null=True, max_digits=14, decimal_places=4, blank=True)
    compensation_day = models.IntegerField("Payment Compensation Day", null=True, blank=True)
    is_active = models.BooleanField("Payment Method is active?", default=True)

    def __str__(self):
        return f"{self.wallet} {self.type} - {self.description}"


class Payment(BaseModel):
    class PaymentStatuses(models.TextChoices):
        AWAITING_VALIDATION = ("VALIDATION", "EM VALIDAÇÃO")
        AWAITING_PAYMENT = ("AWAITING", "AGUARDANDO PAGAMENTO")
        PAID = ("PAID", "PAGO")
        OVERDUE = ("OVERDUE", "VENCIDO")
    payer = models.ForeignKey("User", related_name="paid_expenses", on_delete=models.PROTECT)
    payment_method = models.ForeignKey("PaymentMethod", related_name="payments", on_delete=models.PROTECT)
    value = models.DecimalField("Payment Value", max_digits=14, decimal_places=4)
    expense = models.ForeignKey("Expense", related_name="payments", on_delete=models.PROTECT, null=True, blank=True)
    payment_status = models.CharField("Payment Status", default=PaymentStatuses.AWAITING_VALIDATION, max_length=128, choices=PaymentStatuses.choices)

    def __str__(self):
        return f"{self.expense.regarding.expense_group} - {self.expense.regarding.name} - {self.expense.name} - R${self.value} - {self.payer}"


class Expense(BaseModel):
    name = models.CharField("Name", max_length=128)
    description = models.TextField("Description", null=True, blank=True)
    regarding = models.ForeignKey("Regarding", related_name="expenses", on_delete=models.PROTECT)
    date = models.DateField("Expense Date", default=datetime.today().date())
    cost = models.DecimalField("Expense Cost", max_digits=14, decimal_places=4)
    validated_by = models.ManyToManyField("User", through="Validation", blank=True, null=True)
    is_validated = models.BooleanField("Is validated?", default=False)
    created_by = models.ForeignKey("User", related_name="created_expenses", on_delete=models.PROTECT, blank=True, null=True)

    def __str__(self):
        return f"{self.regarding.expense_group} - {self.regarding.name} - {self.name} - R${self.cost:.2f}"


class Tag(BaseModel):
    name = models.CharField("Tag", max_length=128, default="Outros")
    owner = models.ForeignKey("User", related_name="created_tags", on_delete=models.PROTECT)
    expenses_groups = models.ManyToManyField("ExpenseGroup", related_name="items_tags")

    def __str__(self):
        return self.name


class Item(BaseModel):
    name = models.CharField("Name", max_length=128)
    tags = models.ForeignKey("Tag", related_name="items", on_delete=models.CASCADE, null=True, blank=True)
    price = models.DecimalField("Price", max_digits=14, decimal_places=4)
    expense = models.ForeignKey("Expense", related_name="items", on_delete=models.CASCADE, null=True, blank=True)
    consumers = models.ManyToManyField("User", related_name="items_purchased")

    def __str__(self):
        return f"{self.expense.regarding} - {self.expense.name} - {self.name} - R${self.price:.2f}"


class Notification(BaseModel):
    title = models.CharField("Notification Title", max_length=128)
    body = models.TextField("Notification Body")
    payload = models.JSONField("Notification Payload", null=True)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="notifications")
    was_sent = models.BooleanField("Notification sent?", default=False)
    is_active = models.BooleanField("Is active?", default=True)

class Validation(BaseModel):
    validator = models.ForeignKey("User", on_delete=models.CASCADE, related_name="requested_validations")
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="validations")
    validated_at = models.DateField("Validation Date", null=True, blank=True)
