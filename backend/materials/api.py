from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from academics.scopes import assignments_for, batches_for, require_admin, require_teaching_scope
from accounts.models import Role, StudentProfile
from accounts.permissions import ActiveTenantUser
from common.api import TenantSerializer

from .models import FileAsset, StudyMaterial


def materials_for(user):
    qs = StudyMaterial.objects.filter(institute_id=user.institute_id)
    if user.role == Role.ADMIN:
        return qs
    if user.role == Role.TEACHER:
        scope = Q(pk__in=[])
        for pair in assignments_for(user).values(
            "batch_id", "subject_id", "batch__academic_class_id"
        ):
            scope |= (
                Q(batch_id=pair["batch_id"]) | Q(academic_class_id=pair["batch__academic_class_id"])
            ) & Q(subject_id=pair["subject_id"])
        return qs.filter(scope)
    if user.role == Role.STUDENT:
        batches = batches_for(user)
        return qs.filter(
            Q(batch__in=batches) | Q(academic_class_id__in=batches.values("academic_class_id")),
            is_active=True,
        )
    return qs.none()


def validate_upload(upload):
    if upload.size > 10 * 1024 * 1024 or upload.size == 0:
        raise ValidationError("Files must be nonempty and no larger than 10 MB.")
    extension = Path(upload.name).suffix.lower()
    header = upload.read(16)
    upload.seek(0)
    types = {
        ".pdf": ("application/pdf", b"%PDF-"),
        ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
        ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
        ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
        ".doc": ("application/msword", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        ".ppt": ("application/vnd.ms-powerpoint", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
    }
    if extension in types and header.startswith(types[extension][1]):
        return types[extension][0]
    if extension in (".docx", ".pptx"):
        try:
            with ZipFile(upload) as archive:
                names = archive.namelist()
                prefix = "word/" if extension == ".docx" else "ppt/"
                if (
                    "[Content_Types].xml" in names
                    and any(name.startswith(prefix) for name in names)
                    and not any("vbaproject" in name.lower() for name in names)
                ):
                    return "application/vnd.openxmlformats-officedocument." + (
                        "wordprocessingml.document"
                        if extension == ".docx"
                        else "presentationml.presentation"
                    )
        except BadZipFile:
            pass
        finally:
            upload.seek(0)
    raise ValidationError(
        "File extension and content must match PDF, Office document or PNG/JPEG image."
    )


class MaterialSerializer(TenantSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    uploader_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = StudyMaterial
        fields = [
            "id",
            "title",
            "subject",
            "subject_name",
            "batch",
            "academic_class",
            "topic",
            "description",
            "file_asset",
            "external_url",
            "uploaded_by",
            "uploader_name",
            "is_important",
            "is_active",
            "downloads",
            "created_at",
        ]
        read_only_fields = ["uploaded_by", "downloads", "created_at"]

    def validate(self, attrs):
        def value(key):
            return attrs.get(key, getattr(self.instance, key, None))

        if bool(value("batch")) == bool(value("academic_class")):
            raise ValidationError("Choose a batch or a class target.")
        if bool(value("file_asset")) == bool(value("external_url")):
            raise ValidationError("Choose a file or external link.")
        url = value("external_url")
        if url and not url.startswith(("https://", "http://")):
            raise ValidationError("Only HTTP or HTTPS links are permitted.")
        user = self.context["request"].user
        if user.role == Role.TEACHER:
            if not value("batch"):
                raise PermissionDenied("Teachers may target assigned batches only.")
            require_teaching_scope(user, value("batch"), value("subject"))
        asset = value("file_asset")
        if asset and (
            asset.student_id or (user.role == Role.TEACHER and asset.uploaded_by_id != user.pk)
        ):
            raise PermissionDenied("File unavailable for this material.")
        return attrs


class MaterialViewSet(viewsets.ModelViewSet):
    module_filters = {
        "batch": ("batch_id", "id"),
        "subject": ("subject_id", "id"),
        "topic": ("topic__icontains", "text"),
        "is_important": ("is_important", "bool"),
        "uploader": ("uploaded_by_id", "id"),
    }
    permission_classes = [ActiveTenantUser]
    serializer_class = MaterialSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    search_fields = ["title", "topic", "subject__name"]

    def get_queryset(self):
        return (
            materials_for(self.request.user)
            .select_related("subject", "uploaded_by")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        if self.request.user.role not in (Role.ADMIN, Role.TEACHER):
            raise PermissionDenied()
        material = serializer.save(
            institute_id=self.request.user.institute_id, uploaded_by=self.request.user
        )
        from academics.models import Batch
        from notifications.services import batch_event

        targets = (
            [material.batch]
            if material.batch_id
            else Batch.objects.filter(
                institute_id=material.institute_id,
                academic_class=material.academic_class,
                is_active=True,
            )
        )
        for batch in targets:
            batch_event(batch, "materials", material.pk, material.subject)

    def perform_update(self, serializer):
        user = self.request.user
        if user.role != Role.ADMIN and (
            user.role != Role.TEACHER or serializer.instance.uploaded_by_id != user.pk
        ):
            raise PermissionDenied()
        serializer.save()

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        material = self.get_object()
        if not material.file_asset_id:
            raise ValidationError("This material is an external link.")
        StudyMaterial.objects.filter(pk=material.pk).update(downloads=F("downloads") + 1)
        return asset_response(material.file_asset)


def asset_response(asset):
    try:
        response = FileResponse(
            asset.file.open("rb"),
            as_attachment=True,
            filename=asset.original_name,
            content_type=asset.content_type,
        )
    except FileNotFoundError as exc:
        from rest_framework.exceptions import NotFound

        raise NotFound("File is unavailable.") from exc
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


class FileViewSet(viewsets.ViewSet):
    permission_classes = [ActiveTenantUser]

    @transaction.atomic
    def create(self, request):
        if request.user.role not in (Role.ADMIN, Role.TEACHER):
            raise PermissionDenied()
        upload = request.FILES.get("file")
        if not upload:
            raise ValidationError("Select a file.")
        content_type = validate_upload(upload)
        student = None
        if request.data.get("student"):
            require_admin(request.user)
            student = get_object_or_404(
                StudentProfile,
                pk=serializers.IntegerField(min_value=1).run_validation(request.data["student"]),
                institute_id=request.user.institute_id,
            )
        from django.db.models import Sum

        from institutes.models import Institute, InstituteSubscription

        Institute.objects.select_for_update().get(pk=request.user.institute_id)
        subscription = InstituteSubscription.objects.filter(
            institute_id=request.user.institute_id
        ).first()
        used = (
            FileAsset.objects.filter(institute_id=request.user.institute_id).aggregate(
                value=Sum("size")
            )["value"]
            or 0
        )
        if subscription and used + upload.size > subscription.storage_limit_mb * 1024 * 1024:
            raise ValidationError("Storage limit reached. Contact GrowthSathi support.")
        asset = FileAsset.objects.create(
            institute_id=request.user.institute_id,
            uploaded_by=request.user,
            file=upload,
            original_name=Path(upload.name).name[:200],
            content_type=content_type,
            size=upload.size,
            student=student,
        )
        return Response(
            {"id": asset.pk, "name": asset.original_name, "size": asset.size}, status=201
        )

    def list(self, request):
        require_admin(request.user)
        student = serializers.IntegerField(min_value=1).run_validation(
            request.query_params.get("student")
        )
        rows = FileAsset.objects.filter(institute_id=request.user.institute_id, student_id=student)
        return Response([{"id": f.pk, "name": f.original_name, "size": f.size} for f in rows])

    def retrieve(self, request, pk=None):
        asset = get_object_or_404(FileAsset, pk=pk, institute_id=request.user.institute_id)
        if request.user.role != Role.ADMIN:
            if (
                asset.student_id
                or not materials_for(request.user).filter(file_asset=asset).exists()
            ):
                raise PermissionDenied()
        return asset_response(asset)
