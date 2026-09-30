from uuid import uuid4

from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.scopes import require_admin
from accounts.management import UserSerializer
from accounts.models import AccountStatus, LoginSession, Role, StudentProfile, User
from accounts.permissions import ActiveTenantUser, PlatformOperator
from audit.models import AuditLog
from common.api import TenantSerializer
from materials.api import validate_upload
from materials.models import FileAsset

from .models import Institute, InstituteDomain, InstituteSettings, InstituteSubscription, Plan


def platform_audit(actor, institute, action_name, entity, entity_id):
    AuditLog.objects.create(
        actor=actor,
        institute=institute,
        action=action_name,
        entity=entity,
        entity_id=str(entity_id),
    )


class SettingsSerializer(TenantSerializer):
    class Meta:
        model = InstituteSettings
        fields = [
            "attendance_threshold",
            "default_passing_percentage",
            "working_days",
            "fee_due_day",
            "absence_alerts",
            "show_rank",
        ]

    def validate_working_days(self, value):
        if not isinstance(value, list) or any(
            type(x) is not int or x not in range(7) for x in value
        ):
            raise ValidationError("Working days must be a list of weekdays from 0 to 6.")
        return sorted(set(value))


class BrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institute
        fields = ["name", "contact_name", "email", "phone", "address", "primary_color"]


class SettingsView(APIView):
    permission_classes = [ActiveTenantUser]

    def get(self, request):
        require_admin(request.user)
        settings, _ = InstituteSettings.objects.get_or_create(institute=request.institute)
        return Response(
            {
                "branding": BrandingSerializer(request.institute).data,
                "settings": SettingsSerializer(settings).data,
            }
        )

    @transaction.atomic
    def patch(self, request):
        require_admin(request.user)
        settings, _ = InstituteSettings.objects.get_or_create(institute=request.institute)
        branding = BrandingSerializer(
            request.institute, data=request.data.get("branding", {}), partial=True
        )
        rules = SettingsSerializer(settings, data=request.data.get("settings", {}), partial=True)
        branding.is_valid(raise_exception=True)
        rules.is_valid(raise_exception=True)
        branding.save()
        rules.save()
        platform_audit(
            request.user, request.institute, "settings-update", "Institute", request.institute.pk
        )
        return self.get(request)

    def post(self, request):
        require_admin(request.user)
        upload = request.FILES.get("logo")
        if not upload or validate_upload(upload) not in ("image/png", "image/jpeg"):
            raise ValidationError("Choose a PNG or JPEG logo.")
        upload.name = uuid4().hex + (".png" if validate_upload(upload) == "image/png" else ".jpg")
        request.institute.logo = upload
        request.institute.save(update_fields=["logo"])
        return Response({"detail": "Logo updated."})


class LogoView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.institute or not request.institute.logo:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        return FileResponse(
            request.institute.logo.open("rb"),
            content_type="image/png"
            if request.institute.logo.name.endswith(".png")
            else "image/jpeg",
        )


class AdminAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "phone", "status"]
        read_only_fields = ["id", "username", "status"]
        extra_kwargs = {"email": {"allow_blank": False}}

    def validate(self, attrs):
        forbidden = set(self.initial_data) - {"full_name", "email", "phone"}
        if forbidden:
            raise ValidationError({key: "This field cannot be edited." for key in forbidden})
        return attrs


class InstituteSerializer(serializers.ModelSerializer):
    admin_accounts = serializers.SerializerMethodField()

    def get_admin_accounts(self, institute):
        return AdminAccountSerializer(
            User.objects.filter(institute=institute, role=Role.ADMIN), many=True
        ).data

    initial_admin = UserSerializer(write_only=True, required=False)

    class Meta:
        model = Institute
        fields = [
            "id",
            "name",
            "slug",
            "is_active",
            "contact_name",
            "email",
            "phone",
            "address",
            "primary_color",
            "support_note",
            "support_status",
            "created_at",
            "initial_admin",
            "admin_accounts",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        if not self.instance and "initial_admin" not in attrs:
            raise ValidationError("Provide the initial institute Admin.")
        if self.instance and "initial_admin" in attrs:
            raise ValidationError("Use account recovery for existing institutes.")
        if attrs.get("initial_admin", {}).get("role", Role.ADMIN) != Role.ADMIN:
            raise ValidationError("Initial account must be an Admin.")
        if not self.instance:
            email = attrs.get("email")
            if not email:
                raise ValidationError({"email": "Provide an email for initial Admin onboarding."})
            attrs["email"] = User.objects.normalize_email(email)
            admin_email = attrs["initial_admin"].get("email")
            if (
                admin_email is not None
                and User.objects.normalize_email(admin_email) != attrs["email"]
            ):
                raise ValidationError(
                    {"initial_admin": {"email": "Must match the institute email; omit this field."}}
                )
        return attrs

    @transaction.atomic
    def create(self, attrs):
        admin = attrs.pop("initial_admin")
        institute = Institute.objects.create(**attrs)
        admin["role"] = Role.ADMIN
        admin["email"] = institute.email
        UserSerializer(context=self.context).create({**admin, "institute_id": institute.pk})
        InstituteSettings.objects.create(institute=institute)
        return institute


class InstituteViewSet(viewsets.ModelViewSet):
    permission_classes = [PlatformOperator]
    queryset = Institute.objects.all().order_by("pk")
    serializer_class = InstituteSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    search_fields = ["name", "slug"]

    @transaction.atomic
    def perform_create(self, serializer):
        institute = serializer.save()
        platform_audit(self.request.user, institute, "institute-create", "Institute", institute.pk)

    @transaction.atomic
    def perform_update(self, serializer):
        institute = serializer.save()
        if not institute.is_active:
            LoginSession.objects.filter(user__institute=institute, revoked_at=None).update(
                revoked_at=timezone.now()
            )
        platform_audit(self.request.user, institute, "institute-update", "Institute", institute.pk)

    @action(detail=True, methods=["get"])
    def usage(self, request, pk=None):
        institute = self.get_object()
        return Response(
            {
                "students": StudentProfile.objects.filter(institute=institute).count(),
                "users": User.objects.filter(institute=institute).count(),
                "storage_bytes": FileAsset.objects.filter(institute=institute).aggregate(
                    value=Sum("size")
                )["value"]
                or 0,
            }
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def admin_status(self, request, pk=None):
        institute = self.get_object()

        class StatusInput(serializers.Serializer):
            admin = serializers.IntegerField(min_value=1)
            status = serializers.ChoiceField(choices=[AccountStatus.ACTIVE, AccountStatus.DISABLED])

        data = StatusInput(data=request.data)
        data.is_valid(raise_exception=True)
        user = get_object_or_404(
            User, pk=data.validated_data["admin"], institute=institute, role=Role.ADMIN
        )
        if data.validated_data["status"] == AccountStatus.ACTIVE and not user.has_usable_password():
            raise ValidationError("Complete activation before enabling this account.")
        user.status = data.validated_data["status"]
        user.save(update_fields=["status"])
        LoginSession.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
        platform_audit(request.user, institute, "admin-status", "User", user.pk)
        return Response({"detail": "Admin access updated."})

    @action(detail=True, methods=["patch"], url_path=r"admin_accounts/(?P<admin_id>[0-9]+)")
    @transaction.atomic
    def edit_admin(self, request, pk=None, admin_id=None):
        institute = self.get_object()
        user = get_object_or_404(
            User.objects.select_for_update(), pk=admin_id, institute=institute, role=Role.ADMIN
        )
        serializer = AdminAccountSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        platform_audit(request.user, institute, "admin-update", "User", user.pk)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def admin_recovery(self, request, pk=None):
        institute = self.get_object()
        admin_id = serializers.IntegerField(min_value=1).run_validation(request.data.get("admin"))
        user = get_object_or_404(User, pk=admin_id, institute=institute, role=Role.ADMIN)
        # Links must use the institute's verified host, never the operator host.
        domain = institute.domains.filter(is_active=True, is_verified=True).first()
        if (
            not domain
            or not user.email
            or not institute.is_active
            or user.status == AccountStatus.DISABLED
        ):
            raise ValidationError(
                "An active institute domain and enabled Admin recovery email are required."
            )
        from django.conf import settings
        from django.core.mail import send_mail

        from accounts.tokens import activation_tokens, reset_tokens

        purpose = "activate" if user.status == AccountStatus.PENDING else "reset"
        generator = activation_tokens if purpose == "activate" else reset_tokens
        token = generator.make_token(user)
        url = f"https://{domain.hostname}/account/{purpose}#uid={user.pk}&token={token}"
        subject = (
            "Activate your GrowthSathi Admin Account"
            if purpose == "activate"
            else "Reset your GrowthSathi Admin Password"
        )
        send_mail(subject, url, settings.DEFAULT_FROM_EMAIL, [user.email])
        platform_audit(request.user, institute, "admin-recovery", "User", user.pk)
        return Response({"detail": "Recovery instructions sent."})


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name", "student_limit", "storage_limit_mb", "billing_cycle"]


class PlanViewSet(viewsets.ModelViewSet):
    permission_classes = [PlatformOperator]
    queryset = Plan.objects.all().order_by("pk")
    serializer_class = PlanSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]


class DomainSerializer(serializers.ModelSerializer):
    institute_name = serializers.CharField(source="institute.name", read_only=True)

    class Meta:
        model = InstituteDomain
        fields = ["id", "institute", "institute_name", "hostname", "is_verified", "is_active"]


class DomainViewSet(viewsets.ModelViewSet):
    permission_classes = [PlatformOperator]
    queryset = InstituteDomain.objects.all().order_by("pk")
    serializer_class = DomainSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        domain = serializer.save()
        platform_audit(
            self.request.user, domain.institute, "domain-create", "InstituteDomain", domain.pk
        )

    def perform_update(self, serializer):
        domain = serializer.save()
        platform_audit(
            self.request.user, domain.institute, "domain-update", "InstituteDomain", domain.pk
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    institute_name = serializers.CharField(source="institute.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = InstituteSubscription
        fields = [
            "id",
            "institute",
            "plan",
            "starts_on",
            "ends_on",
            "status",
            "student_limit",
            "storage_limit_mb",
            "payment_note",
            "institute_name",
            "plan_name",
        ]


class SubscriptionViewSet(viewsets.ModelViewSet):
    permission_classes = [PlatformOperator]
    queryset = InstituteSubscription.objects.select_related("plan").all().order_by("pk")
    serializer_class = SubscriptionSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        item = serializer.save()
        platform_audit(
            self.request.user,
            item.institute,
            "subscription-create",
            "InstituteSubscription",
            item.pk,
        )

    def perform_update(self, serializer):
        item = serializer.save()
        platform_audit(
            self.request.user,
            item.institute,
            "subscription-update",
            "InstituteSubscription",
            item.pk,
        )
