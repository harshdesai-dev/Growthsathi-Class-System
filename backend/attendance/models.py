from django.core.exceptions import ValidationError
from django.db import models

from institutes.models import TenantModel


class AttendanceSession(TenantModel):
    batch = models.ForeignKey("academics.Batch", on_delete=models.PROTECT)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    date = models.DateField()
    recorded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "batch", "subject", "date"], name="attendance_session_unique"
            )
        ]


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"


class AttendanceRecord(TenantModel):
    def clean(self):
        super().clean()
        if (
            self.session_id
            and self.enrollment_id
            and self.session.batch_id != self.enrollment.batch_id
        ):
            raise ValidationError({"enrollment": "Enrollment must belong to the attendance batch."})

    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name="records")
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    remark = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "enrollment"], name="attendance_record_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=AttendanceStatus.values),
                name="attendance_status_valid",
            ),
        ]


class TeacherAttendanceRecord(TenantModel):
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.PROTECT)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    remark = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["teacher", "date"], name="teacher_attendance_unique")
        ]
