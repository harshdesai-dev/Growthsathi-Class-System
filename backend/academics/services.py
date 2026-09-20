from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import StudentProfile
from audit.models import AuditLog

from .models import Batch, Enrollment, StudentRegistration
from .scopes import require_admin


@transaction.atomic
def transfer_student(actor, student_id, batch_id, roll_number):
    require_admin(actor)
    student = get_object_or_404(
        StudentProfile.objects.select_for_update(), pk=student_id, institute_id=actor.institute_id
    )
    batch = get_object_or_404(Batch, pk=batch_id, institute_id=actor.institute_id, is_active=True)
    current = Enrollment.objects.filter(student=student, ended_at=None).first()
    if current and current.batch_id == batch.pk:
        raise ValidationError({"batch": "Student is already in this batch."})
    registration, _ = StudentRegistration.objects.get_or_create(
        institute_id=actor.institute_id,
        student=student,
        academic_year=batch.academic_year,
        defaults={"roll_number": roll_number},
    )
    if registration.roll_number != roll_number:
        raise ValidationError(
            {"roll_number": "Use the existing roll number for this academic year."}
        )
    now = timezone.now()
    if current:
        current.ended_at = now
        current.save(update_fields=["ended_at"])
    enrollment = Enrollment.objects.create(
        institute_id=actor.institute_id,
        student=student,
        registration=registration,
        batch=batch,
        started_at=now,
    )
    AuditLog.objects.create(
        institute_id=actor.institute_id,
        actor=actor,
        action="student-transfer",
        entity="StudentProfile",
        entity_id=str(student.pk),
        summary={
            "previous_enrollment": current.pk if current else None,
            "enrollment": enrollment.pk,
        },
    )
    return enrollment
