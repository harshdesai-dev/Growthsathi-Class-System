from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler

from academics.scopes import require_admin
from accounts.permissions import ActiveTenantUser


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = ValidationError(getattr(exc, "message_dict", {"detail": exc.messages}))
    elif isinstance(exc, IntegrityError):
        exc = ValidationError({"detail": "This change conflicts with an existing record."})
    return exception_handler(exc, context)


class TenantSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request:
            for field in fields.values():
                if (
                    isinstance(field, serializers.PrimaryKeyRelatedField)
                    and field.queryset is not None
                ):
                    if hasattr(field.queryset.model, "institute_id"):
                        field.queryset = field.queryset.filter(
                            institute_id=request.user.institute_id
                        )
        return fields


class AdminResourceViewSet(viewsets.ModelViewSet):
    permission_classes = [ActiveTenantUser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_admin(request.user)

    def get_queryset(self):
        return self.queryset.filter(institute_id=self.request.user.institute_id).order_by("pk")

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(institute_id=self.request.user.institute_id)

    @transaction.atomic
    def perform_update(self, serializer):
        item = serializer.save()
        from audit.models import AuditLog

        AuditLog.objects.create(
            institute_id=self.request.user.institute_id,
            actor=self.request.user,
            action="record-update",
            entity=item.__class__.__name__,
            entity_id=str(item.pk),
        )
