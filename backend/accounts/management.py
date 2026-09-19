from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from audit.models import AuditLog
from common.api import AdminResourceViewSet

from .models import (
    AccountStatus,
    AdminProfile,
    LoginSession,
    ParentProfile,
    Role,
    StudentProfile,
    TeacherProfile,
    User,
)
from .views import send_account_link


class UserSerializer(serializers.ModelSerializer):
    temporary_password = serializers.CharField(
        write_only=True, required=False, max_length=256, trim_whitespace=False
    )
    profile_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "email",
            "phone",
            "role",
            "status",
            "last_login",
            "must_change_password",
            "temporary_password",
            "profile_id",
        ]
        read_only_fields = ["id", "status", "last_login", "must_change_password"]

    def get_profile_id(self, user):
        relation = {
            Role.ADMIN: "adminprofile",
            Role.TEACHER: "teacherprofile",
            Role.STUDENT: "studentprofile",
            Role.PARENT: "parentprofile",
        }.get(user.role)
        profile = getattr(user, relation, None) if relation else None
        return profile.pk if profile else None

    def validate_role(self, value):
        if value == Role.SUPER_ADMIN or (self.instance and value != self.instance.role):
            raise serializers.ValidationError("Role cannot be changed or elevated.")
        return value

    def validate(self, attrs):
        if self.instance and "temporary_password" in attrs:
            raise serializers.ValidationError("Use account recovery to reset a password.")
        if "temporary_password" in attrs:
            validate_password(
                attrs["temporary_password"],
                User(**{k: v for k, v in attrs.items() if k != "temporary_password"}),
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("temporary_password", None)
        user = User.objects.create_user(
            password=password,
            status=AccountStatus.ACTIVE if password else AccountStatus.PENDING,
            must_change_password=bool(password),
            **validated_data,
        )
        profile = {
            Role.ADMIN: AdminProfile,
            Role.TEACHER: TeacherProfile,
            Role.STUDENT: StudentProfile,
            Role.PARENT: ParentProfile,
        }[user.role]
        profile.objects.create(user=user, institute_id=user.institute_id)
        return user


class UserViewSet(AdminResourceViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    search_fields = ["username", "full_name", "email", "phone"]

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        return qs.filter(role=role) if role in Role.values else qs

    @transaction.atomic
    def perform_create(self, serializer):
        from institutes.models import Institute, InstituteSubscription

        Institute.objects.select_for_update().get(pk=self.request.user.institute_id)
        subscription = InstituteSubscription.objects.filter(
            institute_id=self.request.user.institute_id
        ).first()
        if (
            serializer.validated_data.get("role") == Role.STUDENT
            and subscription
            and StudentProfile.objects.filter(institute_id=self.request.user.institute_id).count()
            >= subscription.student_limit
        ):
            raise ValidationError("Student limit reached. Contact GrowthSathi support.")
        user = serializer.save(institute_id=self.request.user.institute_id)
        self.record(user, "account-create")

    def record(self, user, action_name):
        AuditLog.objects.create(
            institute_id=user.institute_id,
            actor=self.request.user,
            action=action_name,
            entity="User",
            entity_id=str(user.pk),
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def status(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise ValidationError("You cannot disable your own account.")
        status = request.data.get("status")
        if status not in (AccountStatus.ACTIVE, AccountStatus.DISABLED):
            raise ValidationError({"status": "Choose ACTIVE or DISABLED."})
        if status == AccountStatus.ACTIVE and not user.has_usable_password():
            raise ValidationError("Send an activation link before enabling this account.")
        user.status = status
        user.save(update_fields=["status"])
        LoginSession.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
        self.record(user, "account-" + status.lower())
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def recovery(self, request, pk=None):
        user = self.get_object()
        if not user.email or user.status == AccountStatus.DISABLED:
            raise ValidationError("An enabled account with a recovery email is required.")
        send_account_link(
            request, user, "activate" if user.status == AccountStatus.PENDING else "reset"
        )
        self.record(user, "account-recovery-request")
        return Response({"detail": "Account instructions sent."})
