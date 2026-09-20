from datetime import time, timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academics.models import Enrollment, TeacherAssignment
from accounts.models import Role, User
from announcements.models import Announcement
from attendance.models import AttendanceRecord, AttendanceSession
from exams.models import Exam, ExamScore
from fees.services import create_account, record_payment
from institutes.models import Institute
from notifications.services import announce
from timetable.models import TimetableEntry


class Command(BaseCommand):
    help = "Add operational examples to synthetic demo institutes without replacing records."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo commands require local DEBUG settings.")
        today = timezone.localdate()
        for institute in Institute.objects.filter(slug__in=["success-demo", "bright-demo"]):
            if Announcement.objects.filter(
                institute=institute, title="Synthetic demo welcome"
            ).exists():
                self.stdout.write("Existing demo activity preserved.")
                continue
            admin = User.objects.get(institute=institute, role=Role.ADMIN, username="admin")
            for index, enrollment in enumerate(
                Enrollment.objects.filter(institute=institute, ended_at=None)
            ):
                assignment = TeacherAssignment.objects.filter(
                    batch=enrollment.batch, subject__code="MATH", is_active=True
                ).first()
                TimetableEntry.objects.create(
                    institute=institute,
                    batch=enrollment.batch,
                    subject=assignment.subject,
                    teacher=assignment.teacher,
                    date=today + timedelta(days=1),
                    starts_at=time(9 + index),
                    ends_at=time(10 + index),
                    room=enrollment.batch.room,
                )
                session = AttendanceSession.objects.create(
                    institute=institute,
                    batch=enrollment.batch,
                    subject=assignment.subject,
                    date=today,
                    recorded_by=assignment.teacher.user,
                )
                AttendanceRecord.objects.create(
                    institute=institute,
                    session=session,
                    enrollment=enrollment,
                    status="PRESENT" if index == 0 else "LATE",
                )
                account = create_account(
                    admin,
                    {
                        "registration": enrollment.registration_id,
                        "title": "Synthetic tuition plan",
                        "total_fee": Decimal("10000.00"),
                        "installments": [
                            {"due_date": today, "amount": Decimal("6000.00")},
                            {"due_date": today + timedelta(days=30), "amount": Decimal("4000.00")},
                        ],
                    },
                )
                if index == 0:
                    record_payment(
                        admin,
                        account.pk,
                        {
                            "amount": Decimal("6000.00"),
                            "method": "UPI",
                            "paid_on": today,
                            "reference": "Synthetic example only",
                            "idempotency_key": uuid4(),
                        },
                    )
                for published in [False, True]:
                    exam = Exam.objects.create(
                        institute=institute,
                        name="Demo algebra review" if published else "Demo upcoming unit test",
                        batch=enrollment.batch,
                        subject=assignment.subject,
                        date=today if published else today + timedelta(days=7),
                        starts_at=time(10),
                        total_marks=Decimal("50"),
                        passing_marks=Decimal("20"),
                        published_at=timezone.now() if published else None,
                    )
                    ExamScore.objects.create(
                        institute=institute,
                        exam=exam,
                        enrollment=enrollment,
                        marks=Decimal("42") if published else None,
                    )
            notice = Announcement.objects.create(
                institute=institute,
                title="Synthetic demo welcome",
                message="Fictional training records for exploring class workflows.",
                audience="ALL",
                created_by=admin,
                is_important=True,
            )
            announce(notice)
            self.stdout.write(f"Synthetic activity created for {institute.name}.")
