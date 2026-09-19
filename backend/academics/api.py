from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.models import ParentProfile, Role, StudentProfile, TeacherProfile
from accounts.permissions import ActiveTenantUser
from common.api import AdminResourceViewSet, TenantSerializer

from .models import (
    AcademicClass,
    AcademicYear,
    Batch,
    Enrollment,
    ParentStudentLink,
    Subject,
    TeacherAssignment,
)
from .scopes import batches_for, require_admin, selected_students
from .services import transfer_student


class YearSerializer(TenantSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "name", "starts_on", "ends_on", "is_current"]


class ClassSerializer(TenantSerializer):
    class Meta:
        model = AcademicClass
        fields = ["id", "name"]


class SubjectSerializer(TenantSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "code"]


class BatchSerializer(TenantSerializer):
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    year_name = serializers.CharField(source="academic_year.name", read_only=True)

    class Meta:
        model = Batch
        fields = [
            "id",
            "name",
            "academic_year",
            "academic_class",
            "room",
            "is_active",
            "class_name",
            "year_name",
        ]


class AssignmentSerializer(TenantSerializer):
    class Meta:
        model = TeacherAssignment
        fields = ["id", "teacher", "batch", "subject", "is_active"]


class LinkSerializer(TenantSerializer):
    class Meta:
        model = ParentStudentLink
        fields = ["id", "parent", "student", "relationship", "is_active"]


class EnrollmentSerializer(serializers.ModelSerializer):
    roll_number = serializers.CharField(source="registration.roll_number")
    batch_name = serializers.CharField(source="batch.name")
    class_name = serializers.CharField(source="batch.academic_class.name")

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "batch",
            "batch_name",
            "class_name",
            "roll_number",
            "started_at",
            "ended_at",
        ]


class StudentAcademicSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    current_enrollment = serializers.SerializerMethodField()

    def get_current_enrollment(self, student):
        enrollment = (
            student.enrollments.select_related("registration", "batch__academic_class")
            .filter(ended_at=None)
            .first()
        )
        return EnrollmentSerializer(enrollment).data if enrollment else None

    class Meta:
        model = StudentProfile
        fields = ["id", "full_name", "current_enrollment"]


class StudentSerializer(StudentAcademicSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    status = serializers.CharField(source="user.status", read_only=True)

    class Meta:
        model = StudentProfile
        fields = StudentAcademicSerializer.Meta.fields + [
            "user",
            "email",
            "phone",
            "status",
            "date_of_birth",
            "joining_date",
            "address",
        ]
        read_only_fields = ["user"]


class TeacherSerializer(TenantSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    status = serializers.CharField(source="user.status", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = [
            "id",
            "user",
            "full_name",
            "email",
            "phone",
            "status",
            "qualification",
            "experience_years",
            "joining_date",
            "address",
        ]
        read_only_fields = ["user"]


class ParentSerializer(TenantSerializer):
    status = serializers.CharField(source="user.status", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)

    class Meta:
        model = ParentProfile
        fields = [
            "id",
            "user",
            "full_name",
            "email",
            "phone",
            "address",
            "emergency_phone",
            "status",
        ]
        read_only_fields = ["user"]


class YearViewSet(AdminResourceViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = YearSerializer


class ClassViewSet(AdminResourceViewSet):
    queryset = AcademicClass.objects.all()
    serializer_class = ClassSerializer


class SubjectViewSet(AdminResourceViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class AssignmentViewSet(AdminResourceViewSet):
    queryset = TeacherAssignment.objects.all()
    serializer_class = AssignmentSerializer


class LinkViewSet(AdminResourceViewSet):
    queryset = ParentStudentLink.objects.all()
    serializer_class = LinkSerializer


class BatchViewSet(AdminResourceViewSet):
    module_filters = {
        "class": ("academic_class_id", "id"),
        "teacher": ("assignments__teacher_id", "id"),
        "subject": ("assignments__subject_id", "id"),
        "is_active": ("is_active", "bool"),
    }
    filter_constraints = {
        "subject": {"assignments__is_active": True},
        "teacher": {"assignments__is_active": True},
    }
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    search_fields = ["name"]

    def initial(self, request, *args, **kwargs):
        viewsets.ModelViewSet.initial(self, request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            require_admin(request.user)
        if request.user.role not in (Role.ADMIN, Role.TEACHER):
            raise PermissionDenied()

    def get_queryset(self):
        return (
            batches_for(self.request.user)
            .select_related("academic_year", "academic_class")
            .order_by("pk")
        )


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    module_filters = {
        "class": ("enrollments__batch__academic_class_id", "id"),
        "batch": ("enrollments__batch_id", "id"),
        "status": ("user__status", "text"),
    }
    filter_constraints = {
        "class": {"enrollments__ended_at": None},
        "batch": {"enrollments__ended_at": None},
    }
    permission_classes = [ActiveTenantUser]
    search_fields = ["user__full_name"]

    def get_queryset(self):
        return selected_students(self.request).select_related("user").order_by("pk")

    def get_serializer_class(self):
        return (
            StudentAcademicSerializer
            if self.request.user.role == Role.TEACHER
            else StudentSerializer
        )

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        class TransferInput(serializers.Serializer):
            batch = serializers.IntegerField(min_value=1)
            roll_number = serializers.CharField(max_length=40)

        data = TransferInput(data=request.data)
        data.is_valid(raise_exception=True)
        student = self.get_object()
        enrollment = transfer_student(
            request.user,
            student.pk,
            data.validated_data["batch"],
            data.validated_data["roll_number"],
        )
        return Response(EnrollmentSerializer(enrollment).data)

    def partial_update(self, request, pk=None):
        require_admin(request.user)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        require_admin(request.user)
        return Response(
            EnrollmentSerializer(
                self.get_object().enrollments.order_by("-started_at"), many=True
            ).data
        )


class TeacherViewSet(AdminResourceViewSet):
    module_filters = {
        "batch": ("assignments__batch_id", "id"),
        "subject": ("assignments__subject_id", "id"),
        "status": ("user__status", "text"),
    }
    filter_constraints = {
        "subject": {"assignments__is_active": True},
        "batch": {"assignments__is_active": True},
    }
    queryset = TeacherProfile.objects.select_related("user")
    serializer_class = TeacherSerializer
    http_method_names = ["get", "patch", "head", "options"]
    search_fields = ["user__full_name"]


class ParentViewSet(AdminResourceViewSet):
    module_filters = {
        "batch": ("child_links__student__enrollments__batch_id", "id"),
        "class": ("child_links__student__enrollments__batch__academic_class_id", "id"),
        "status": ("user__status", "text"),
    }
    filter_constraints = {
        "class": {
            "child_links__is_active": True,
            "child_links__student__enrollments__ended_at": None,
        },
        "batch": {
            "child_links__is_active": True,
            "child_links__student__enrollments__ended_at": None,
        },
    }
    queryset = ParentProfile.objects.select_related("user")
    serializer_class = ParentSerializer
    http_method_names = ["get", "patch", "head", "options"]
    search_fields = ["user__full_name"]
