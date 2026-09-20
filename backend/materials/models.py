import uuid
from pathlib import Path

from django.db import models

from institutes.models import TenantModel


def private_path(instance, filename):
    return f"{instance.institute_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class FileAsset(TenantModel):
    file = models.FileField(upload_to=private_path)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    student = models.ForeignKey(
        "accounts.StudentProfile", null=True, blank=True, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)


class StudyMaterial(TenantModel):
    title = models.CharField(max_length=180)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    batch = models.ForeignKey("academics.Batch", on_delete=models.PROTECT, null=True, blank=True)
    academic_class = models.ForeignKey(
        "academics.AcademicClass", on_delete=models.PROTECT, null=True, blank=True
    )
    topic = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    file_asset = models.ForeignKey(FileAsset, on_delete=models.PROTECT, null=True, blank=True)
    external_url = models.URLField(blank=True)
    uploaded_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    downloads = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
