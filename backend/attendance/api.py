from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from academics.models import Batch, Enrollment, Subject
from academics.scopes import assignments_for, require_teaching_scope, students_for
from accounts.models import Role
from accounts.permissions import ActiveTenantUser
from audit.models import AuditLog
from common.api import AdminResourceViewSet, TenantSerializer
from institutes.models import Institute

from .models import AttendanceRecord, AttendanceSession, AttendanceStatus, TeacherAttendanceRecord


class AttendanceSerializer(serializers.ModelSerializer):
    student = serializers.IntegerField(source="enrollment.student_id")
    student_name = serializers.CharField(source="enrollment.student.user.full_name")
    batch_name = serializers.CharField(source="enrollment.batch.name")
    subject_name = serializers.CharField(source="session.subject.name")
    date = serializers.DateField(source="session.date")

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "student",
            "student_name",
            "batch_name",
            "subject_name",
            "date",
            "status",
            "remark",
        ]


class AttendanceInput(serializers.Serializer):
    class Row(serializers.Serializer):
        student = serializers.IntegerField(min_value=1)
        status = serializers.ChoiceField(choices=AttendanceStatus.choices)
        remark = serializers.CharField(max_length=300, required=False, allow_blank=True)

    batch = serializers.IntegerField(min_value=1)
    subject = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    records = Row(many=True, allow_empty=False)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    module_filters = {
        "class": ("session__batch__academic_class_id", "id"),
        "date_from": ("session__date__gte", "date"),
        "date_to": ("session__date__lte", "date"),
        "status": ("status", "text"),
    }
    search_fields = [
        "enrollment__student__user__full_name",
        "enrollment__registration__roll_number",
    ]
    permission_classes = [ActiveTenantUser]
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        user = self.request.user
        qs = AttendanceRecord.objects.filter(institute_id=user.institute_id)
        if user.role == Role.TEACHER:
            scope = Q(pk__in=[])
            for pair in assignments_for(user).values("batch_id", "subject_id"):
                scope |= Q(
                    session__batch_id=pair["batch_id"], session__subject_id=pair["subject_id"]
                )
            qs = qs.filter(scope)
        elif user.role != Role.ADMIN:
            qs = qs.filter(enrollment__student__in=students_for(user))
        for param, lookup in [
            ("student", "enrollment__student_id"),
            ("batch", "session__batch_id"),
            ("subject", "session__subject_id"),
        ]:
            if param in self.request.query_params:
                qs = qs.filter(
                    **{
                        lookup: serializers.IntegerField(min_value=1).run_validation(
                            self.request.query_params[param]
                        )
                    }
                )
        return qs.select_related(
            "enrollment__student__user", "enrollment__batch", "session__subject"
        ).order_by("-session__date", "pk")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = self.filter_queryset(self.get_queryset())
        counts = {status: rows.filter(status=status).count() for status in AttendanceStatus.values}
        total = sum(counts.values())
        # Late counts as attended; shared deterministic rule for every portal.
        percentage = round((counts["PRESENT"] + counts["LATE"]) * 100 / total, 2) if total else None
        from institutes.models import InstituteSettings

        settings = InstituteSettings.objects.filter(institute_id=request.user.institute_id).first()
        threshold = settings.attendance_threshold if settings else 75

        def groups(fields):
            return rows.values(*fields).annotate(
                total=Count("id"), attended=Count("id", filter=Q(status__in=["PRESENT", "LATE"]))
            )

        low = [
            {
                "id": row["enrollment__student_id"],
                "student": row["enrollment__student__user__full_name"],
                "percentage": round(row["attended"] * 100 / row["total"], 2),
            }
            for row in groups(["enrollment__student_id", "enrollment__student__user__full_name"])
            if row["attended"] * 100 < threshold * row["total"]
        ]
        monthly = (
            rows.annotate(month=TruncMonth("session__date"))
            .values("month")
            .annotate(
                total=Count("id"), attended=Count("id", filter=Q(status__in=["PRESENT", "LATE"]))
            )
            .order_by("month")
        )
        sections = [
            {
                "title": "Low attendance",
                "columns": [["student", "Student"], ["percentage", "Attendance (%)"]],
                "rows": low,
            },
            {
                "title": "Monthly attendance",
                "columns": [["month", "Month"], ["total", "Recorded"], ["attended", "Attended"]],
                "rows": [{"id": index, **row} for index, row in enumerate(monthly)],
            },
        ]
        return Response(
            {
                "counts": counts,
                "total": total,
                "percentage": percentage,
                "Threshold (%)": threshold,
                "sections": sections,
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
            "attendance",
            ["Student", "Batch", "Subject", "Date", "Status", "Remark"],
            (
                (
                    r.enrollment.student.user.full_name,
                    r.enrollment.batch.name,
                    r.session.subject.name,
                    r.session.date,
                    r.status,
                    r.remark,
                )
                for r in rows
            ),
        )

    @action(detail=False, methods=["get"])
    def roster(self, request):
        class Selection(serializers.Serializer):
            batch = serializers.IntegerField(min_value=1)
            subject = serializers.IntegerField(min_value=1)
            date = serializers.DateField()

        selection = Selection(data=request.query_params)
        selection.is_valid(raise_exception=True)
        values = selection.validated_data
        batch = get_object_or_404(Batch, pk=values["batch"], institute_id=request.user.institute_id)
        subject = get_object_or_404(
            Subject, pk=values["subject"], institute_id=request.user.institute_id
        )
        require_teaching_scope(request.user, batch, subject)
        entries = Enrollment.objects.filter(
            institute_id=request.user.institute_id,
            batch=batch,
            started_at__date__lte=values["date"],
        ).filter(Q(ended_at=None) | Q(ended_at__date__gte=values["date"]))
        existing = {
            row.enrollment.student_id: row
            for row in AttendanceRecord.objects.filter(
                institute_id=request.user.institute_id,
                session__batch=batch,
                session__subject=subject,
                session__date=values["date"],
            ).select_related("enrollment")
        }
        students = {}
        for entry in entries.select_related("student__user").order_by("started_at"):
            saved = existing.get(entry.student_id)
            students[entry.student_id] = {
                "id": entry.student_id,
                "full_name": entry.student.user.full_name,
                "status": saved.status if saved else "PRESENT",
                "remark": saved.remark if saved else "",
            }
        return Response(list(students.values()))

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def record(self, request):
        data = AttendanceInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        Institute.objects.select_for_update().get(pk=request.user.institute_id)
        batch = get_object_or_404(Batch, pk=values["batch"], institute_id=request.user.institute_id)
        subject = get_object_or_404(
            Subject, pk=values["subject"], institute_id=request.user.institute_id
        )
        require_teaching_scope(request.user, batch, subject)
        if values["date"] > timezone.localdate():
            raise ValidationError("Attendance cannot be recorded in the future.")
        if request.user.role == Role.TEACHER and values["date"] != timezone.localdate():
            raise ValidationError("Only Admin may correct previous-day attendance.")
        students = [row["student"] for row in values["records"]]
        if len(set(students)) != len(students):
            raise ValidationError("Duplicate student in attendance submission.")
        roster = (
            Enrollment.objects.filter(
                institute_id=request.user.institute_id,
                batch=batch,
                started_at__date__lte=values["date"],
            )
            .filter(Q(ended_at=None) | Q(ended_at__date__gte=values["date"]))
            .order_by("started_at")
        )
        enrollments = {entry.student_id: entry for entry in roster}
        if any(student not in enrollments for student in students):
            raise ValidationError("Every student must be enrolled in this batch on this date.")
        session, _ = AttendanceSession.objects.get_or_create(
            institute_id=request.user.institute_id,
            batch=batch,
            subject=subject,
            date=values["date"],
            defaults={"recorded_by": request.user},
        )
        changes = []
        for row in values["records"]:
            enrollment = enrollments[row["student"]]
            previous = AttendanceRecord.objects.filter(
                session=session, enrollment=enrollment
            ).first()
            changes.append(
                {
                    "student": row["student"],
                    "before": previous.status if previous else None,
                    "after": row["status"],
                }
            )
            AttendanceRecord.objects.update_or_create(
                institute_id=request.user.institute_id,
                session=session,
                enrollment=enrollment,
                defaults={"status": row["status"], "remark": row.get("remark", "")},
            )
        AuditLog.objects.create(
            institute_id=request.user.institute_id,
            actor=request.user,
            action="attendance-save",
            entity="AttendanceSession",
            entity_id=str(session.pk),
            summary={"changes": changes},
        )
        from institutes.models import InstituteSettings
        from notifications.services import student_event

        preferences = InstituteSettings.objects.filter(
            institute_id=request.user.institute_id
        ).first()
        if not preferences or preferences.absence_alerts:
            for row in values["records"]:
                if row["status"] in ("ABSENT", "LATE"):
                    student_event(enrollments[row["student"]].student, "attendance", session.pk)
        return Response({"session": session.pk, "saved": len(students)})


class TeacherAttendanceSerializer(TenantSerializer):
    teacher_name = serializers.CharField(source="teacher.user.full_name", read_only=True)

    class Meta:
        model = TeacherAttendanceRecord
        fields = ["id", "teacher", "teacher_name", "date", "status", "remark"]


class TeacherAttendanceViewSet(AdminResourceViewSet):
    queryset = TeacherAttendanceRecord.objects.all()
    serializer_class = TeacherAttendanceSerializer
    search_fields = ["teacher__user__full_name"]

    def initial(self, request, *args, **kwargs):
        viewsets.ModelViewSet.initial(self, request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS") or request.user.role != Role.TEACHER:
            from academics.scopes import require_admin

            require_admin(request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        return (
            qs.filter(teacher__user=self.request.user)
            if self.request.user.role == Role.TEACHER
            else qs
        )

    def perform_create(self, serializer):
        from django.db import transaction

        from audit.models import AuditLog

        with transaction.atomic():
            if serializer.validated_data["date"] > timezone.localdate():
                raise ValidationError("Attendance cannot be recorded in the future.")
            entry = serializer.save(institute_id=self.request.user.institute_id)
            AuditLog.objects.create(
                institute_id=entry.institute_id,
                actor=self.request.user,
                action="teacher-attendance-create",
                entity="TeacherAttendanceRecord",
                entity_id=str(entry.pk),
            )
