from academics.models import Enrollment, ParentStudentLink, TeacherAssignment
from accounts.models import AccountStatus, Role, User

from .models import UserNotification


def student_event(student, kind, object_id):
    recipients = [student.user_id] + list(
        ParentStudentLink.objects.filter(
            institute_id=student.institute_id, student=student, is_active=True
        ).values_list("parent__user_id", flat=True)
    )
    for user in User.objects.filter(
        pk__in=recipients, institute_id=student.institute_id, status=AccountStatus.ACTIVE
    ):
        UserNotification.objects.create(
            institute_id=student.institute_id,
            user=user,
            kind=kind,
            object_id=object_id,
            student=student,
        )


def batch_event(batch, kind, object_id, subject=None):
    for entry in Enrollment.objects.filter(
        institute_id=batch.institute_id, batch=batch, ended_at=None
    ).select_related("student"):
        student_event(entry.student, kind, object_id)
    assignments = TeacherAssignment.objects.filter(
        institute_id=batch.institute_id, batch=batch, is_active=True
    )
    if subject:
        assignments = assignments.filter(subject=subject)
    for uid in assignments.values_list("teacher__user_id", flat=True).distinct():
        UserNotification.objects.create(
            institute_id=batch.institute_id, user_id=uid, kind=kind, object_id=object_id
        )


def announce(announcement):
    # Compute recipients now, and recheck current audience authorization when read.
    for user in User.objects.filter(
        institute_id=announcement.institute_id, status=AccountStatus.ACTIVE
    ).exclude(role=Role.ADMIN):
        from academics.scopes import batches_for

        role_audience = {
            Role.STUDENT: "STUDENTS",
            Role.PARENT: "PARENTS",
            Role.TEACHER: "TEACHERS",
        }.get(user.role)
        allowed = announcement.audience in ("ALL", role_audience)
        if announcement.audience == "BATCH":
            allowed = batches_for(user).filter(pk=announcement.batch_id).exists()
        elif announcement.audience == "CLASS":
            allowed = (
                batches_for(user).filter(academic_class_id=announcement.academic_class_id).exists()
            )
        if not allowed:
            continue
        UserNotification.objects.get_or_create(
            institute_id=announcement.institute_id,
            user=user,
            kind="announcements",
            object_id=announcement.pk,
            announcement=announcement,
        )
