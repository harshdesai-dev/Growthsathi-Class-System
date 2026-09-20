import csv
import io
from decimal import Decimal
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone

from common.reports import csv_report
from tests.test_academic_scopes import AcademicFixture


class CsvSafetyTests(SimpleTestCase):
    def test_formula_cells_are_escaped_and_private(self):
        response = csv_report(
            "test", ["Value"], [[" =SUM(A1:A2)"], ["@command"], ["normal"], [None]]
        )
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[1:], [["' =SUM(A1:A2)"], ["'@command"], ["normal"], [""]])
        self.assertEqual(response["Cache-Control"], "private, no-store")


class ReportScopeTests(AcademicFixture):
    def test_fee_summary_decimal_balance_and_reminder_permissions(self):
        result = self.post(
            "fees/",
            {
                "registration": self.sp.registrations.get().pk,
                "title": "Tuition",
                "total_fee": "1000.10",
                "installments": [{"due_date": str(timezone.localdate()), "amount": "1000.10"}],
            },
        )
        self.assertEqual(result.status_code, 201)
        account = result.json()["id"]
        self.assertEqual(
            self.post(
                f"fees/{account}/payment/",
                {
                    "amount": "100.01",
                    "paid_on": str(timezone.localdate()),
                    "method": "CASH",
                    "idempotency_key": str(uuid4()),
                },
            ).status_code,
            200,
        )
        summary = self.get("fees/summary/").json()
        self.assertEqual(Decimal(summary["Pending"]), Decimal("900.09"))
        self.assertEqual(self.post(f"fees/{account}/remind/", {}).status_code, 200)
        report = self.get("fees/report/")
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"900.09", report.content)
        for user in [self.student, self.parent]:
            self.client.force_authenticate(user)
            self.assertEqual(
                Decimal(self.get("fees/summary/").json()["Pending"]), Decimal("900.09")
            )
            self.assertEqual(self.get("fees/report/").status_code, 403)
            self.assertEqual(self.post(f"fees/{account}/remind/", {}).status_code, 403)
        self.link.is_active = False
        self.link.save()
        self.assertEqual(Decimal(self.get("fees/summary/").json()["Pending"]), 0)
        self.client.force_authenticate(self.teacher)
        for path in ["fees/summary/", "fees/report/"]:
            self.assertEqual(self.get(path).status_code, 403)
        self.assertEqual(self.post(f"fees/{account}/remind/", {}).status_code, 403)

    def test_attendance_export_and_summary_recheck_assignment(self):
        self.assertEqual(
            self.post(
                "attendance/record/",
                {
                    "batch": self.batch.pk,
                    "subject": self.subject.pk,
                    "date": str(timezone.localdate()),
                    "records": [{"student": self.sp.pk, "status": "ABSENT"}],
                },
            ).status_code,
            200,
        )
        self.client.force_authenticate(self.teacher)
        report = self.get("attendance/report/")
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"ABSENT", report.content)
        self.assertEqual(self.get("attendance/summary/").json()["total"], 1)
        self.assignment.is_active = False
        self.assignment.save()
        self.assertNotIn(b"ABSENT", self.get("attendance/report/").content)
        self.assertEqual(self.get("attendance/summary/").json()["total"], 0)
        for user in [self.student, self.parent]:
            self.client.force_authenticate(user)
            self.assertEqual(self.get("attendance/report/").status_code, 403)
            self.assertEqual(self.get("results/report/").status_code, 403)
