from django.db import models

from institutes.models import TenantModel


class TimetableEntry(TenantModel):
    batch = models.ForeignKey("academics.Batch", on_delete=models.PROTECT)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.PROTECT)
    date = models.DateField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    room = models.CharField(max_length=80, blank=True)
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")), name="lecture_time_ordered"
            )
        ]
        ordering = ["date", "starts_at"]
