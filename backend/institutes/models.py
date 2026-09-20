"""Tenant identity; domains must be explicitly verified before routing."""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class Institute(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    contact_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    primary_color = models.CharField(
        max_length=7,
        default="#2563eb",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use a six-digit hex color.")],
    )
    logo = models.FileField(upload_to="branding/", blank=True)
    support_note = models.TextField(blank=True)
    support_status = models.CharField(max_length=30, default="NONE")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class InstituteDomain(models.Model):
    institute = models.ForeignKey(Institute, on_delete=models.PROTECT, related_name="domains")
    hostname = models.CharField(max_length=253, unique=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    def clean(self):
        super().clean()
        self.hostname = self.hostname.strip().lower().rstrip(".")
        labels = self.hostname.split(".")
        import re

        if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in labels):
            raise ValidationError({"hostname": "Enter a hostname without scheme, port or path."})
        if self.is_active and not self.is_verified:
            raise ValidationError({"is_active": "Verify the domain before activating it."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_active=False) | models.Q(is_verified=True),
                name="active_domain_is_verified",
            ),
            models.CheckConstraint(
                condition=models.Q(hostname=models.functions.Lower("hostname")),
                name="domain_hostname_lowercase",
            ),
        ]


class TenantModel(models.Model):
    """Validate explicit tenant ownership on all immediate tenant relationships.

    Services must also scope lookups and own transactions. Bulk writes bypass
    model validation and must not be used for unvalidated client relationships.
    """

    institute = models.ForeignKey(Institute, on_delete=models.PROTECT)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        errors = {}
        for field in self._meta.fields:
            if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            if field.name == "institute" or not getattr(self, field.attname):
                continue
            related = getattr(self, field.name)
            if hasattr(related, "institute_id") and related.institute_id != self.institute_id:
                errors[field.name] = "Related record must belong to the same institute."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class InstituteSettings(TenantModel):
    attendance_threshold = models.PositiveSmallIntegerField(default=75)
    default_passing_percentage = models.PositiveSmallIntegerField(default=40)
    working_days = models.JSONField(default=list, blank=True)
    fee_due_day = models.PositiveSmallIntegerField(default=10)
    absence_alerts = models.BooleanField(default=True)
    show_rank = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["institute"], name="one_settings_per_institute"),
            models.CheckConstraint(
                condition=models.Q(
                    attendance_threshold__lte=100,
                    default_passing_percentage__lte=100,
                    fee_due_day__gte=1,
                    fee_due_day__lte=28,
                ),
                name="settings_ranges_valid",
            ),
        ]


class Plan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    student_limit = models.PositiveIntegerField(default=200)
    storage_limit_mb = models.PositiveIntegerField(default=1024)
    billing_cycle = models.CharField(
        max_length=10, choices=[("MONTHLY", "Monthly"), ("YEARLY", "Yearly")], default="MONTHLY"
    )


class InstituteSubscription(TenantModel):
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(
        max_length=12,
        choices=[("ACTIVE", "Active"), ("EXPIRED", "Expired"), ("CANCELLED", "Cancelled")],
        default="ACTIVE",
    )
    student_limit = models.PositiveIntegerField()
    storage_limit_mb = models.PositiveIntegerField()
    payment_note = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["institute"], name="one_subscription_per_institute"),
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="subscription_dates_ordered",
            ),
        ]
