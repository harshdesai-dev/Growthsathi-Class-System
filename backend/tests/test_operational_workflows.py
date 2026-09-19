from datetime import time
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from academics.models import Subject
from academics.scopes import require_teaching_scope
from academics.services import transfer_student
from attendance.models import AttendanceRecord
from fees.models import FeePayment
from fees.services import total_paid
from tests.test_academic_scopes import AcademicFixture


class OperationalWorkflowTests(AcademicFixture):
    def account(self):
        registration = self.sp.registrations.get()
        response = self.post(
            "fees/",
            {
                "registration": registration.pk,
                "title": "Tuition",
                "total_fee": "1000.00",
                "installments": [
                    {"due_date": str(timezone.localdate()), "amount": "600.00"},
                    {"due_date": str(timezone.localdate()), "amount": "400.00"},
                ],
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def test_payment_allocation_idempotency_reversal_and_role_visibility(self):
        account = self.account()
        payload = {
            "amount": "700.00",
            "paid_on": str(timezone.localdate()),
            "method": "CASH",
            "idempotency_key": str(uuid4()),
        }
        response = self.post(f"fees/{account}/payment/", payload)
        self.assertEqual(response.status_code, 200)
        payment_id = response.json()["id"]
        self.assertEqual(self.post(f"fees/{account}/payment/", payload).json()["id"], payment_id)
        payment = FeePayment.objects.get(pk=payment_id)
        self.assertEqual(
            list(payment.allocations.order_by("pk").values_list("amount", flat=True)),
            [Decimal("600.00"), Decimal("100.00")],
        )
        self.assertEqual(total_paid(payment.account), Decimal("700.00"))
        payload["amount"] = "800.00"
        self.assertEqual(self.post(f"fees/{account}/payment/", payload).status_code, 400)
        payload["idempotency_key"] = str(uuid4())
        self.assertEqual(self.post(f"fees/{account}/payment/", payload).status_code, 400)
        for user in [self.student, self.parent]:
            self.client.force_authenticate(user)
            self.assertEqual(self.get(f"fees/{account}/").status_code, 200)
            self.assertEqual(self.get(f"fees/{account}/receipt/{payment_id}/").status_code, 200)
            self.assertEqual(self.post(f"fees/{account}/payment/", payload).status_code, 403)
        self.client.force_authenticate(self.teacher)
        for path in ["fees/", f"fees/{account}/", f"fees/{account}/receipt/{payment_id}/"]:
            self.assertEqual(self.get(path).status_code, 403)
        self.client.force_authenticate(self.peer)
        self.assertEqual(self.get(f"fees/{account}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        response = self.post(
            f"fees/{account}/reverse/", {"payment": payment_id, "reason": "Duplicate cash entry"}
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(total_paid(payment.account), Decimal("0"))
        self.assertEqual(payment.allocations.count(), 2)

    def test_fee_plan_total_validation(self):
        response = self.post(
            "fees/",
            {
                "registration": self.sp.registrations.get().pk,
                "title": "Invalid",
                "total_fee": "1000.00",
                "installments": [{"due_date": str(timezone.localdate()), "amount": "999.99"}],
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_attendance_end_to_end_and_historical_context(self):
        self.client.force_authenticate(self.teacher)
        payload = {
            "batch": self.batch.pk,
            "subject": self.subject.pk,
            "date": str(timezone.localdate()),
            "records": [{"student": self.sp.pk, "status": "LATE"}],
        }
        self.assertEqual(self.post("attendance/record/", payload).status_code, 200)
        row = AttendanceRecord.objects.get()
        for user in [self.admin, self.student, self.parent]:
            self.client.force_authenticate(user)
            self.assertEqual(self.get("attendance/summary/").json()["percentage"], 100.0)
        self.client.force_authenticate(self.peer)
        self.assertEqual(self.get("attendance/").json()["count"], 0)
        transfer_student(self.admin, self.sp.pk, self.next_batch.pk, "001")
        row.refresh_from_db()
        self.assertEqual(row.enrollment.batch_id, self.batch.pk)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get("attendance/").json()["count"], 1)
        self.assertEqual(self.post("attendance/record/", payload).status_code, 403)

    def test_wrong_batch_subject_and_removed_assignment(self):
        other_subject = Subject.objects.create(institute=self.a, name="Physics", code="PHY")
        with self.assertRaises(PermissionDenied):
            require_teaching_scope(self.teacher, self.batch, other_subject)
        self.client.force_authenticate(self.teacher)
        payload = {
            "batch": self.next_batch.pk,
            "subject": self.subject.pk,
            "date": str(timezone.localdate()),
            "records": [{"student": self.peer_profile.pk, "status": "PRESENT"}],
        }
        self.assertEqual(self.post("attendance/record/", payload).status_code, 403)
        payload["batch"] = self.batch.pk
        payload["records"][0]["student"] = self.foreign_profile.pk
        self.assertEqual(self.post("attendance/record/", payload).status_code, 400)
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.post("attendance/record/", payload).status_code, 403)

    def test_timetable_conflict_and_teacher_read_only(self):
        payload = {
            "batch": self.batch.pk,
            "subject": self.subject.pk,
            "teacher": self.tp.pk,
            "date": str(timezone.localdate()),
            "starts_at": str(time(9)),
            "ends_at": str(time(10)),
            "room": "101",
        }
        response = self.post("timetable/", payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post("timetable/", payload).status_code, 400)
        payload["starts_at"], payload["ends_at"] = "10:00", "11:00"
        self.assertEqual(self.post("timetable/", payload).status_code, 201)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get("timetable/").json()["count"], 2)
        self.assertEqual(self.post("timetable/", payload).status_code, 403)

    def test_unpaid_plan_revision_and_paid_history_lock(self):
        account = self.account()
        values = {
            "title": "Revised",
            "total_fee": "1200.00",
            "installments": [{"due_date": str(timezone.localdate()), "amount": "1200.00"}],
        }
        response = self.client.patch(
            f"/api/fees/{account}/", values, format="json", HTTP_HOST="a.test"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["balance"], "1200.00")
        self.post(
            f"fees/{account}/payment/",
            {
                "amount": "100.00",
                "paid_on": str(timezone.localdate()),
                "method": "CASH",
                "idempotency_key": str(uuid4()),
            },
        )
        response = self.client.patch(
            f"/api/fees/{account}/", values, format="json", HTTP_HOST="a.test"
        )
        self.assertEqual(response.status_code, 400)

    def test_teacher_attendance_is_admin_managed_and_self_readable(self):
        response = self.post(
            "teacher-attendance/",
            {"teacher": self.tp.pk, "date": str(timezone.localdate()), "status": "PRESENT"},
        )
        self.assertEqual(response.status_code, 201)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get("teacher-attendance/").json()["count"], 1)
        self.assertEqual(
            self.post(
                "teacher-attendance/",
                {"teacher": self.tp.pk, "date": str(timezone.localdate()), "status": "ABSENT"},
            ).status_code,
            403,
        )
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get("teacher-attendance/").status_code, 403)

    def test_timetable_date_window_validation_and_assignment_removal(self):
        payload = {
            "batch": self.batch.pk,
            "teacher": self.tp.pk,
            "subject": self.subject.pk,
            "date": "2026-09-20",
            "starts_at": "09:00",
            "ends_at": "10:00",
            "room": "101",
        }
        self.assertEqual(self.post("timetable/", payload).status_code, 201)
        self.assertEqual(
            self.get("timetable/?date_from=2026-09-21&date_to=2026-09-27").json()["count"], 0
        )
        self.assertEqual(
            self.get("timetable/?date_from=2026-09-14&date_to=2026-09-20").json()["count"], 1
        )
        self.assertEqual(self.get("timetable/?date_from=invalid").status_code, 400)
        self.assertEqual(
            self.get("timetable/?date_from=2026-09-21&date_to=2026-09-20").status_code, 400
        )
        self.client.force_authenticate(self.teacher)
        self.assertEqual(
            self.get("timetable/?date_from=2026-09-14&date_to=2026-09-20").json()["count"], 1
        )
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(
            self.get("timetable/?date_from=2026-09-14&date_to=2026-09-20").json()["count"], 0
        )

    def test_attendance_roster_preserves_saved_status_and_historical_membership(self):
        today = str(timezone.localdate())
        self.assertEqual(
            self.post(
                "attendance/record/",
                {
                    "batch": self.batch.pk,
                    "subject": self.subject.pk,
                    "date": today,
                    "records": [{"student": self.sp.pk, "status": "LATE", "remark": "Bus delay"}],
                },
            ).status_code,
            200,
        )
        transfer_student(self.admin, self.sp.pk, self.next_batch.pk, "001")
        url = f"attendance/roster/?batch={self.batch.pk}&subject={self.subject.pk}&date={today}"
        rows = self.get(url).json()
        self.assertEqual(
            rows,
            [
                {
                    "id": self.sp.pk,
                    "full_name": self.student.full_name,
                    "status": "LATE",
                    "remark": "Bus delay",
                }
            ],
        )
        self.client.force_authenticate(self.student)
        self.assertEqual(self.get(url).status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.get(url).status_code, 200)
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.get(url).status_code, 403)
