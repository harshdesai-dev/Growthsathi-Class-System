from rest_framework.permissions import BasePermission

from .models import Role


class ActiveTenantUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        institute = getattr(request, "institute", None)
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.must_change_password
            and institute
            and institute.is_active
            and user.institute_id == institute.pk
            and user.role in (Role.ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT)
            and not getattr(request, "platform_context", False)
        )


class PlatformOperator(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.must_change_password
            and user.role == Role.SUPER_ADMIN
            and user.institute_id is None
            and getattr(request, "platform_context", False)
            and getattr(request, "institute", None) is None
        )
