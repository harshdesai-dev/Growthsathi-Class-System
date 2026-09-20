from django.db import transaction
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.models import TeacherAssignment
from academics.scopes import assignments_for, batches_for, require_admin
from accounts.models import Role
from audit.models import AuditLog
from common.api import AdminResourceViewSet, TenantSerializer
from institutes.models import Institute

from .models import TimetableEntry


class TimetableSerializer(TenantSerializer):
    batch_name = serializers.CharField(source="batch.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.user.full_name", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = [
            "id",
            "batch",
            "subject",
            "teacher",
            "date",
            "starts_at",
            "ends_at",
            "room",
            "is_cancelled",
            "batch_name",
            "subject_name",
            "teacher_name",
        ]


class TimetableViewSet(AdminResourceViewSet):
    queryset = TimetableEntry.objects.all()
    serializer_class = TimetableSerializer

    def initial(self, request, *args, **kwargs):
        viewsets.ModelViewSet.initial(self, request, *args, **kwargs)
        if request.user.role == Role.PARENT:
            raise PermissionDenied()
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            require_admin(request.user)

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset.filter(institute_id=user.institute_id)
        if user.role == Role.TEACHER:
            pairs = assignments_for(user).values("batch_id", "subject_id")
            allowed = Q(pk__in=[])
            for pair in pairs:
                allowed |= Q(batch_id=pair["batch_id"], subject_id=pair["subject_id"])
            qs = qs.filter(allowed, teacher__user=user)
        elif user.role == Role.STUDENT:
            qs = qs.filter(batch__in=batches_for(user))
        if self.request.query_params.get("date"):
            field = serializers.DateField()
            qs = qs.filter(date=field.run_validation(self.request.query_params["date"]))
        bounds = {}
        for parameter, lookup in (("date_from", "date__gte"), ("date_to", "date__lte")):
            if self.request.query_params.get(parameter):
                bounds[lookup] = serializers.DateField().run_validation(
                    self.request.query_params[parameter]
                )
        if len(bounds) == 2 and bounds["date__gte"] > bounds["date__lte"]:
            raise ValidationError("Start date must not follow end date.")
        qs = qs.filter(**bounds)
        return qs.select_related("batch", "subject", "teacher__user").order_by("date", "starts_at")

    @transaction.atomic
    def save_entry(self, serializer):
        user = self.request.user
        # Serialize conflict checks per institute to prevent simultaneous double booking.
        Institute.objects.select_for_update().get(pk=user.institute_id)
        entry = serializer.instance or TimetableEntry(institute_id=user.institute_id)
        before = (
            {
                "date": str(entry.date),
                "starts_at": str(entry.starts_at),
                "ends_at": str(entry.ends_at),
                "cancelled": entry.is_cancelled,
            }
            if entry.pk
            else {}
        )
        for field, value in serializer.validated_data.items():
            setattr(entry, field, value)
        entry.full_clean()
        if not entry.is_cancelled:
            if not TeacherAssignment.objects.filter(
                institute_id=user.institute_id,
                teacher=entry.teacher,
                batch=entry.batch,
                subject=entry.subject,
                is_active=True,
            ).exists():
                raise ValidationError("Teacher must be assigned to this batch and subject.")
            conflicts = TimetableEntry.objects.filter(
                institute_id=user.institute_id,
                date=entry.date,
                is_cancelled=False,
                starts_at__lt=entry.ends_at,
                ends_at__gt=entry.starts_at,
            ).exclude(pk=entry.pk)
            occupied = Q(teacher=entry.teacher) | Q(batch=entry.batch)
            if entry.room:
                occupied |= Q(room__iexact=entry.room.strip())
            if conflicts.filter(occupied).exists():
                raise ValidationError("Teacher, batch or room already has a lecture at this time.")
        entry.room = entry.room.strip()
        entry.save()
        serializer.instance = entry
        from notifications.services import batch_event

        batch_event(entry.batch, "timetable", entry.pk, entry.subject)
        AuditLog.objects.create(
            institute_id=user.institute_id,
            actor=user,
            action="timetable-save",
            entity="TimetableEntry",
            entity_id=str(entry.pk),
            summary={"before": before},
        )

    def perform_create(self, serializer):
        self.save_entry(serializer)

    def perform_update(self, serializer):
        self.save_entry(serializer)
