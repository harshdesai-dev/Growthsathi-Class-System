import secrets

from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import AccountStatus, LoginSession, Role, User
from accounts.tokens import activation_tokens, reset_tokens
from accounts.views import send_account_link
from institutes.models import Institute, InstituteDomain


@override_settings(
    ALLOWED_HOSTS=[
        "a.test",
        "b.test",
        "backend.test",
        "platform.test",
        "unknown.test",
    ],
    PLATFORM_HOSTS=["platform.test"],
    PROXY_TENANT_SECRET="test-proxy-secret",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class AuthWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Institute.objects.create(name="Success Academy", slug="success")
        cls.b = Institute.objects.create(name="Bright Classes", slug="bright")
        for institute, hostname in [(cls.a, "a.test"), (cls.b, "b.test")]:
            InstituteDomain.objects.create(
                institute=institute, hostname=hostname, is_active=True, is_verified=True
            )
        cls.password = secrets.token_urlsafe(30)
        cls.user = User.objects.create_user(
            "demo",
            cls.password,
            institute=cls.a,
            role=Role.ADMIN,
            full_name="Demo Admin",
            status=AccountStatus.ACTIVE,
            email="family@example.invalid",
        )
        cls.other = User.objects.create_user(
            "demo",
            cls.password,
            institute=cls.b,
            role=Role.ADMIN,
            full_name="Other Admin",
            status=AccountStatus.ACTIVE,
        )
        cls.operator = User.objects.create_superuser("operator", cls.password, full_name="Operator")

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.host = "a.test"
        self.csrf()

    def csrf(self):
        response = self.client.get(
            "/api/auth/context/",
            HTTP_HOST=self.host,
            secure=True,
            **getattr(self, "forwarded_headers", {}),
        )
        self.csrf_token = response.json().get("csrfToken", "")
        return response

    def post(self, path, payload=None, host=None, forwarded_headers=None):
        return self.client.post(
            "/api/auth/" + path,
            payload or {},
            format="json",
            HTTP_HOST=host or self.host,
            HTTP_ORIGIN="https://" + (host or self.host),
            HTTP_X_CSRFTOKEN=self.csrf_token,
            secure=True,
            **(
                forwarded_headers
                or getattr(self, "forwarded_headers", {})
            ),
        )

    def login(self, username="demo"):
        response = self.post("login/", {"username": username, "password": self.password})
        if response.status_code == 200:
            self.csrf_token = response.json()["csrfToken"]
        return response

    def me(self):
        return self.client.get("/api/auth/me/", HTTP_HOST=self.host, secure=True)

    def test_cookie_login_context_rotation_and_logout(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access", response.json())
        for name in ["gs_access", "gs_refresh"]:
            self.assertTrue(response.cookies[name]["httponly"])
            self.assertTrue(response.cookies[name]["secure"])
            self.assertEqual(response.cookies[name]["domain"], "")
        self.assertEqual(self.me().json()["id"], self.user.pk)
        old_refresh = self.client.cookies["gs_refresh"].value
        old_access = self.client.cookies["gs_access"].value
        self.assertEqual(self.post("refresh/").status_code, 200)
        fresh_refresh = self.client.cookies["gs_refresh"].value
        self.client.cookies["gs_refresh"] = old_refresh
        self.assertEqual(self.post("refresh/").status_code, 401)
        self.client.cookies["gs_refresh"] = fresh_refresh
        self.assertEqual(self.post("logout/").status_code, 200)
        self.client.cookies["gs_access"] = old_access
        self.assertEqual(self.me().status_code, 401)

    def test_csrf_is_required_for_anonymous_login_refresh_and_logout(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "demo", "password": self.password},
            format="json",
            HTTP_HOST=self.host,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.login().status_code, 200)
        for path in ["refresh/", "logout/", "reset/", "password/"]:
            response = self.client.post("/api/auth/" + path, {}, format="json", HTTP_HOST=self.host)
            self.assertEqual(response.status_code, 403)

    def test_cookie_cannot_cross_tenant_or_platform_context(self):
        self.login()
        for host in ["b.test", "platform.test", "unknown.test"]:
            self.host = host
            self.assertEqual(self.me().status_code, 401)
        self.host = "b.test"
        self.csrf()
        self.assertEqual(self.post("refresh/").status_code, 401)

    def test_platform_login_is_separate(self):
        self.assertEqual(self.login("operator").status_code, 401)
        self.host = "platform.test"
        self.csrf()
        self.assertEqual(self.login("operator").status_code, 200)
        self.assertEqual(self.me().json()["role"], Role.SUPER_ADMIN)

    def test_disable_user_and_institute_take_effect_immediately(self):
        self.login()
        self.user.status = AccountStatus.DISABLED
        self.user.save()
        self.assertEqual(self.me().status_code, 401)
        self.assertEqual(self.post("refresh/").status_code, 401)
        self.user.status = AccountStatus.ACTIVE
        self.user.save()
        self.a.is_active = False
        self.a.save()
        self.assertEqual(self.me().status_code, 401)
        self.assertEqual(self.post("refresh/").status_code, 401)

    def test_password_change_revokes_every_session(self):
        self.login()
        self.assertEqual(
            self.post(
                "password/",
                {"current_password": self.password, "password": secrets.token_urlsafe(30)},
            ).status_code,
            200,
        )
        self.assertFalse(LoginSession.objects.filter(user=self.user, revoked_at=None).exists())
        self.assertEqual(self.me().status_code, 401)

    def test_reset_is_single_use_tenant_bound_and_revokes_sessions(self):
        self.login()
        self.user.refresh_from_db()
        token = reset_tokens.make_token(self.user)
        payload = {"uid": self.user.pk, "token": token, "password": secrets.token_urlsafe(30)}
        self.host = "b.test"
        self.csrf()
        self.assertEqual(self.post("reset/confirm/", payload).status_code, 400)
        self.host = "a.test"
        self.csrf()
        self.assertEqual(self.post("reset/confirm/", payload).status_code, 200)
        self.assertEqual(self.post("reset/confirm/", payload).status_code, 400)
        self.assertFalse(LoginSession.objects.filter(user=self.user, revoked_at=None).exists())

    def test_activation_is_single_use_and_purpose_bound(self):
        self.user.status = AccountStatus.PENDING
        self.user.save()
        token = activation_tokens.make_token(self.user)
        payload = {"uid": self.user.pk, "token": token, "password": secrets.token_urlsafe(30)}
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.post("reset/confirm/", payload).status_code, 400)
        self.assertEqual(self.post("activate/", payload).status_code, 200)
        self.assertEqual(self.post("activate/", payload).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_recovery_uses_username_and_generic_response(self):
        existing = self.post("reset/", {"username": "demo"})
        missing = self.post("reset/", {"username": "missing"})
        self.assertEqual(existing.json(), missing.json())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://a.test/account/reset#", mail.outbox[0].body)

    def test_recovery_link_uses_trusted_public_tenant_hostname(self):
        self.forwarded_headers = {
            "HTTP_X_GROWTHSATHI_HOST": "a.test",
            "HTTP_X_GROWTHSATHI_PROXY_SECRET": "test-proxy-secret",
        }
        self.host = "backend.test"
        self.csrf()
        self.post("reset/", {"username": "demo"})
        body = mail.outbox[0].body
        self.assertIn("https://a.test/account/reset#uid=", body)
        self.assertNotIn("https://backend.test/account/reset#", body)

    def test_recovery_link_rejects_untrusted_or_cross_tenant_forwarded_host(self):
        cases = [
            {
                "HTTP_X_GROWTHSATHI_HOST": "b.test",
                "HTTP_X_GROWTHSATHI_PROXY_SECRET": "wrong-secret",
            },
        ]
        for forwarded_headers in cases:
            with self.subTest(forwarded_headers=forwarded_headers):
                mail.outbox.clear()
                self.forwarded_headers = forwarded_headers
                self.host = "a.test"
                self.csrf()
                self.post("reset/", {"username": "demo"})
                body = mail.outbox[0].body
                self.assertIn("https://a.test/account/reset#uid=", body)
                self.assertNotIn("https://b.test/account/reset#", body)
                self.assertNotIn("https://backend.test/account/reset#", body)

    def test_recovery_link_falls_back_for_cross_tenant_public_hostname(self):
        request = RequestFactory().get(
            "/api/auth/reset/",
            HTTP_HOST="backend.test",
            secure=True,
        )
        request.public_hostname = "b.test"
        send_account_link(request, self.user, "reset")
        body = mail.outbox[0].body
        self.assertIn("https://a.test/account/reset#uid=", body)
        self.assertNotIn("https://b.test/account/reset#", body)

    def test_activation_link_uses_tenant_hostname(self):
        pending = User.objects.create_user(
            "pending",
            None,
            institute=self.a,
            role=Role.TEACHER,
            full_name="Pending Teacher",
            status=AccountStatus.PENDING,
            email="pending@example.invalid",
        )
        self.login()
        response = self.client.post(
            f"/api/users/{pending.pk}/recovery/",
            {},
            format="json",
            HTTP_HOST="a.test",
            HTTP_ORIGIN="https://a.test",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("https://a.test/account/activate#uid=", mail.outbox[0].body)

    def test_login_throttled(self):
        for _ in range(10):
            self.post("login/", {"username": "missing", "password": self.password})
        self.assertEqual(
            self.post("login/", {"username": "missing", "password": self.password}).status_code, 429
        )
