from django.db import models
from django.utils import timezone

from institutes.models import TenantModel


class Announcement(TenantModel):
    class Audience(models.TextChoices):
        ALL = "ALL", "All"
        STUDENTS = "STUDENTS", "Students"
        PARENTS = "PARENTS", "Parents"
        TEACHERS = "TEACHERS", "Teachers"
        BATCH = "BATCH", "Batch"
        CLASS = "CLASS", "Class"

    title = models.CharField(max_length=180)
    message = models.TextField()
    audience = models.CharField(max_length=12, choices=Audience.choices)
    batch = models.ForeignKey("academics.Batch", on_delete=models.PROTECT, null=True, blank=True)
    academic_class = models.ForeignKey(
        "academics.AcademicClass", on_delete=models.PROTECT, null=True, blank=True
    )
    attachment = models.ForeignKey(
        "materials.FileAsset", on_delete=models.PROTECT, null=True, blank=True
    )
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    published_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at=None)
                | models.Q(expires_at__gt=models.F("published_at")),
                name="announcement_dates_ordered",
            )
        ]
