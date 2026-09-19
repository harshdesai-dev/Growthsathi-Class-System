from django.core.exceptions import ValidationError
from django.db import models

from institutes.models import TenantModel


class Exam(TenantModel):
    name = models.CharField(max_length=160)
    batch = models.ForeignKey("academics.Batch", on_delete=models.PROTECT)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT)
    date = models.DateField()
    starts_at = models.TimeField()
    total_marks = models.DecimalField(max_digits=7, decimal_places=2)
    passing_marks = models.DecimalField(max_digits=7, decimal_places=2)
    instructions = models.TextField(blank=True)
    is_cancelled = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    total_marks__gt=0,
                    passing_marks__gte=0,
                    passing_marks__lte=models.F("total_marks"),
                ),
                name="exam_marks_valid",
            )
        ]


class ExamScore(TenantModel):
    def clean(self):
        super().clean()
        if self.exam_id and self.enrollment_id and self.enrollment.batch_id != self.exam.batch_id:
            raise ValidationError({"enrollment": "Enrollment must belong to the exam batch."})
        if self.exam_id and self.marks is not None and self.marks > self.exam.total_marks:
            raise ValidationError({"marks": "Marks cannot exceed the exam maximum."})

    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="scores")
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT)
    marks = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False)
    remark = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "enrollment"], name="exam_enrollment_unique"),
            models.CheckConstraint(
                condition=models.Q(marks=None) | models.Q(marks__gte=0), name="score_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(is_absent=False) | models.Q(marks=None),
                name="absent_has_no_mark",
            ),
        ]
