"""Deny authentication until an explicit verified tenant context is provided."""

from django.contrib.auth.backends import BaseBackend

from .models import AccountStatus, Role, User, normalize_username


class TenantBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if request is None or username is None or password is None:
            return None
        institute = getattr(request, "institute", None)
        platform = getattr(request, "platform_context", False)
        if institute is not None and institute.is_active and not platform:
            users = User.objects.filter(institute=institute).exclude(role=Role.SUPER_ADMIN)
        elif platform and institute is None:
            users = User.objects.filter(institute=None, role=Role.SUPER_ADMIN)
        else:
            User().set_password(password)
            return None
        user = users.filter(username=normalize_username(username)).first()
        if user is None:
            User().set_password(password)
            return None
        if user.check_password(password) and user.status == AccountStatus.ACTIVE:
            return user
        return None

    def get_user(self, user_id):
        user = User.objects.select_related("institute").filter(pk=user_id).first()
        if user and user.is_active and (user.institute_id is None or user.institute.is_active):
            return user
        return None
