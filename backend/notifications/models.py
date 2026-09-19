from django.db import models
from django.utils import timezone

from institutes.models import TenantModel


class UserNotification(TenantModel):
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    kind = models.CharField(max_length=30)
    object_id = models.PositiveBigIntegerField()
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.PROTECT, null=True, blank=True
    )
    announcement = models.ForeignKey(
        "announcements.Announcement", on_delete=models.PROTECT, null=True, blank=True
    )
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
