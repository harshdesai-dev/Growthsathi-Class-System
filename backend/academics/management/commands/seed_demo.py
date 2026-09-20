import json
import secrets
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academics.models import (
    AcademicClass,
    AcademicYear,
    Batch,
    ParentStudentLink,
    Subject,
    TeacherAssignment,
)
from academics.services import transfer_student
from accounts.models import (
    AccountStatus,
    AdminProfile,
    ParentProfile,
    Role,
    StudentProfile,
    TeacherProfile,
    User,
)
from institutes.models import (
    Institute,
    InstituteDomain,
    InstituteSettings,
    InstituteSubscription,
    Plan,
)


class Command(BaseCommand):
    help = "Create synthetic demo data without replacing existing records."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding is permitted only with local DEBUG settings.")
        access_path = settings.BASE_DIR / ".local" / "demo-access.json"
        if (
            access_path.exists()
            or Institute.objects.filter(slug__in=["success-demo", "bright-demo"]).exists()
        ):
            raise CommandError(
                "Demo records or access file already exist. Existing data was preserved."
            )
        credentials = []
        plan = Plan.objects.create(name="Synthetic Pilot", student_limit=100, storage_limit_mb=100)
        for title, slug, host in [
            ("Success Academy", "success-demo", "localhost"),
            ("Bright Classes", "bright-demo", "127.0.0.1"),
        ]:
            institute = Institute.objects.create(name=title, slug=slug)
            InstituteDomain.objects.create(
                institute=institute, hostname=host, is_verified=True, is_active=True
            )
            InstituteSettings.objects.create(institute=institute)
            InstituteSubscription.objects.create(
                institute=institute,
                plan=plan,
                starts_on=timezone.localdate(),
                ends_on=timezone.localdate() + timedelta(days=365),
                student_limit=100,
                storage_limit_mb=100,
            )
            year = AcademicYear.objects.create(
                institute=institute,
                name="2026-27",
                starts_on=date(2026, 4, 1),
                ends_on=date(2027, 3, 31),
                is_current=True,
            )
            academic_class = AcademicClass.objects.create(institute=institute, name="Class 12")
            maths = Subject.objects.create(institute=institute, name="Mathematics", code="MATH")
            physics = Subject.objects.create(institute=institute, name="Physics", code="PHY")
            batches = [
                Batch.objects.create(
                    institute=institute,
                    academic_year=year,
                    academic_class=academic_class,
                    name=name,
                    room=room,
                )
                for name, room in [("Morning", "101"), ("Evening", "102")]
            ]
            profiles = {}
            users = {}
            for username, role, name, status in [
                ("admin", Role.ADMIN, "Demo Administrator", AccountStatus.ACTIVE),
                ("teacher1", Role.TEACHER, "Demo Teacher One", AccountStatus.ACTIVE),
                ("teacher2", Role.TEACHER, "Demo Teacher Two", AccountStatus.ACTIVE),
                ("student1", Role.STUDENT, "Demo Student One", AccountStatus.ACTIVE),
                ("student2", Role.STUDENT, "Demo Student Two", AccountStatus.ACTIVE),
                ("parent1", Role.PARENT, "Demo Parent One", AccountStatus.ACTIVE),
                ("unlinked-parent", Role.PARENT, "Demo Unlinked Parent", AccountStatus.ACTIVE),
                ("disabled-student", Role.STUDENT, "Demo Disabled Student", AccountStatus.DISABLED),
                ("pending-teacher", Role.TEACHER, "Demo Pending Teacher", AccountStatus.PENDING),
            ]:
                password = secrets.token_urlsafe(24)
                user = User.objects.create_user(
                    username,
                    password if status != AccountStatus.PENDING else None,
                    institute=institute,
                    role=role,
                    full_name=name,
                    status=status,
                    email="shared-family@example.invalid",
                )
                model = {
                    Role.ADMIN: AdminProfile,
                    Role.TEACHER: TeacherProfile,
                    Role.STUDENT: StudentProfile,
                    Role.PARENT: ParentProfile,
                }[role]
                profiles[username] = model.objects.create(user=user, institute=institute)
                users[username] = user
                if status == AccountStatus.ACTIVE:
                    credentials.append(
                        {
                            "host": host,
                            "institute": title,
                            "username": username,
                            "role": role,
                            "password": password,
                        }
                    )
            for index, batch in enumerate(batches):
                TeacherAssignment.objects.create(
                    institute=institute,
                    teacher=profiles[f"teacher{index + 1}"],
                    batch=batch,
                    subject=maths,
                )
                TeacherAssignment.objects.create(
                    institute=institute,
                    teacher=profiles[f"teacher{index + 1}"],
                    batch=batch,
                    subject=physics,
                )
                transfer_student(
                    users["admin"],
                    profiles[f"student{index + 1}"].pk,
                    batch.pk,
                    f"DEMO-00{index + 1}",
                )
            ParentStudentLink.objects.create(
                institute=institute,
                parent=profiles["parent1"],
                student=profiles["student1"],
                relationship="Guardian",
            )
        password = secrets.token_urlsafe(24)
        User.objects.create_superuser("demo-operator", password, full_name="Demo Platform Operator")
        credentials.append(
            {
                "host": "platform.localhost",
                "institute": "GrowthSathi",
                "username": "demo-operator",
                "role": Role.SUPER_ADMIN,
                "password": password,
            }
        )
        access_path.parent.mkdir(parents=True, exist_ok=True)
        access_path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
        self.stdout.write(
            "Synthetic demo created. Access file: ignored backend/.local/demo-access.json. "
            "No credential values printed."
        )
