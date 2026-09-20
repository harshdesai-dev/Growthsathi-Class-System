from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from accounts.models import AccountStatus, Role, User
from institutes.models import InstituteSubscription, Plan
from notifications.models import UserNotification
from tests.test_academic_scopes import AcademicFixture


@override_settings(
    ALLOWED_HOSTS=["a.test", "b.test", "platform.test"], PLATFORM_HOSTS=["platform.test"]
)
class PlatformAndAudienceTests(AcademicFixture):
    def test_announcements_audience_schedule_and_removed_link(self):
        self.client.force_authenticate(self.teacher)
        bad = self.post(
            "announcements/", {"title": "Bad broadcast", "message": "No", "audience": "ALL"}
        )
        self.assertEqual(bad.status_code, 403)
        response = self.post(
            "announcements/",
            {
                "title": "Batch update",
                "message": "Read chapter 1",
                "audience": "BATCH",
                "batch": self.batch.pk,
            },
        )
        self.assertEqual(response.status_code, 201)
        notice = response.json()["id"]
        self.assertFalse(
            UserNotification.objects.filter(user=self.peer, announcement_id=notice).exists()
        )
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(f"announcements/{notice}/").status_code, 200)
        self.assertEqual(self.get("notifications/").json()["count"], 1)
        self.client.force_authenticate(self.parent)
        self.assertEqual(self.get(f"announcements/{notice}/").status_code, 200)
        self.link.is_active = False
        self.link.save()
        self.assertEqual(self.get(f"announcements/{notice}/").status_code, 404)
        self.assertEqual(self.get("notifications/").json()["count"], 0)
        self.client.force_authenticate(self.admin)
        scheduled = self.post(
            "announcements/",
            {
                "title": "Future",
                "message": "Later",
                "audience": "STUDENTS",
                "published_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(scheduled.status_code, 201)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(f"announcements/{scheduled.json()['id']}/").status_code, 404)

    def test_operator_institute_creation_and_separation(self):
        operator = User.objects.create_superuser("operator", self.password, full_name="Operator")
        self.assertEqual(self.get("super-admin/institutes/").status_code, 403)
        self.client.force_authenticate(operator)
        self.assertEqual(self.get("students/").status_code, 403)
        response = self.client.post(
            "/api/super-admin/institutes/",
            {
                "name": "Third Demo",
                "slug": "third",
                "initial_admin": {
                    "username": "owner",
                    "full_name": "Owner",
                    "email": "owner@example.invalid",
                    "role": "ADMIN",
                },
            },
            format="json",
            HTTP_HOST="platform.test",
        )
        self.assertEqual(response.status_code, 201)
        admin = User.objects.get(institute_id=response.json()["id"])
        self.assertEqual(admin.role, Role.ADMIN)
        self.assertEqual(admin.status, AccountStatus.PENDING)
        self.assertFalse(admin.has_usable_password())
        response = self.client.get("/api/students/", HTTP_HOST="platform.test")
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            f"/api/super-admin/institutes/{self.a.pk}/usage/", HTTP_HOST="platform.test"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("names", response.json())

    def test_subscription_student_limit(self):
        plan = Plan.objects.create(name="Pilot", student_limit=2, storage_limit_mb=100)
        InstituteSubscription.objects.create(
            institute=self.a,
            plan=plan,
            starts_on=timezone.localdate(),
            ends_on=timezone.localdate() + timedelta(days=30),
            student_limit=2,
            storage_limit_mb=100,
        )
        response = self.post(
            "users/", {"username": "over-limit", "full_name": "Limit test", "role": "STUDENT"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="over-limit").exists())

    def test_setting_update_cannot_change_institute_status(self):
        response = self.client.patch(
            "/api/settings/",
            {
                "branding": {"is_active": False, "name": "Success Academy Revised"},
                "settings": {"attendance_threshold": 76},
            },
            format="json",
            HTTP_HOST="a.test",
        )
        self.assertEqual(response.status_code, 200)
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_active)
        self.assertEqual(self.a.name, "Success Academy Revised")
