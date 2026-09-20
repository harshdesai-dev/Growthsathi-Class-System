"""Role-scoped dashboard composition using the same query scopes as module APIs."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.scopes import batches_for, selected_students
from accounts.models import Role, TeacherProfile
from accounts.permissions import ActiveTenantUser, PlatformOperator
from announcements.api import AnnouncementSerializer, AnnouncementViewSet
from attendance.api import AttendanceViewSet
from audit.models import AuditLog
from exams.api import ExamSerializer, ExamViewSet, ResultViewSet, ScoreSerializer
from fees.api import FeeViewSet
from fees.services import installment_paid, total_paid
from institutes.models import Institute, InstituteSettings, InstituteSubscription
from materials.api import MaterialSerializer, MaterialViewSet
from timetable.api import TimetableSerializer, TimetableViewSet


class DashboardView(APIView):
    permission_classes = [ActiveTenantUser | PlatformOperator]

    def get(self, request):
        user, today = request.user, timezone.localdate()
        sections = []

        def section(title, module, columns, rows):
            sections.append({"title": title, "module": module, "columns": columns, "rows": rows})

        def scoped(view_class):
            view = view_class()
            view.request = request
            return view.get_queryset()

        if user.role == Role.SUPER_ADMIN:
            institutes = Institute.objects.all()
            renewals = InstituteSubscription.objects.filter(
                ends_on__gte=today, ends_on__lte=today + timedelta(days=30)
            ).select_related("institute", "plan")
            stats = {
                "Institutes": institutes.count(),
                "Active institutes": institutes.filter(is_active=True).count(),
                "Inactive institutes": institutes.filter(is_active=False).count(),
                "Renewals in 30 days": renewals.count(),
                "Open support items": institutes.filter(support_status="OPEN").count(),
            }
            section(
                "Upcoming renewals",
                "subscriptions",
                [["name", "Institute"], ["plan", "Plan"], ["date", "Renewal"]],
                [
                    {"id": r.pk, "name": r.institute.name, "plan": r.plan.name, "date": r.ends_on}
                    for r in renewals[:8]
                ],
            )
            section(
                "Recent operator activity",
                "support",
                [["action", "Action"], ["entity", "Record type"], ["date", "Date"]],
                [
                    {"id": a.pk, "action": a.action, "entity": a.entity, "date": a.created_at}
                    for a in AuditLog.objects.filter(actor__role=Role.SUPER_ADMIN).order_by(
                        "-created_at"
                    )[:8]
                ],
            )
            return Response({**stats, "sections": sections})

        students = selected_students(request)
        batches = batches_for(user)
        if user.role == Role.PARENT and request.query_params.get("student"):
            batches = batches.filter(
                enrollments__student__in=students, enrollments__ended_at=None
            ).distinct()
        attendance = scoped(AttendanceViewSet)
        attended = attendance.filter(status__in=["PRESENT", "LATE"]).count()
        total = attendance.count()
        stats = {
            "Students"
            if user.role in (Role.ADMIN, Role.TEACHER)
            else "Linked records": students.count(),
            "Batches": batches.count(),
            "Attendance (%)": round(attended * 100 / total, 2) if total else None,
        }
        today_rows = attendance.filter(session__date=today)
        stats.update(
            {
                f"{status.title()} today": today_rows.filter(status=status)
                .values("enrollment__student_id")
                .distinct()
                .count()
                for status in ("PRESENT", "ABSENT", "LATE")
            }
        )
        if user.role == Role.ADMIN:
            stats["Teachers"] = TeacherProfile.objects.filter(
                institute_id=user.institute_id
            ).count()
        preferences = InstituteSettings.objects.filter(institute_id=user.institute_id).first()
        threshold = preferences.attendance_threshold if preferences else 75
        stats["Attendance threshold (%)"] = threshold
        grouped = attendance.values(
            "enrollment__student_id", "enrollment__student__user__full_name"
        ).annotate(
            total=Count("pk"), attended=Count("pk", filter=Q(status__in=["PRESENT", "LATE"]))
        )
        low = [
            {
                "id": row["enrollment__student_id"],
                "name": row["enrollment__student__user__full_name"],
                "percentage": round(row["attended"] * 100 / row["total"], 2),
            }
            for row in grouped
            if row["attended"] * 100 < threshold * row["total"]
        ]
        section(
            "Low attendance",
            "attendance",
            [["name", "Student"], ["percentage", "Attendance (%)"]],
            low[:8],
        )
        if user.role != Role.PARENT:
            lectures = scoped(TimetableViewSet).filter(date=today, is_cancelled=False)
            stats["Classes today"] = lectures.count()
            section(
                "Today's classes",
                "timetable",
                [
                    ["starts_at", "Start"],
                    ["batch_name", "Batch"],
                    ["subject_name", "Subject"],
                    ["teacher_name", "Teacher"],
                    ["room", "Room"],
                ],
                TimetableSerializer(lectures[:8], many=True).data,
            )
        exams = (
            scoped(ExamViewSet)
            .filter(date__gte=today, is_cancelled=False)
            .order_by("date", "starts_at")
        )
        stats["Upcoming exams"] = exams.count()
        if user.role in (Role.ADMIN, Role.TEACHER):
            stats["Exams awaiting marks"] = (
                exams.filter(scores__marks=None, scores__is_absent=False, published_at=None)
                .distinct()
                .count()
            )
        section(
            "Upcoming exams",
            "exams",
            [
                ["name", "Exam"],
                ["batch_name", "Batch"],
                ["subject_name", "Subject"],
                ["date", "Date"],
            ],
            ExamSerializer(exams[:5], many=True).data,
        )
        results = scoped(ResultViewSet)
        section(
            "Latest published results",
            "results",
            [["student_name", "Student"], ["exam_name", "Exam"], ["calculation", "Result"]],
            ScoreSerializer(results[:5], many=True).data,
        )
        notices = (
            scoped(AnnouncementViewSet)
            .filter(is_active=True, published_at__lte=timezone.now())
            .filter(Q(expires_at=None) | Q(expires_at__gt=timezone.now()))
        )
        section(
            "Recent announcements",
            "announcements",
            [["title", "Title"], ["message", "Message"], ["published_at", "Published"]],
            AnnouncementSerializer(notices[:5], many=True).data,
        )
        if user.role != Role.PARENT:
            materials = scoped(MaterialViewSet).filter(is_active=True)
            section(
                "Recent materials",
                "materials",
                [["title", "Material"], ["subject_name", "Subject"], ["topic", "Topic"]],
                MaterialSerializer(materials[:5], many=True).data,
            )
        if user.role != Role.TEACHER:
            accounts = scoped(FeeViewSet)
            expected = paid = overdue = Decimal("0")
            due = []
            for account in accounts:
                expected += account.total_fee
                paid += total_paid(account)
                for installment in account.installments.all():
                    pending = installment.amount - installment_paid(installment)
                    if pending > 0:
                        if installment.due_date < today:
                            overdue += pending
                        due.append(
                            {
                                "id": installment.pk,
                                "student": account.registration.student.user.full_name,
                                "due_date": installment.due_date,
                                "amount": str(pending),
                            }
                        )
            stats.update(
                {
                    "Expected fees": str(expected),
                    "Fees collected": str(paid),
                    "Fees pending": str(expected - paid),
                    "Overdue fees": str(overdue),
                }
            )
            section(
                "Upcoming and overdue installments",
                "fees",
                [["student", "Student"], ["due_date", "Due date"], ["amount", "Pending (INR)"]],
                sorted(due, key=lambda row: row["due_date"])[:8],
            )
        return Response({**stats, "sections": sections})
