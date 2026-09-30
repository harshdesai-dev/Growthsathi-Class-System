from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import AccountStatus, AdminProfile, Role, User
from accounts.tokens import activation_tokens, reset_tokens
from audit.models import AuditLog
from institutes.models import Institute, InstituteDomain, InstituteSettings


@override_settings(
    ALLOWED_HOSTS=["platform.test", "tenant.test"],
    PLATFORM_HOSTS=["platform.test"],
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class InstituteAdminTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_superuser("operator", full_name="Operator")
        self.client.force_authenticate(self.operator)
        self.institute = Institute.objects.create(
            name="Test Institute", slug="test", email="contact@example.invalid"
        )
        self.admin = User.objects.create_user(
            "owner",
            institute=self.institute,
            role=Role.ADMIN,
            full_name="Owner",
            email="old@example.invalid",
        )
        self.domain = InstituteDomain.objects.create(
            institute=self.institute, hostname="tenant.test", is_active=True, is_verified=True
        )
        self.base = f"/api/super-admin/institutes/{self.institute.pk}/"

    def request(self, method, path, data=None, host="platform.test"):
        return getattr(self.client, method)(path, data, format="json", HTTP_HOST=host)

    def edit(self, data, user=None):
        return self.request("patch", self.base + f"admin_accounts/{(user or self.admin).pk}/", data)

    def payload(self):
        return {
            "name": "New Institute",
            "slug": "new",
            "email": "owner@example.invalid",
            "initial_admin": {"username": "new-owner", "full_name": "New Owner", "role": "ADMIN"},
        }

    def create(self, data):
        return self.request("post", "/api/super-admin/institutes/", data)

    @patch("django.core.mail.send_mail")
    def test_creation_seeds_pending_admin_and_safe_response(self, send):
        response = self.create(self.payload())
        self.assertEqual(response.status_code, 201, response.data)
        institute = Institute.objects.get(pk=response.data["id"])
        user = User.objects.get(institute=institute)
        self.assertEqual(user.email, institute.email)
        self.assertEqual(user.role, Role.ADMIN)
        self.assertEqual(user.status, AccountStatus.PENDING)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(AdminProfile.objects.filter(user=user, institute=institute).exists())
        self.assertTrue(InstituteSettings.objects.filter(institute=institute).exists())
        self.assertEqual(
            set(response.data["admin_accounts"][0]),
            {"id", "username", "full_name", "email", "phone", "status"},
        )
        self.assertTrue(
            AuditLog.objects.filter(institute=institute, action="institute-create").exists()
        )
        send.assert_not_called()

    def test_conflicting_email_rejected_and_matching_email_accepted(self):
        data = self.payload()
        data["initial_admin"]["email"] = "different@example.invalid"
        response = self.create(data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data["initial_admin"])
        self.assertFalse(Institute.objects.filter(slug="new").exists())
        data["initial_admin"]["email"] = data["email"]
        self.assertEqual(self.create(data).status_code, 201)

    def test_missing_blank_invalid_onboarding_email(self):
        for value in (None, "", "not-an-email"):
            with self.subTest(value=value):
                data = self.payload()
                if value is None:
                    del data["email"]
                else:
                    data["email"] = value
                response = self.create(data)
                self.assertEqual(response.status_code, 400)
                self.assertIn("email", response.data)
        self.assertFalse(Institute.objects.filter(slug="new").exists())

    def test_creation_is_atomic(self):
        with patch("institutes.api.InstituteSettings.objects.create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.create(self.payload())
        self.assertFalse(Institute.objects.filter(slug="new").exists())
        self.assertFalse(User.objects.filter(username="new-owner").exists())
        self.assertFalse(AdminProfile.objects.exists())

    def test_edit_fields_audit_and_independent_contact_emails(self):
        password = self.admin.password
        for field, value in (
            ("full_name", "Updated Owner"),
            ("email", "updated@example.invalid"),
            ("phone", "+1 555 0100"),
        ):
            response = self.edit({field: value})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data[field], value)
        self.admin.refresh_from_db()
        self.institute.refresh_from_db()
        self.assertEqual(self.institute.email, "contact@example.invalid")
        self.assertEqual(self.admin.username, "owner")
        self.assertEqual(self.admin.password, password)
        self.assertEqual(self.admin.status, AccountStatus.PENDING)
        self.assertEqual(
            AuditLog.objects.filter(
                actor=self.operator,
                institute=self.institute,
                action="admin-update",
                entity="User",
                entity_id=str(self.admin.pk),
            ).count(),
            3,
        )
        response = self.request("patch", self.base, {"email": "contact2@example.invalid"})
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "updated@example.invalid")
        self.assertEqual(self.request("patch", self.base, {"email": ""}).status_code, 200)

    def test_edit_rejects_forbidden_and_invalid_fields_without_partial_changes(self):
        for field in (
            "password",
            "temporary_password",
            "role",
            "institute",
            "status",
            "permissions",
            "username",
            "id",
            "token",
            "is_superuser",
        ):
            with self.subTest(field=field):
                response = self.edit({field: "SUPER_ADMIN", "full_name": "Must not save"})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        for data in (
            {"email": ""},
            {"email": "invalid"},
            {"email": None},
            {"full_name": ""},
            {"phone": "x" * 33},
        ):
            self.assertEqual(self.edit(data).status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "Owner")
        self.assertFalse(AuditLog.objects.filter(action="admin-update").exists())

    def test_edit_rejects_foreign_admin_and_other_roles(self):
        other = Institute.objects.create(name="Other", slug="other")
        foreign = User.objects.create_user(
            "other", institute=other, role=Role.ADMIN, full_name="Other"
        )
        for user in [foreign, self.operator]:
            self.assertEqual(self.edit({"full_name": "No"}, user).status_code, 404)
        for role in (Role.TEACHER, Role.STUDENT, Role.PARENT):
            user = User.objects.create_user(
                role.lower(), institute=self.institute, role=role, full_name=role
            )
            self.assertEqual(self.edit({"full_name": "No"}, user).status_code, 404)

    def test_platform_permission_and_host_required(self):
        path = self.base + f"admin_accounts/{self.admin.pk}/"
        self.assertEqual(
            self.request("patch", path, {"phone": "1"}, "tenant.test").status_code, 403
        )
        for role in (Role.ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT):
            user = User.objects.create_user(
                role.lower(),
                institute=self.institute,
                role=role,
                full_name=role,
                status=AccountStatus.ACTIVE,
            )
            self.client.force_authenticate(user)
            self.assertEqual(self.edit({"phone": "1"}).status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.edit({"phone": "1"}).status_code, (401, 403))
        self.operator.status = AccountStatus.DISABLED
        self.operator.save()
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.edit({"phone": "1"}).status_code, 403)

    @patch("django.core.mail.send_mail")
    def test_recovery_uses_updated_email_and_correct_token_purpose(self, send):
        for status, generator, purpose, subject in (
            (
                AccountStatus.PENDING,
                activation_tokens,
                "activate",
                "Activate your GrowthSathi Admin Account",
            ),
            (AccountStatus.ACTIVE, reset_tokens, "reset", "Reset your GrowthSathi Admin Password"),
        ):
            with self.subTest(status=status):
                self.admin.status = status
                if status == AccountStatus.ACTIVE:
                    self.admin.set_password("synthetic-password-for-test")
                self.admin.save()
                old_token = generator.make_token(self.admin)
                email = f"{purpose}@example.invalid"
                self.assertEqual(self.edit({"email": email}).status_code, 200)
                self.admin.refresh_from_db()
                self.assertFalse(generator.check_token(self.admin, old_token))
                response = self.request(
                    "post", self.base + "admin_recovery/", {"admin": self.admin.pk}
                )
                self.assertEqual(response.status_code, 200)
                args = send.call_args.args
                self.assertEqual(args[0], subject)
                self.assertEqual(args[3], [email])
                self.assertTrue(
                    args[1].startswith(
                        f"https://tenant.test/account/{purpose}#uid={self.admin.pk}&token="
                    )
                )
                token = args[1].split("&token=")[1]
                self.assertTrue(generator.check_token(self.admin, token))
                self.assertNotIn(token, str(response.data))
                self.assertTrue(
                    AuditLog.objects.filter(
                        action="admin-recovery", entity_id=str(self.admin.pk)
                    ).exists()
                )

    @patch("django.core.mail.send_mail")
    def test_recovery_rejects_disabled_and_unverified_cases(self, send):
        for target, field in (
            (self.admin, "status"),
            (self.institute, "is_active"),
            (self.domain, "is_active"),
        ):
            original = getattr(target, field)
            setattr(target, field, AccountStatus.DISABLED if field == "status" else False)
            target.save()
            self.assertEqual(
                self.request(
                    "post", self.base + "admin_recovery/", {"admin": self.admin.pk}
                ).status_code,
                400,
            )
            setattr(target, field, original)
            target.save()
        send.assert_not_called()

    def test_email_domain_normalization_keeps_initial_emails_equal(self):
        data = self.payload()
        data["email"] = "Owner@EXAMPLE.INVALID"
        response = self.create(data)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["email"], response.data["admin_accounts"][0]["email"])

    def test_admin_edit_and_audit_are_atomic(self):
        with patch("institutes.api.platform_audit", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.edit({"email": "rollback@example.invalid"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "old@example.invalid")

    @patch("django.core.mail.send_mail")
    def test_recovery_rejects_foreign_admin_other_roles_and_missing_email(self, send):
        other = Institute.objects.create(name="Other", slug="other")
        foreign = User.objects.create_user(
            "foreign", institute=other, role=Role.ADMIN, full_name="Other"
        )
        teacher = User.objects.create_user(
            "teacher", institute=self.institute, role=Role.TEACHER, full_name="Teacher"
        )
        for user in (foreign, teacher):
            response = self.request("post", self.base + "admin_recovery/", {"admin": user.pk})
            self.assertEqual(response.status_code, 404)
        self.admin.email = ""
        self.admin.save()
        response = self.request("post", self.base + "admin_recovery/", {"admin": self.admin.pk})
        self.assertEqual(response.status_code, 400)
        send.assert_not_called()
