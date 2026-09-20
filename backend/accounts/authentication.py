from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import LoginSession, Role


def validate_context(request, user):
    institute = getattr(request, "institute", None)
    platform = getattr(request, "platform_context", False)
    if not user.is_active:
        raise AuthenticationFailed("Account access unavailable.")
    if user.role == Role.SUPER_ADMIN:
        allowed = platform and institute is None and user.institute_id is None
    else:
        allowed = (
            not platform
            and institute
            and institute.is_active
            and user.institute_id == institute.pk
            and user.institute.is_active
        )
    if not allowed:
        raise AuthenticationFailed("Account access unavailable.")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw = request.COOKIES.get(settings.ACCESS_COOKIE_NAME)
        if not raw:
            return None
        token = self.get_validated_token(raw)
        user = self.get_user(token)
        validate_context(request, user)
        if not LoginSession.objects.filter(
            pk=token.get("sid"), user=user, revoked_at=None, expires_at__gt=timezone.now()
        ).exists():
            raise AuthenticationFailed("Session expired. Please sign in again.")
        SessionAuthentication().enforce_csrf(request)
        return user, token
