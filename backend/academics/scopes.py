from rest_framework.exceptions import PermissionDenied

from accounts.models import Role, StudentProfile

from .models import Batch, Enrollment, TeacherAssignment


def students_for(user):
    students = StudentProfile.objects.filter(institute_id=user.institute_id)
    if user.role == Role.ADMIN:
        return students
    if user.role == Role.STUDENT:
        return students.filter(user=user)
    if user.role == Role.PARENT:
        return students.filter(
            parent_links__parent__user=user, parent_links__is_active=True
        ).distinct()
    if user.role == Role.TEACHER:
        return students.filter(
            enrollments__ended_at=None,
            enrollments__batch_id__in=assignments_for(user).values("batch_id"),
        ).distinct()
    return students.none()


def assignments_for(user):
    return TeacherAssignment.objects.filter(
        institute_id=user.institute_id, teacher__user=user, is_active=True, batch__is_active=True
    )


def batches_for(user):
    batches = Batch.objects.filter(institute_id=user.institute_id)
    if user.role == Role.ADMIN:
        return batches
    if user.role == Role.TEACHER:
        return batches.filter(pk__in=assignments_for(user).values("batch_id"))
    if user.role in (Role.STUDENT, Role.PARENT):
        return batches.filter(
            pk__in=Enrollment.objects.filter(
                institute_id=user.institute_id, student__in=students_for(user), ended_at=None
            ).values("batch_id")
        )
    return batches.none()


def require_admin(user):
    if user.role != Role.ADMIN:
        raise PermissionDenied("Institute Admin access required.")


def require_teaching_scope(user, batch, subject):
    if batch.institute_id != user.institute_id or subject.institute_id != user.institute_id:
        raise PermissionDenied("Academic scope unavailable.")
    if user.role == Role.ADMIN:
        return
    if (
        user.role != Role.TEACHER
        or not assignments_for(user).filter(batch=batch, subject=subject).exists()
    ):
        raise PermissionDenied("Academic scope unavailable.")


def selected_students(request):
    from django.shortcuts import get_object_or_404
    from rest_framework import serializers

    qs = students_for(request.user)
    if request.query_params.get("student"):
        key = serializers.IntegerField(min_value=1).run_validation(request.query_params["student"])
        student = get_object_or_404(qs, pk=key)
        return qs.filter(pk=student.pk)
    return qs
