"""Username is an institute-local identity, never a contact address."""

import unicodedata
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from institutes.models import TenantModel


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    ADMIN = "ADMIN", "Admin"
    TEACHER = "TEACHER", "Teacher"
    STUDENT = "STUDENT", "Student"
    PARENT = "PARENT", "Parent"


class AccountStatus(models.TextChoices):
    PENDING = "PENDING", "Pending activation"
    ACTIVE = "ACTIVE", "Active"
    DISABLED = "DISABLED", "Disabled"


def normalize_username(value):
    return unicodedata.normalize("NFKC", value).strip().lower()


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        user = self.model(username=normalize_username(username), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        if extra_fields.get("institute") or extra_fields.get("institute_id"):
            raise ValueError("Platform users cannot belong to an institute.")
        extra_fields.update(role=Role.SUPER_ADMIN, status=AccountStatus.ACTIVE)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser):
    institute = models.ForeignKey(
        "institutes.Institute", null=True, blank=True, on_delete=models.PROTECT
    )
    username = models.CharField(
        max_length=150,
        validators=[
            RegexValidator(
                r"^[a-z0-9][a-z0-9._@+-]*$", "Use letters, numbers, dots, @, +, - or underscores."
            )
        ],
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    status = models.CharField(
        max_length=16, choices=AccountStatus.choices, default=AccountStatus.PENDING
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["full_name"]

    @property
    def is_active(self):
        return self.status == AccountStatus.ACTIVE

    def clean(self):
        super().clean()
        self.username = normalize_username(self.username)
        self.email = self.__class__.objects.normalize_email(self.email)
        if (self.role == Role.SUPER_ADMIN) != (self.institute_id is None):
            raise ValidationError({"institute": "Only platform Super Admin has no institute."})

    def save(self, *args, **kwargs):
        self.username = normalize_username(self.username)
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "username"], name="tenant_username_unique"
            ),
            models.UniqueConstraint(
                fields=["username"],
                condition=models.Q(institute=None),
                name="platform_username_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role=Role.SUPER_ADMIN, institute__isnull=True)
                    | (
                        models.Q(role__in=[Role.ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT])
                        & models.Q(institute__isnull=False)
                    )
                ),
                name="user_role_tenant_boundary",
            ),
            models.CheckConstraint(
                condition=models.Q(username=models.functions.Lower("username")),
                name="username_lowercase",
            ),
            models.CheckConstraint(condition=~models.Q(username=""), name="username_required"),
            models.CheckConstraint(
                condition=models.Q(status__in=AccountStatus.values), name="valid_account_status"
            ),
        ]


class RoleProfile(TenantModel):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    address = models.TextField(blank=True)
    expected_role = None

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.user_id and self.user.role != self.expected_role:
            raise ValidationError({"user": "User role does not match this profile."})


class AdminProfile(RoleProfile):
    expected_role = Role.ADMIN


class TeacherProfile(RoleProfile):
    expected_role = Role.TEACHER
    qualification = models.CharField(max_length=200, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    joining_date = models.DateField(null=True, blank=True)


class StudentProfile(RoleProfile):
    expected_role = Role.STUDENT
    date_of_birth = models.DateField(null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)


class ParentProfile(RoleProfile):
    expected_role = Role.PARENT
    emergency_phone = models.CharField(max_length=32, blank=True)


class LoginSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="login_sessions")
    refresh_jti = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AccessAttempt(models.Model):
    # HMAC of context + username/IP; no raw credentials or IP addresses stored.
    key = models.CharField(max_length=64, primary_key=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
