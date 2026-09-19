from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError

from academics.scopes import assignments_for, batches_for
from accounts.models import Role
from accounts.permissions import ActiveTenantUser
from common.api import TenantSerializer
from materials.api import asset_response

from .models import Announcement


def announcements_for(user):
    qs = Announcement.objects.filter(institute_id=user.institute_id)
    if user.role == Role.ADMIN:
        return qs
    audience = {Role.TEACHER: "TEACHERS", Role.STUDENT: "STUDENTS", Role.PARENT: "PARENTS"}.get(
        user.role
    )
    batches = batches_for(user)
    scope = (
        Q(audience__in=["ALL", audience])
        | Q(audience="BATCH", batch__in=batches)
        | Q(audience="CLASS", academic_class_id__in=batches.values("academic_class_id"))
    )
    if user.role == Role.TEACHER:
        # Teachers can review their own future announcements while still assigned.
        return qs.filter(
            (
                scope
                & Q(published_at__lte=timezone.now())
                & (Q(expires_at=None) | Q(expires_at__gt=timezone.now()))
                & Q(is_active=True)
            )
            | Q(created_by=user, batch__in=batches)
        )
    return qs.filter(scope, is_active=True, published_at__lte=timezone.now()).filter(
        Q(expires_at=None) | Q(expires_at__gt=timezone.now())
    )


class AnnouncementSerializer(TenantSerializer):
    sender_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "message",
            "audience",
            "batch",
            "academic_class",
            "attachment",
            "sender_name",
            "published_at",
            "expires_at",
            "is_important",
            "is_active",
        ]

    def validate(self, attrs):
        def value(field):
            return attrs.get(field, getattr(self.instance, field, None))

        audience, batch, academic_class = value("audience"), value("batch"), value("academic_class")
        if (audience == "BATCH") != bool(batch) or (audience == "CLASS") != bool(academic_class):
            raise ValidationError("Audience must match exactly its batch or class target.")
        user = self.context["request"].user
        if user.role == Role.TEACHER and (
            audience != "BATCH" or not assignments_for(user).filter(batch=batch).exists()
        ):
            raise PermissionDenied("Teachers may send to their assigned batches only.")
        attachment = value("attachment")
        if attachment and (
            attachment.student_id
            or (user.role != Role.ADMIN and attachment.uploaded_by_id != user.pk)
        ):
            raise PermissionDenied("Attachment unavailable.")
        return attrs


class AnnouncementViewSet(viewsets.ModelViewSet):
    module_filters = {
        "audience": ("audience", "text"),
        "batch": ("batch_id", "id"),
        "class": ("academic_class_id", "id"),
        "is_important": ("is_important", "bool"),
        "date_from": ("published_at__date__gte", "date"),
        "date_to": ("published_at__date__lte", "date"),
    }
    permission_classes = [ActiveTenantUser]
    serializer_class = AnnouncementSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    search_fields = ["title", "message"]

    def get_queryset(self):
        qs = announcements_for(self.request.user)
        if self.request.query_params.get("student"):
            from academics.models import Enrollment
            from academics.scopes import selected_students

            selected = selected_students(self.request)
            batches = Enrollment.objects.filter(student__in=selected, ended_at=None).values(
                "batch_id"
            )
            classes = Enrollment.objects.filter(student__in=selected, ended_at=None).values(
                "batch__academic_class_id"
            )
            qs = qs.filter(
                Q(audience__in=["ALL", "PARENTS", "STUDENTS"])
                | Q(batch_id__in=batches)
                | Q(academic_class_id__in=classes)
            )
        return qs.select_related("created_by").order_by("-published_at")

    def perform_create(self, serializer):
        if self.request.user.role not in (Role.ADMIN, Role.TEACHER):
            raise PermissionDenied()
        announcement = serializer.save(
            institute_id=self.request.user.institute_id, created_by=self.request.user
        )
        from notifications.services import announce

        announce(announcement)

    def perform_update(self, serializer):
        user = self.request.user
        if user.role != Role.ADMIN and (
            user.role != Role.TEACHER or serializer.instance.created_by_id != user.pk
        ):
            raise PermissionDenied()
        announcement = serializer.save()
        from notifications.services import announce

        announce(announcement)

    @action(detail=True, methods=["get"])
    def attachment(self, request, pk=None):
        notice = self.get_object()
        if not notice.attachment_id:
            raise ValidationError("No attachment.")
        return asset_response(notice.attachment)
