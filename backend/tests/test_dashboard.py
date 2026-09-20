from accounts.models import Role
from tests.test_academic_scopes import AcademicFixture


class DashboardTests(AcademicFixture):
    def test_teacher_dashboard_has_no_financial_data(self):
        self.client.force_authenticate(self.teacher)
        response = self.get("dashboard/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["Students"], 1)
        self.assertEqual(data["Batches"], 1)
        self.assertFalse(any("fee" in key.lower() for key in data))
        self.assertNotIn("fees", [row["module"] for row in data["sections"]])

    def test_parent_dashboard_requires_link_for_selected_child(self):
        self.client.force_authenticate(self.parent)
        self.assertEqual(self.get(f"dashboard/?student={self.peer_profile.pk}").status_code, 404)
        data = self.get(f"dashboard/?student={self.sp.pk}").json()
        self.assertEqual(data["Linked records"], 1)
        self.assertEqual(data["Batches"], 1)
        self.assertNotIn("timetable", [row["module"] for row in data["sections"]])
        self.link.is_active = False
        self.link.save()
        self.assertEqual(self.get(f"dashboard/?student={self.sp.pk}").status_code, 404)

    def test_dashboard_scopes_counts_and_rejects_foreign_student(self):
        self.assertEqual(self.get("dashboard/").json()["Students"], 2)
        self.assertEqual(self.get(f"dashboard/?student={self.foreign_profile.pk}").status_code, 404)
        self.client.force_authenticate(self.student)
        data = self.get("dashboard/").json()
        self.assertEqual(data["Linked records"], 1)
        self.assertEqual(self.student.role, Role.STUDENT)
