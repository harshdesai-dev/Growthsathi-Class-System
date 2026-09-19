import os
import secrets
from types import SimpleNamespace
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from accounts.backends import TenantBackend
from accounts.models import AccountStatus, Role, StudentProfile, User
from accounts.permissions import ActiveTenantUser, PlatformOperator
from institutes.middleware import TenantContextMiddleware
from institutes.models import Institute, InstituteDomain


@skipUnless(os.getenv("RUN_DATABASE_TESTS", "").lower() == "true", "Requires PostgreSQL")
class IdentityDatabaseTests(TestCase):
    databases = {"default"} if os.getenv("RUN_DATABASE_TESTS", "").lower() == "true" else set()

    @classmethod
    def setUpTestData(cls):
        cls.a = Institute.objects.create(name="Success Academy", slug="success")
        cls.b = Institute.objects.create(name="Bright Classes", slug="bright")
        cls.password = secrets.token_urlsafe(32)
        cls.alice = User.objects.create_user(
            "Alice",
            cls.password,
            institute=cls.a,
            role=Role.STUDENT,
            status=AccountStatus.ACTIVE,
            full_name="Demo Student",
            email="family@example.invalid",
        )
        cls.other = User.objects.create_user(
            "Alice",
            cls.password,
            institute=cls.b,
            role=Role.STUDENT,
            status=AccountStatus.ACTIVE,
            full_name="Other Student",
            email="family@example.invalid",
        )

    def test_tenant_local_username_and_shared_contacts(self):
        self.assertNotEqual(self.alice.pk, self.other.pk)
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                " ALICE ", self.password, institute=self.a, role=Role.STUDENT, full_name="Duplicate"
            )
        User.objects.create_user(
            "sibling",
            self.password,
            institute=self.a,
            role=Role.STUDENT,
            full_name="Sibling",
            email="family@example.invalid",
        )

    def test_database_rejects_duplicate_username_even_bypassing_save(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(username="alice", institute=self.a, role=Role.STUDENT)])

    def test_database_enforces_platform_boundary(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.alice.pk).update(institute=None)

    def test_login_is_bound_to_request_tenant(self):
        backend = TenantBackend()
        request = SimpleNamespace(institute=self.a, platform_context=False)
        self.assertEqual(
            backend.authenticate(request, username="ALICE", password=self.password), self.alice
        )
        request.institute = self.b
        self.assertEqual(
            backend.authenticate(request, username="alice", password=self.password), self.other
        )
        self.assertIsNone(
            backend.authenticate(request, username="alice", password=secrets.token_urlsafe(32))
        )
        request.institute = None
        self.assertIsNone(backend.authenticate(request, username="alice", password=self.password))

    def test_disable_is_checked_on_session_reload(self):
        self.assertIsNotNone(TenantBackend().get_user(self.alice.pk))
        self.a.is_active = False
        self.a.save()
        self.assertIsNone(TenantBackend().get_user(self.alice.pk))
        self.a.is_active = True
        self.a.save()
        self.alice.status = AccountStatus.DISABLED
        self.alice.save()
        self.assertIsNone(TenantBackend().get_user(self.alice.pk))

    def test_profile_relationship_must_match_tenant(self):
        with self.assertRaises(ValidationError):
            StudentProfile.objects.create(institute=self.b, user=self.alice)

    def test_permissions_deny_cross_tenant_and_temporary_password(self):
        request = SimpleNamespace(user=self.alice, institute=self.a, platform_context=False)
        self.assertTrue(ActiveTenantUser().has_permission(request, None))
        self.assertFalse(PlatformOperator().has_permission(request, None))
        request.institute = self.b
        self.assertFalse(ActiveTenantUser().has_permission(request, None))
        request.institute = self.a
        self.alice.must_change_password = True
        self.assertFalse(ActiveTenantUser().has_permission(request, None))

    @override_settings(PLATFORM_HOSTS=["platform.example.invalid"])
    def test_domain_resolution_requires_verification_and_active_institute(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        middleware = TenantContextMiddleware(lambda request: HttpResponse())
        domain = InstituteDomain.objects.create(institute=self.a, hostname="a.example.invalid")
        with override_settings(ALLOWED_HOSTS=["a.example.invalid"]):
            request = RequestFactory().get("/api/context/", HTTP_HOST="a.example.invalid")
            middleware(request)
            self.assertIsNone(request.institute)
            domain.is_verified = domain.is_active = True
            domain.save()
            response = middleware(request)
            self.assertEqual(request.institute, self.a)
            self.assertIn("no-store", response["Cache-Control"])
            self.a.is_active = False
            self.a.save()
            middleware(request)
            self.assertIsNone(request.institute)
