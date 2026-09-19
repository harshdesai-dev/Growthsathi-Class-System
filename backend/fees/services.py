from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import StudentRegistration
from academics.scopes import require_admin
from audit.models import AuditLog

from .models import FeeInstallment, FeePayment, PaymentAllocation, Receipt, StudentFeeAccount


def total_paid(account):
    return account.payments.filter(reversed_at=None).aggregate(value=Sum("amount"))[
        "value"
    ] or Decimal("0.00")


def installment_paid(installment):
    return installment.allocations.filter(payment__reversed_at=None).aggregate(value=Sum("amount"))[
        "value"
    ] or Decimal("0.00")


@transaction.atomic
def create_account(actor, values):
    require_admin(actor)
    registration = get_object_or_404(
        StudentRegistration, pk=values["registration"], institute_id=actor.institute_id
    )
    if sum(row["amount"] for row in values["installments"]) != values["total_fee"]:
        raise ValidationError("Installments must add up to the total fee.")
    account = StudentFeeAccount.objects.create(
        institute_id=actor.institute_id,
        registration=registration,
        title=values["title"],
        total_fee=values["total_fee"],
    )
    for installment in values["installments"]:
        FeeInstallment.objects.create(
            institute_id=actor.institute_id, account=account, **installment
        )
    AuditLog.objects.create(
        institute_id=actor.institute_id,
        actor=actor,
        action="fee-plan-create",
        entity="StudentFeeAccount",
        entity_id=str(account.pk),
    )
    return account


@transaction.atomic
def record_payment(actor, account_id, values):
    require_admin(actor)
    account = get_object_or_404(
        StudentFeeAccount.objects.select_for_update(),
        pk=account_id,
        institute_id=actor.institute_id,
    )
    previous = FeePayment.objects.filter(
        institute_id=actor.institute_id, idempotency_key=values["idempotency_key"]
    ).first()
    if previous:
        if previous.account_id != account.pk or any(
            getattr(previous, k) != values.get(k, "")
            for k in ["amount", "method", "paid_on", "reference"]
        ):
            raise ValidationError(
                "This payment request key has already been used for different details."
            )
        return previous
    if values["paid_on"] > timezone.localdate():
        raise ValidationError("Payment date cannot be in the future.")
    if values["amount"] <= 0 or values["amount"] > account.total_fee - total_paid(account):
        raise ValidationError("Payment must be positive and cannot exceed the remaining balance.")
    payment = FeePayment.objects.create(
        institute_id=actor.institute_id, account=account, recorded_by=actor, **values
    )
    remaining = payment.amount
    for installment in account.installments.all():
        allocated = min(remaining, installment.amount - installment_paid(installment))
        if allocated > 0:
            PaymentAllocation.objects.create(
                institute_id=actor.institute_id,
                payment=payment,
                installment=installment,
                amount=allocated,
            )
            remaining -= allocated
    if remaining:
        raise ValidationError("Installment plan does not match the fee account.")
    Receipt.objects.create(
        institute_id=actor.institute_id,
        payment=payment,
        number=f"GS-{actor.institute_id}-{payment.pk:08d}",
    )
    AuditLog.objects.create(
        institute_id=actor.institute_id,
        actor=actor,
        action="payment-record",
        entity="FeePayment",
        entity_id=str(payment.pk),
        summary={"amount": str(payment.amount)},
    )
    from notifications.services import student_event

    student_event(account.registration.student, "fees", account.pk)
    return payment


@transaction.atomic
def reverse_payment(actor, payment_id, reason):
    require_admin(actor)
    payment = get_object_or_404(FeePayment, pk=payment_id, institute_id=actor.institute_id)
    StudentFeeAccount.objects.select_for_update().get(pk=payment.account_id)
    payment.refresh_from_db()
    if not payment.reversed_at:
        payment.reversed_at = timezone.now()
        payment.reversal_reason = reason
        payment.save(update_fields=["reversed_at", "reversal_reason"])
        AuditLog.objects.create(
            institute_id=actor.institute_id,
            actor=actor,
            action="payment-reverse",
            entity="FeePayment",
            entity_id=str(payment.pk),
            summary={"reason": reason},
        )
    return payment


@transaction.atomic
def revise_account(actor, account_id, values):
    require_admin(actor)
    account = get_object_or_404(
        StudentFeeAccount.objects.select_for_update(),
        pk=account_id,
        institute_id=actor.institute_id,
    )
    if account.payments.exists():
        raise ValidationError("Plans with payments are locked. Use reversals to correct payments.")
    if sum(row["amount"] for row in values["installments"]) != values["total_fee"]:
        raise ValidationError("Installments must add up to the total fee.")
    before = {
        "total_fee": str(account.total_fee),
        "installments": [
            {"amount": str(i.amount), "due_date": str(i.due_date)}
            for i in account.installments.all()
        ],
    }
    account.total_fee = values["total_fee"]
    account.title = values["title"]
    account.save()
    # No payment/allocation references exist; replace only this unused draft plan.
    account.installments.all().delete()
    for row in values["installments"]:
        FeeInstallment.objects.create(institute_id=actor.institute_id, account=account, **row)
    AuditLog.objects.create(
        institute_id=actor.institute_id,
        actor=actor,
        action="fee-plan-revise",
        entity="StudentFeeAccount",
        entity_id=str(account.pk),
        summary={"before": before, "total_fee": str(account.total_fee)},
    )
    return account
