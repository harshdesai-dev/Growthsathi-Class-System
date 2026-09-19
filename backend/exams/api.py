from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import format_html
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from academics.models import Enrollment
from academics.scopes import (
    assignments_for,
    batches_for,
    require_admin,
    require_teaching_scope,
    students_for,
)
from accounts.models import Role
from accounts.permissions import ActiveTenantUser
from audit.models import AuditLog
from common.api import AdminResourceViewSet, TenantSerializer

from .models import Exam, ExamScore


def exams_for(user):
    qs = Exam.objects.filter(institute_id=user.institute_id)
    if user.role == Role.TEACHER:
        scope = Q(pk__in=[])
        for pair in assignments_for(user).values("batch_id", "subject_id"):
            scope |= Q(batch_id=pair["batch_id"], subject_id=pair["subject_id"])
        return qs.filter(scope)
    if user.role in (Role.STUDENT, Role.PARENT):
        return qs.filter(
            Q(batch__in=batches_for(user))
            | Q(published_at__isnull=False, scores__enrollment__student__in=students_for(user))
        ).distinct()
    return qs if user.role == Role.ADMIN else qs.none()


def result_values(score):
    if score.is_absent:
        return {"percentage": None, "result": "ABSENT"}
    if score.marks is None:
        return {"percentage": None, "result": "PENDING"}
    return {
        "percentage": str((score.marks * 100 / score.exam.total_marks).quantize(Decimal("0.01"))),
        "result": "PASS" if score.marks >= score.exam.passing_marks else "FAIL",
    }


class ExamSerializer(TenantSerializer):
    batch_name = serializers.CharField(source="batch.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "name",
            "batch",
            "batch_name",
            "subject",
            "subject_name",
            "date",
            "starts_at",
            "total_marks",
            "passing_marks",
            "instructions",
            "is_cancelled",
            "published_at",
        ]
        read_only_fields = ["published_at"]


class ScoreSerializer(serializers.ModelSerializer):
    student = serializers.IntegerField(source="enrollment.student_id")
    student_name = serializers.CharField(source="enrollment.student.user.full_name")
    exam_name = serializers.CharField(source="exam.name")
    batch_name = serializers.CharField(source="enrollment.batch.name")
    subject_name = serializers.CharField(source="exam.subject.name")
    total_marks = serializers.DecimalField(
        source="exam.total_marks", max_digits=7, decimal_places=2
    )
    calculation = serializers.SerializerMethodField()

    def get_calculation(self, score):
        return result_values(score)

    class Meta:
        model = ExamScore
        fields = [
            "id",
            "exam",
            "exam_name",
            "student",
            "student_name",
            "batch_name",
            "subject_name",
            "marks",
            "total_marks",
            "is_absent",
            "remark",
            "calculation",
        ]


class ExamViewSet(AdminResourceViewSet):
    module_filters = {
        "class": ("batch__academic_class_id", "id"),
        "batch": ("batch_id", "id"),
        "subject": ("subject_id", "id"),
        "date_from": ("date__gte", "date"),
        "date_to": ("date__lte", "date"),
        "is_cancelled": ("is_cancelled", "bool"),
    }
    search_fields = ["name", "subject__name"]
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer

    def initial(self, request, *args, **kwargs):
        viewsets.ModelViewSet.initial(self, request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS") and self.action != "marks":
            require_admin(request.user)

    def get_queryset(self):
        qs = exams_for(self.request.user)
        if self.request.query_params.get("student"):
            from academics.scopes import selected_students

            selected = selected_students(self.request)
            qs = qs.filter(
                Q(batch__enrollments__student__in=selected, batch__enrollments__ended_at=None)
                | Q(published_at__isnull=False, scores__enrollment__student__in=selected)
            ).distinct()
        return qs.select_related("batch", "subject").order_by("-date", "pk")

    @transaction.atomic
    def perform_create(self, serializer):
        exam = serializer.save(institute_id=self.request.user.institute_id)
        for enrollment in Enrollment.objects.filter(
            institute_id=exam.institute_id, batch=exam.batch, ended_at=None
        ):
            ExamScore.objects.create(
                institute_id=exam.institute_id, exam=exam, enrollment=enrollment
            )

        from notifications.services import batch_event

        batch_event(exam.batch, "exams", exam.pk, exam.subject)

    @transaction.atomic
    def perform_update(self, serializer):
        exam = Exam.objects.select_for_update().get(pk=serializer.instance.pk)
        if exam.published_at:
            raise ValidationError("Unpublish before changing this exam.")
        if any(
            field in serializer.validated_data
            and serializer.validated_data[field].pk != getattr(exam, field + "_id")
            for field in ["batch", "subject"]
        ):
            raise ValidationError("Academic context is locked. Cancel and create a new exam.")
        if (
            any(
                k in serializer.validated_data and serializer.validated_data[k] != getattr(exam, k)
                for k in ["total_marks", "passing_marks"]
            )
            and exam.scores.filter(Q(marks__isnull=False) | Q(is_absent=True)).exists()
        ):
            raise ValidationError("Marks limits cannot change after marks entry.")
        serializer.instance = exam
        serializer.save()

    @action(detail=True, methods=["get", "post"])
    @transaction.atomic
    def marks(self, request, pk=None):
        exam = self.get_object()
        require_teaching_scope(request.user, exam.batch, exam.subject)
        exam = Exam.objects.select_for_update().get(pk=exam.pk)
        if request.method == "POST":
            if exam.published_at or exam.is_cancelled:
                raise ValidationError("Published or cancelled exam marks cannot be edited.")

            class Row(serializers.Serializer):
                score = serializers.IntegerField(min_value=1)
                marks = serializers.DecimalField(
                    max_digits=7, decimal_places=2, min_value=Decimal("0"), allow_null=True
                )
                is_absent = serializers.BooleanField(default=False)
                remark = serializers.CharField(
                    max_length=300, required=False, allow_blank=True, default=""
                )

            data = Row(data=request.data.get("scores"), many=True, allow_empty=False)
            data.is_valid(raise_exception=True)
            if len({row["score"] for row in data.validated_data}) != len(data.validated_data):
                raise ValidationError("Duplicate score entries.")
            for row in data.validated_data:
                score = get_object_or_404(exam.scores, pk=row["score"])
                if row["marks"] is not None and (
                    row["marks"] > exam.total_marks or row["is_absent"]
                ):
                    raise ValidationError("Marks exceed the maximum or conflict with absence.")
                previous = str(score.marks)
                score.marks, score.is_absent, score.remark = (
                    row["marks"],
                    row["is_absent"],
                    row["remark"],
                )
                score.save()
                AuditLog.objects.create(
                    institute_id=exam.institute_id,
                    actor=request.user,
                    action="marks-save",
                    entity="ExamScore",
                    entity_id=str(score.pk),
                    summary={
                        "before": previous,
                        "after": str(score.marks),
                        "absent": score.is_absent,
                    },
                )
        return Response(
            ScoreSerializer(
                exam.scores.select_related(
                    "exam", "enrollment__student__user", "enrollment__batch"
                ),
                many=True,
            ).data
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def publication(self, request, pk=None):
        exam = Exam.objects.select_for_update().get(pk=self.get_object().pk)

        class Publication(serializers.Serializer):
            published = serializers.BooleanField()

        data = Publication(data=request.data)
        data.is_valid(raise_exception=True)
        publish = data.validated_data["published"]
        if publish and (
            exam.is_cancelled
            or not exam.scores.exists()
            or exam.scores.filter(marks=None, is_absent=False).exists()
        ):
            raise ValidationError("Complete all marks or absence entries before publishing.")
        exam.published_at = timezone.now() if publish else None
        exam.save(update_fields=["published_at"])
        AuditLog.objects.create(
            institute_id=exam.institute_id,
            actor=request.user,
            action="result-publication",
            entity="Exam",
            entity_id=str(exam.pk),
            summary={"published": publish},
        )
        if publish:
            from notifications.services import student_event

            for score in exam.scores.select_related("enrollment__student"):
                student_event(score.enrollment.student, "results", exam.pk)
        return Response(self.get_serializer(exam).data)


class ResultViewSet(viewsets.ReadOnlyModelViewSet):
    module_filters = {
        "class": ("enrollment__batch__academic_class_id", "id"),
        "batch": ("enrollment__batch_id", "id"),
        "subject": ("exam__subject_id", "id"),
        "exam": ("exam_id", "id"),
        "date_from": ("exam__date__gte", "date"),
        "date_to": ("exam__date__lte", "date"),
    }
    search_fields = ["exam__name", "enrollment__student__user__full_name"]
    permission_classes = [ActiveTenantUser]
    serializer_class = ScoreSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ExamScore.objects.filter(
            institute_id=user.institute_id,
            exam__in=exams_for(user),
            exam__published_at__isnull=False,
        )
        if user.role in (Role.STUDENT, Role.PARENT):
            qs = qs.filter(enrollment__student__in=students_for(user))
        if "student" in self.request.query_params:
            qs = qs.filter(
                enrollment__student_id=serializers.IntegerField(min_value=1).run_validation(
                    self.request.query_params["student"]
                )
            )
        return qs.select_related(
            "exam", "exam__subject", "enrollment__batch", "enrollment__student__user"
        ).order_by("-exam__date", "pk")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = list(self.filter_queryset(self.get_queryset()))
        groups = {}
        passed = 0
        for score in rows:
            result = result_values(score)
            passed += result["result"] == "PASS"
            group = groups.setdefault(
                score.exam_id,
                {
                    "id": score.exam_id,
                    "exam": score.exam.name,
                    "batch": score.enrollment.batch.name,
                    "subject": score.exam.subject.name,
                    "students": 0,
                    "passed": 0,
                    "marks": Decimal("0"),
                    "total_marks": score.exam.total_marks,
                },
            )
            group["students"] += 1
            group["passed"] += result["result"] == "PASS"
            group["marks"] += score.marks or Decimal("0")
        summary = [
            {
                "id": g["id"],
                "exam": g["exam"],
                "batch": g["batch"],
                "subject": g["subject"],
                "students": g["students"],
                "passed": g["passed"],
                "failed_absent": g["students"] - g["passed"],
                "average": str((g["marks"] / g["students"]).quantize(Decimal("0.01"))),
                "pass_percentage": round(g["passed"] * 100 / g["students"], 2),
            }
            for g in groups.values()
        ]
        return Response(
            {
                "Published exams": len(groups),
                "Results": len(rows),
                "Passed": passed,
                "Pass percentage": round(passed * 100 / len(rows), 2) if rows else None,
                "sections": [
                    {
                        "title": "Exam performance",
                        "columns": [
                            ["exam", "Exam"],
                            ["batch", "Batch"],
                            ["subject", "Subject"],
                            ["students", "Students"],
                            ["average", "Average marks"],
                            ["passed", "Passed"],
                            ["failed_absent", "Failed / absent"],
                            ["pass_percentage", "Pass (%)"],
                        ],
                        "rows": summary,
                    }
                ],
            }
        )

    @action(detail=False, methods=["get"])
    def report(self, request):
        from rest_framework.exceptions import PermissionDenied

        from common.reports import csv_report

        if request.user.role not in (Role.ADMIN, Role.TEACHER):
            raise PermissionDenied()
        rows = self.filter_queryset(self.get_queryset())
        return csv_report(
            "results",
            ["Student", "Exam", "Batch", "Subject", "Marks", "Total", "Percentage", "Result"],
            (
                (
                    r.enrollment.student.user.full_name,
                    r.exam.name,
                    r.enrollment.batch.name,
                    r.exam.subject.name,
                    r.marks,
                    r.exam.total_marks,
                    result_values(r)["percentage"],
                    result_values(r)["result"],
                )
                for r in rows
            ),
        )

    @action(detail=True, methods=["get"])
    def report_card(self, request, pk=None):
        score = self.get_object()
        calculated = result_values(score)
        html = format_html(
            '<!doctype html><html><head><meta charset="utf-8"><title>Report card</title></head>'
            "<body><h1>{}</h1><h2>{}</h2><p>{} | Roll {}</p><p>{} | {}</p><p>Marks: {} / {}</p>"
            "<p>Percentage: {} | Result: {}</p>"
            "<p>Use browser Print / Save as PDF.</p></body></html>",
            score.institute.name,
            score.exam.name,
            score.enrollment.student.user.full_name,
            score.enrollment.registration.roll_number,
            score.enrollment.batch.name,
            score.exam.subject.name,
            score.marks if score.marks is not None else "Absent",
            score.exam.total_marks,
            calculated["percentage"] or "-",
            calculated["result"],
        )
        response = HttpResponse(html)
        response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response
