from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.middleware.csrf import get_token, rotate_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditLog

from .authentication import validate_context
from .models import AccountStatus, LoginSession, Role, User, normalize_username
from .throttling import limit_access
from .tokens import activation_tokens, reset_tokens


def audit(user, action):
    AuditLog.objects.create(
        institute_id=user.institute_id,
        actor=user,
        action=action,
        entity="User",
        entity_id=str(user.pk),
    )


def user_data(user):
    return {
        "id": user.pk,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
        "phone": user.phone,
        "must_change_password": user.must_change_password,
        "route": "/account/password" if user.must_change_password else "/portal/dashboard",
    }


def context_users(request):
    if request.institute and request.institute.is_active and not request.platform_context:
        return User.objects.filter(institute=request.institute).exclude(role=Role.SUPER_ADMIN)
    if request.platform_context and request.institute is None:
        return User.objects.filter(institute=None, role=Role.SUPER_ADMIN)
    return User.objects.none()


def cookies(response, refresh):
    for name, token, path in [
        (settings.ACCESS_COOKIE_NAME, refresh.access_token, "/api/"),
        (settings.REFRESH_COOKIE_NAME, refresh, "/api/auth/"),
    ]:
        response.set_cookie(
            name,
            str(token),
            max_age=max(0, token["exp"] - int(timezone.now().timestamp())),
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite="Lax",
            path=path,
        )
    return response


def clear_cookies(response):
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/api/", samesite="Lax")
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/auth/", samesite="Lax")
    return response


def start_session(user):
    refresh = RefreshToken.for_user(user)
    session = LoginSession.objects.create(
        user=user,
        refresh_jti=refresh["jti"],
        expires_at=datetime.fromtimestamp(refresh["exp"], UTC),
    )
    refresh["sid"] = str(session.pk)
    return refresh


def new_password(user, password):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": exc.messages}) from exc
    user.set_password(password)
    user.must_change_password = False
    user.save()
    LoginSession.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())


class Credentials(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class PasswordChange(serializers.Serializer):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class RecoveryRequest(serializers.Serializer):
    username = serializers.CharField(max_length=150)


class RecoveryConfirm(serializers.Serializer):
    uid = serializers.IntegerField(min_value=1)
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


# Django's CSRF decorator protects anonymous login/reset and refresh as well as
# authenticated mutations. DRF cookie authentication also enforces it globally.
@method_decorator(csrf_protect, name="dispatch")
class PublicAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        return "Cookie"


class ContextView(PublicAuthView):
    def get(self, request):
        csrf = get_token(request)
        if request.platform_context:
            return Response({"platform": True, "name": "GrowthSathi", "csrfToken": csrf})
        institute = request.institute
        if not institute:
            return Response({"detail": "Portal unavailable. Contact your institute."}, status=404)
        return Response(
            {
                "platform": False,
                "name": institute.name,
                "primary_color": institute.primary_color,
                "has_logo": bool(institute.logo),
                "csrfToken": csrf,
            }
        )


class LoginView(PublicAuthView):
    def post(self, request):
        data = Credentials(data=request.data)
        data.is_valid(raise_exception=True)
        limit_access(request, "login", data.validated_data["username"])
        user = authenticate(request, **data.validated_data)
        if not user:
            raise AuthenticationFailed("Invalid credentials or account unavailable.")
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            validate_context(request, user)
            refresh = start_session(user)
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
            audit(user, "login")
        rotate_token(request)
        return cookies(
            Response({"user": user_data(user), "csrfToken": get_token(request)}), refresh
        )


class RefreshView(PublicAuthView):
    def post(self, request):
        try:
            refresh = RefreshToken(request.COOKIES.get(settings.REFRESH_COOKIE_NAME, ""))
            with transaction.atomic():
                session = (
                    LoginSession.objects.select_for_update()
                    .select_related("user")
                    .filter(
                        pk=refresh.get("sid"),
                        refresh_jti=refresh["jti"],
                        revoked_at=None,
                        expires_at__gt=timezone.now(),
                    )
                    .first()
                )
                if not session:
                    raise AuthenticationFailed("Session expired. Please sign in again.")
                # The library checks active state and password-change revocation.
                user = JWTAuthentication().get_user(refresh)
                if session.user_id != user.pk:
                    raise AuthenticationFailed("Session unavailable.")
                validate_context(request, user)
                refresh.blacklist()
                replacement = RefreshToken.for_user(user)
                replacement["sid"] = str(session.pk)
                session.refresh_jti = replacement["jti"]
                # Absolute seven-day session lifetime; refresh cannot extend it.
                replacement["exp"] = int(session.expires_at.timestamp())
                session.save(update_fields=["refresh_jti"])
                return cookies(Response({"user": user_data(user)}), replacement)
        except TokenError as exc:
            raise AuthenticationFailed("Session expired. Please sign in again.") from exc


class LogoutView(PublicAuthView):
    def post(self, request):
        try:
            refresh = RefreshToken(request.COOKIES.get(settings.REFRESH_COOKIE_NAME, ""))
            user = User.objects.get(pk=refresh["user_id"])
            validate_context(request, user)
            with transaction.atomic():
                LoginSession.objects.filter(pk=refresh.get("sid"), user=user).update(
                    revoked_at=timezone.now()
                )
                refresh.blacklist()
                audit(user, "logout")
        except TokenError:
            pass
        except User.DoesNotExist:
            pass
        except AuthenticationFailed:
            pass
        return clear_cookies(Response({"detail": "Signed out."}))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(user_data(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = PasswordChange(data=request.data)
        data.is_valid(raise_exception=True)
        limit_access(request, "password-change", request.user.username)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(data.validated_data["current_password"]):
                raise ValidationError({"current_password": ["Current password is incorrect."]})
            new_password(user, data.validated_data["password"])
            audit(user, "password-change")
        return clear_cookies(Response({"detail": "Password changed. Please sign in again."}))


def send_account_link(request, user, purpose):
    generator = activation_tokens if purpose == "activate" else reset_tokens
    token = generator.make_token(user)
    # Fragment keeps recovery credentials out of ordinary HTTP request logs.
    url = request.build_absolute_uri(f"/account/{purpose}") + f"#uid={user.pk}&token={token}"
    send_mail(
        "Your account access",
        f"Open this link to continue:\n{url}\nThis link expires in one hour.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


class ResetRequestView(PublicAuthView):
    def post(self, request):
        data = RecoveryRequest(data=request.data)
        data.is_valid(raise_exception=True)
        username = normalize_username(data.validated_data["username"])
        limit_access(request, "recovery", username)
        user = context_users(request).filter(username=username, status=AccountStatus.ACTIVE).first()
        if user and user.email:
            send_account_link(request, user, "reset")
        return Response(
            {"detail": "If recovery is available, instructions will be sent to your contact."}
        )


class RecoveryConfirmView(PublicAuthView):
    purpose = "reset"

    def post(self, request):
        data = RecoveryConfirm(data=request.data)
        data.is_valid(raise_exception=True)
        limit_access(request, "recovery-confirm", str(data.validated_data["uid"]))
        expected = AccountStatus.PENDING if self.purpose == "activate" else AccountStatus.ACTIVE
        generator = activation_tokens if self.purpose == "activate" else reset_tokens
        with transaction.atomic():
            user = (
                context_users(request)
                .select_for_update()
                .filter(pk=data.validated_data["uid"], status=expected)
                .first()
            )
            if not user or not generator.check_token(user, data.validated_data["token"]):
                raise ValidationError({"detail": "Invalid or expired account link."})
            user.status = AccountStatus.ACTIVE
            new_password(user, data.validated_data["password"])
            audit(user, self.purpose)
        return clear_cookies(Response({"detail": "Account updated. Please sign in."}))


class ActivationView(RecoveryConfirmView):
    purpose = "activate"
