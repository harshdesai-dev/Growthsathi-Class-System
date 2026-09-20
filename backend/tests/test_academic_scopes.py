import secrets
from datetime import date

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from academics.models import (
    AcademicClass,
    AcademicYear,
    Batch,
    ParentStudentLink,
    Subject,
    TeacherAssignment,
)
from academics.services import transfer_student
from accounts.models import AccountStatus, ParentProfile, Role, StudentProfile, TeacherProfile, User
from institutes.models import Institute, InstituteDomain


@override_settings(
    ALLOWED_HOSTS=["a.test", "b.test"],
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class AcademicFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Institute.objects.create(name="Success Academy", slug="success")
        cls.b = Institute.objects.create(name="Bright Classes", slug="bright")
        for institute, host in [(cls.a, "a.test"), (cls.b, "b.test")]:
            InstituteDomain.objects.create(
                institute=institute, hostname=host, is_verified=True, is_active=True
            )
        cls.password = secrets.token_urlsafe(30)

        def user(name, role, institute=cls.a):
            return User.objects.create_user(
                name,
                cls.password,
                institute=institute,
                full_name=name,
                role=role,
                status=AccountStatus.ACTIVE,
            )

        cls.admin = user("admin", Role.ADMIN)
        cls.teacher = user("teacher", Role.TEACHER)
        cls.parent = user("parent", Role.PARENT)
        cls.student = user("student", Role.STUDENT)
        cls.peer = user("peer", Role.STUDENT)
        cls.foreign = user("foreign", Role.STUDENT, cls.b)
        cls.tp = TeacherProfile.objects.create(user=cls.teacher, institute=cls.a)
        cls.pp = ParentProfile.objects.create(user=cls.parent, institute=cls.a)
        cls.sp = StudentProfile.objects.create(user=cls.student, institute=cls.a)
        cls.peer_profile = StudentProfile.objects.create(user=cls.peer, institute=cls.a)
        cls.foreign_profile = StudentProfile.objects.create(user=cls.foreign, institute=cls.b)
        cls.year = AcademicYear.objects.create(
            institute=cls.a, name="2026", starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31)
        )
        cls.academic_class = AcademicClass.objects.create(institute=cls.a, name="Class 12")
        cls.batch = Batch.objects.create(
            institute=cls.a,
            name="Morning",
            academic_year=cls.year,
            academic_class=cls.academic_class,
        )
        cls.next_batch = Batch.objects.create(
            institute=cls.a,
            name="Evening",
            academic_year=cls.year,
            academic_class=cls.academic_class,
        )
        cls.subject = Subject.objects.create(institute=cls.a, name="Maths", code="MATH")
        cls.assignment = TeacherAssignment.objects.create(
            institute=cls.a, teacher=cls.tp, batch=cls.batch, subject=cls.subject
        )
        cls.link = ParentStudentLink.objects.create(institute=cls.a, parent=cls.pp, student=cls.sp)
        transfer_student(cls.admin, cls.sp.pk, cls.batch.pk, "001")
        transfer_student(cls.admin, cls.peer_profile.pk, cls.next_batch.pk, "002")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def get(self, path):
        return self.client.get("/api/" + path, HTTP_HOST="a.test")

    def post(self, path, data):
        return self.client.post("/api/" + path, data, format="json", HTTP_HOST="a.test")


class AcademicScopeTests(AcademicFixture):
    def test_admin_isolation_and_server_assigned_ownership(self):
        self.assertEqual(self.get(f"students/{self.foreign_profile.pk}/").status_code, 404)
        response = self.post(
            "users/",
            {
                "username": "new-student",
                "full_name": "New Student",
                "role": Role.STUDENT,
                "institute": self.b.pk,
            },
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(pk=response.json()["id"])
        self.assertEqual(user.institute_id, self.a.pk)
        self.assertEqual(user.studentprofile.institute_id, self.a.pk)
        self.assertNotIn("password", response.json())
        self.assertEqual(
            self.post(
                "users/", {"username": "bad", "full_name": "Bad", "role": Role.SUPER_ADMIN}
            ).status_code,
            400,
        )

    def test_teacher_loses_access_after_assignment_removal(self):
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get(f"students/{self.sp.pk}/").status_code, 200)
        data = self.get(f"students/{self.sp.pk}/").json()
        self.assertEqual(set(data), {"id", "full_name", "current_enrollment"})
        self.assertEqual(self.get(f"students/{self.peer_profile.pk}/").status_code, 404)
        self.assertEqual(self.get("parents/").status_code, 403)
        self.assertEqual(self.get("users/").status_code, 403)
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.get(f"students/{self.sp.pk}/").status_code, 404)
        self.assertEqual(self.get(f"batches/{self.batch.pk}/").status_code, 404)

    def test_parent_link_removed_and_student_ownership(self):
        self.client.force_authenticate(self.parent)
        self.assertEqual(self.get(f"students/{self.sp.pk}/").status_code, 200)
        self.assertEqual(self.get(f"students/{self.peer_profile.pk}/").status_code, 404)
        self.link.is_active = False
        self.link.save()
        self.assertEqual(self.get(f"students/{self.sp.pk}/").status_code, 404)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(f"students/{self.sp.pk}/").status_code, 200)
        self.assertEqual(self.get(f"students/{self.peer_profile.pk}/").status_code, 404)

    def test_student_and_parent_batch_read_scope(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(f"batches/{self.batch.pk}/").status_code, 200)
        self.assertEqual(self.get(f"batches/{self.next_batch.pk}/").status_code, 404)

        self.client.force_authenticate(self.parent)
        self.assertEqual(self.get(f"batches/{self.batch.pk}/").status_code, 200)
        self.assertEqual(self.get(f"batches/{self.next_batch.pk}/").status_code, 404)

        self.link.is_active = False
        self.link.save()
        self.assertEqual(self.get(f"batches/{self.batch.pk}/").status_code, 404)

    def test_student_and_parent_cannot_mutate_batches(self):
        batch_payload = {
            "name": "Unauthorized Batch",
            "academic_year": self.year.pk,
            "academic_class": self.academic_class.pk,
            "room": "999",
            "is_active": True,
        }

        self.client.force_authenticate(self.student)
        self.assertEqual(self.post("batches/", batch_payload).status_code, 403)

        response = self.client.patch(
            f"/api/batches/{self.batch.pk}/",
            {"name": "Changed by Student"},
            format="json",
            HTTP_HOST="a.test",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.delete(
            f"/api/batches/{self.batch.pk}/",
            HTTP_HOST="a.test",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.parent)
        self.assertEqual(self.post("batches/", batch_payload).status_code, 403)

        response = self.client.patch(
            f"/api/batches/{self.batch.pk}/",
            {"name": "Changed by Parent"},
            format="json",
            HTTP_HOST="a.test",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.delete(
            f"/api/batches/{self.batch.pk}/",
            HTTP_HOST="a.test",
        )
        self.assertEqual(response.status_code, 403)

    def test_transfer_preserves_history_and_changes_teacher_visibility(self):
        previous = self.sp.enrollments.get(ended_at=None)
        response = self.post(
            f"students/{self.sp.pk}/transfer/", {"batch": self.next_batch.pk, "roll_number": "001"}
        )
        self.assertEqual(response.status_code, 200)
        previous.refresh_from_db()
        self.assertIsNotNone(previous.ended_at)
        self.assertEqual(previous.batch_id, self.batch.pk)
        self.assertEqual(self.sp.enrollments.filter(ended_at=None).count(), 1)
        self.assertEqual(self.sp.enrollments.count(), 2)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get(f"students/{self.sp.pk}/").status_code, 404)

    def test_cross_tenant_link_rejected_and_non_admin_transfer_denied(self):
        response = self.post(
            "parent-links/", {"parent": self.pp.pk, "student": self.foreign_profile.pk}
        )
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(self.parent)
        response = self.post(
            f"students/{self.sp.pk}/transfer/", {"batch": self.next_batch.pk, "roll_number": "001"}
        )
        self.assertEqual(response.status_code, 403)

    def test_temporary_password_cannot_access_modules(self):
        self.admin.must_change_password = True
        self.admin.save()
        self.assertEqual(self.get("students/").status_code, 403)
