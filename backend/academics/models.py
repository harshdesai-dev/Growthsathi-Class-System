from django.core.exceptions import ValidationError
from django.db import models

from institutes.models import TenantModel


class AcademicYear(TenantModel):
    name = models.CharField(max_length=80)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")), name="year_dates_ordered"
            ),
            models.UniqueConstraint(fields=["institute", "name"], name="year_name_unique"),
            models.UniqueConstraint(
                fields=["institute"], condition=models.Q(is_current=True), name="one_current_year"
            ),
        ]


class AcademicClass(TenantModel):
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["institute", "name"], name="class_name_unique")
        ]


class Subject(TenantModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["institute", "code"], name="subject_code_unique")
        ]


class Batch(TenantModel):
    name = models.CharField(max_length=100)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT)
    room = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "academic_year", "name"], name="batch_name_unique"
            )
        ]


class TeacherAssignment(TenantModel):
    teacher = models.ForeignKey(
        "accounts.TeacherProfile", on_delete=models.PROTECT, related_name="assignments"
    )
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="assignments")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "batch", "subject"], name="assignment_unique"
            )
        ]


class StudentRegistration(TenantModel):
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.PROTECT, related_name="registrations"
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)
    roll_number = models.CharField(max_length=40)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"], name="student_year_unique"
            ),
            models.UniqueConstraint(
                fields=["institute", "academic_year", "roll_number"], name="year_roll_unique"
            ),
        ]


class Enrollment(TenantModel):
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.PROTECT, related_name="enrollments"
    )
    registration = models.ForeignKey(StudentRegistration, on_delete=models.PROTECT)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="enrollments")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.registration_id and self.batch_id:
            if self.registration.student_id != self.student_id:
                raise ValidationError({"registration": "Registration belongs to another student."})
            if self.registration.academic_year_id != self.batch.academic_year_id:
                raise ValidationError({"batch": "Batch must match registration academic year."})

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student"], condition=models.Q(ended_at=None), name="one_current_enrollment"
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at=None) | models.Q(ended_at__gte=models.F("started_at")),
                name="enrollment_dates_ordered",
            ),
        ]


class ParentStudentLink(TenantModel):
    parent = models.ForeignKey(
        "accounts.ParentProfile", on_delete=models.PROTECT, related_name="child_links"
    )
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.PROTECT, related_name="parent_links"
    )
    relationship = models.CharField(max_length=60, default="Guardian")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["parent", "student"], name="parent_student_unique")
        ]
