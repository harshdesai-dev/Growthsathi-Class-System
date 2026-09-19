from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from institutes.models import TenantModel


class StudentFeeAccount(TenantModel):
    registration = models.ForeignKey("academics.StudentRegistration", on_delete=models.PROTECT)
    title = models.CharField(max_length=120)
    total_fee = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(total_fee__gte=0), name="fee_nonnegative")
        ]


class FeeInstallment(TenantModel):
    account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.PROTECT, related_name="installments"
    )
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["due_date", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="installment_nonnegative"
            )
        ]


class FeePayment(TenantModel):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        BANK = "BANK", "Bank transfer"

    account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=12, choices=Method.choices)
    paid_on = models.DateField()
    reference = models.CharField(max_length=120, blank=True)
    idempotency_key = models.UUIDField()
    recorded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_positive"),
            models.UniqueConstraint(
                fields=["institute", "idempotency_key"], name="payment_idempotency_unique"
            ),
        ]


class PaymentAllocation(TenantModel):
    def clean(self):
        super().clean()
        if (
            self.payment_id
            and self.installment_id
            and self.payment.account_id != self.installment.account_id
        ):
            raise ValidationError({"installment": "Allocation must belong to the payment account."})

    payment = models.ForeignKey(FeePayment, on_delete=models.PROTECT, related_name="allocations")
    installment = models.ForeignKey(
        FeeInstallment, on_delete=models.PROTECT, related_name="allocations"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="allocation_positive")
        ]


class Receipt(TenantModel):
    payment = models.OneToOneField(FeePayment, on_delete=models.PROTECT, related_name="receipt")
    number = models.CharField(max_length=80)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["institute", "number"], name="receipt_number_unique")
        ]
