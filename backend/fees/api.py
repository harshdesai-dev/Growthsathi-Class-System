from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import format_html
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from academics.scopes import students_for
from accounts.models import Role
from accounts.permissions import ActiveTenantUser

from .models import FeePayment, StudentFeeAccount
from .services import create_account, installment_paid, record_payment, reverse_payment, total_paid


class AccountInput(serializers.Serializer):
    class Installment(serializers.Serializer):
        due_date = serializers.DateField()
        amount = serializers.DecimalField(
            max_digits=12, decimal_places=2, min_value=Decimal("0.01")
        )

    registration = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=120)
    total_fee = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    installments = Installment(many=True, allow_empty=False)


class PaymentInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=FeePayment.Method.choices)
    paid_on = serializers.DateField()
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    idempotency_key = serializers.UUIDField()


class PaymentSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source="receipt.number")

    class Meta:
        model = FeePayment
        fields = [
            "id",
            "amount",
            "method",
            "paid_on",
            "reference",
            "receipt_number",
            "reversed_at",
            "reversal_reason",
        ]


class AccountSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="registration.student.user.full_name")
    student = serializers.IntegerField(source="registration.student_id")
    paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    installments = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True)
    next_due_date = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    def get_next_due_date(self, account):
        dates = [i.due_date for i in account.installments.all() if installment_paid(i) < i.amount]
        return min(dates) if dates else None

    def get_payment_status(self, account):
        due = self.get_next_due_date(account)
        return "PAID" if due is None else "OVERDUE" if due < timezone.localdate() else "PENDING"

    def get_paid(self, account):
        return str(total_paid(account))

    def get_balance(self, account):
        return str(account.total_fee - total_paid(account))

    def get_installments(self, account):
        result = []
        for installment in account.installments.all():
            paid = installment_paid(installment)
            result.append(
                {
                    "id": installment.pk,
                    "due_date": installment.due_date,
                    "amount": str(installment.amount),
                    "paid": str(paid),
                    "pending": str(installment.amount - paid),
                    "status": "PAID"
                    if paid == installment.amount
                    else "OVERDUE"
                    if installment.due_date < timezone.localdate()
                    else "PENDING",
                }
            )
        return result

    class Meta:
        model = StudentFeeAccount
        fields = [
            "id",
            "registration",
            "student",
            "student_name",
            "title",
            "total_fee",
            "paid",
            "balance",
            "installments",
            "payments",
            "next_due_date",
            "payment_status",
        ]


class FeeViewSet(viewsets.ReadOnlyModelViewSet):
    module_filters = {
        "batch": ("registration__student__enrollments__batch_id", "id"),
        "class": ("registration__student__enrollments__batch__academic_class_id", "id"),
    }
    filter_constraints = {
        "class": {"registration__student__enrollments__ended_at": None},
        "batch": {"registration__student__enrollments__ended_at": None},
    }
    search_fields = ["registration__student__user__full_name", "title"]
    permission_classes = [ActiveTenantUser]
    serializer_class = AccountSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.role not in (Role.ADMIN, Role.STUDENT, Role.PARENT):
            raise PermissionDenied("Fee access unavailable.")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        accounts = self.filter_queryset(self.get_queryset())
        expected = paid = overdue = Decimal("0")
        for account in accounts:
            expected += account.total_fee
            paid += total_paid(account)
            overdue += sum(
                (
                    i.amount - installment_paid(i)
                    for i in account.installments.all()
                    if i.due_date < timezone.localdate()
                ),
                Decimal("0"),
            )
        return Response(
            {
                "Expected fees": str(expected),
                "Collected": str(paid),
                "Pending": str(expected - paid),
                "Overdue": str(overdue),
            }
        )

    @action(detail=False, methods=["get"])
    def report(self, request):
        from academics.scopes import require_admin
        from common.reports import csv_report

        require_admin(request.user)
        accounts = self.filter_queryset(self.get_queryset())
        return csv_report(
            "fee-summary",
            ["Student", "Plan", "Expected", "Collected", "Pending"],
            (
                (
                    a.registration.student.user.full_name,
                    a.title,
                    a.total_fee,
                    total_paid(a),
                    a.total_fee - total_paid(a),
                )
                for a in accounts
            ),
        )

    @action(detail=True, methods=["post"])
    def remind(self, request, pk=None):
        from academics.scopes import require_admin
        from audit.models import AuditLog
        from notifications.services import student_event

        require_admin(request.user)
        account = self.get_object()
        student_event(account.registration.student, "fees", account.pk)
        AuditLog.objects.create(
            institute_id=request.user.institute_id,
            actor=request.user,
            action="fee-reminder",
            entity="StudentFeeAccount",
            entity_id=str(account.pk),
        )
        return Response(
            {"detail": "Reminder added to the student and linked-parent notification feed."}
        )

    def get_queryset(self):
        user = self.request.user
        qs = StudentFeeAccount.objects.filter(institute_id=user.institute_id)
        if user.role != Role.ADMIN:
            qs = qs.filter(registration__student__in=students_for(user))
        if "student" in self.request.query_params:
            qs = qs.filter(
                registration__student_id=serializers.IntegerField(min_value=1).run_validation(
                    self.request.query_params["student"]
                )
            )
        return qs.select_related("registration__student__user").order_by("pk")

    def create(self, request):
        data = AccountInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(
            self.get_serializer(create_account(request.user, data.validated_data)).data, status=201
        )

    def partial_update(self, request, pk=None):
        from .services import revise_account

        account = self.get_object()
        data = AccountInput(data={**request.data, "registration": account.registration_id})
        data.is_valid(raise_exception=True)
        return Response(
            self.get_serializer(revise_account(request.user, account.pk, data.validated_data)).data
        )

    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        account = self.get_object()
        data = PaymentInput(data=request.data)
        data.is_valid(raise_exception=True)
        payment = record_payment(request.user, account.pk, data.validated_data)
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        account = self.get_object()

        class Reversal(serializers.Serializer):
            payment = serializers.IntegerField(min_value=1)
            reason = serializers.CharField(max_length=300)

        data = Reversal(data=request.data)
        data.is_valid(raise_exception=True)
        payment = get_object_or_404(account.payments, pk=data.validated_data["payment"])
        return Response(
            PaymentSerializer(
                reverse_payment(request.user, payment.pk, data.validated_data["reason"])
            ).data
        )

    @action(detail=True, methods=["get"], url_path="receipt/(?P<payment_id>[0-9]+)")
    def receipt(self, request, pk=None, payment_id=None):
        account = self.get_object()
        payment = get_object_or_404(
            account.payments.select_related("receipt", "institute"), pk=payment_id
        )
        html = format_html(
            '<!doctype html><html><head><meta charset="utf-8"><title>Receipt</title></head>'
            "<body><h1>{}</h1><h2>Receipt {}</h2><p>Student: {}</p>"
            "<p>Date: {}</p><p>Amount: INR {}</p>"
            "<p>Method: {}</p><p>Status: {}</p>"
            "<p>Use your browser Print / Save as PDF.</p></body></html>",
            payment.institute.name,
            payment.receipt.number,
            account.registration.student.user.full_name,
            payment.paid_on,
            payment.amount,
            payment.get_method_display(),
            "REVERSED" if payment.reversed_at else "Recorded",
        )
        response = HttpResponse(html)
        response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response
