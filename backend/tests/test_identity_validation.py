from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from accounts.backends import TenantBackend
from accounts.models import AccountStatus, Role, StudentProfile, User, normalize_username
from institutes.models import Institute, InstituteDomain


class IdentityValidationTests(SimpleTestCase):
    def test_normalized_username(self):
        self.assertEqual(normalize_username("  ALICE.Example  "), "alice.example")
        self.assertEqual(normalize_username("Alice"), "alice")

    def test_tenant_role_boundary(self):
        for role, institute_id in [(Role.ADMIN, None), (Role.SUPER_ADMIN, 1)]:
            with self.subTest(role=role), self.assertRaises(ValidationError):
                User(username="alice", role=role, institute_id=institute_id).clean()

    def test_profile_rejects_cross_tenant_and_wrong_role(self):
        student = User(pk=1, institute_id=1, role=Role.STUDENT)
        with self.assertRaises(ValidationError):
            StudentProfile(user=student, institute_id=2).clean()
        teacher = User(pk=2, institute_id=1, role=Role.TEACHER)
        with self.assertRaises(ValidationError):
            StudentProfile(user=teacher, institute_id=1).clean()

    def test_domain_validation(self):
        domain = InstituteDomain(hostname=" SCHOOL.Example. ")
        domain.clean()
        self.assertEqual(domain.hostname, "school.example")
        for hostname in [
            "https://school.example",
            "school.example/path",
            "school.example:8000",
            "-bad.example",
        ]:
            with self.subTest(hostname=hostname), self.assertRaises(ValidationError):
                InstituteDomain(hostname=hostname).clean()
        with self.assertRaises(ValidationError):
            InstituteDomain(hostname="school.example", is_active=True).clean()

    def test_no_context_cannot_authenticate(self):
        self.assertIsNone(
            TenantBackend().authenticate(None, username="alice", password="irrelevant")
        )
        with patch.object(User, "set_password"):
            self.assertIsNone(
                TenantBackend().authenticate(
                    SimpleNamespace(), username="alice", password="irrelevant"
                )
            )

    def test_inactive_account_property(self):
        self.assertFalse(User(status=AccountStatus.PENDING).is_active)
        self.assertFalse(User(status=AccountStatus.DISABLED).is_active)
        self.assertTrue(User(status=AccountStatus.ACTIVE).is_active)

    def test_contacts_are_not_unique(self):
        self.assertFalse(User._meta.get_field("email").unique)
        self.assertFalse(User._meta.get_field("phone").unique)
        self.assertFalse(User._meta.get_field("username").unique)

    def test_disabled_institute_cannot_authenticate(self):
        request = SimpleNamespace(
            institute=Institute(pk=1, is_active=False), platform_context=False
        )
        with patch.object(User, "set_password"):
            self.assertIsNone(
                TenantBackend().authenticate(request, username="alice", password="irrelevant")
            )
