from rest_framework.response import Response
from rest_framework.views import APIView

from academics.api import BatchSerializer, StudentAcademicSerializer, SubjectSerializer
from academics.models import StudentRegistration, Subject
from academics.scopes import assignments_for, batches_for, students_for
from accounts.models import Role, TeacherProfile
from accounts.permissions import ActiveTenantUser, PlatformOperator
from accounts.views import user_data


class ScopeView(APIView):
    permission_classes = [ActiveTenantUser]

    def get(self, request):
        user = request.user
        subjects = Subject.objects.filter(institute_id=user.institute_id)
        if user.role == Role.TEACHER:
            subjects = subjects.filter(pk__in=assignments_for(user).values("subject_id"))
        elif user.role in (Role.STUDENT, Role.PARENT):
            from academics.models import TeacherAssignment

            subjects = subjects.filter(
                pk__in=TeacherAssignment.objects.filter(
                    institute_id=user.institute_id, batch__in=batches_for(user), is_active=True
                ).values("subject_id")
            )
        data = {
            "students": StudentAcademicSerializer(students_for(user), many=True).data,
            "batches": BatchSerializer(batches_for(user), many=True).data,
            "subjects": SubjectSerializer(subjects, many=True).data,
        }
        if user.role == Role.ADMIN:
            data["teachers"] = [
                {"id": p.pk, "name": p.user.full_name}
                for p in TeacherProfile.objects.filter(
                    institute_id=user.institute_id
                ).select_related("user")
            ]
            data["registrations"] = [
                {"id": r.pk, "name": f"{r.student.user.full_name} - {r.roll_number}"}
                for r in StudentRegistration.objects.filter(
                    institute_id=user.institute_id
                ).select_related("student__user")
            ]
        return Response(data)


class ProfileView(APIView):
    permission_classes = [ActiveTenantUser | PlatformOperator]

    def get(self, request):
        from academics.api import ParentSerializer, StudentSerializer, TeacherSerializer

        user = request.user
        data = user_data(user)
        profile = {
            Role.STUDENT: ("studentprofile", StudentSerializer),
            Role.TEACHER: ("teacherprofile", TeacherSerializer),
            Role.PARENT: ("parentprofile", ParentSerializer),
        }.get(user.role)
        if profile and hasattr(user, profile[0]):
            data["profile"] = profile[1](getattr(user, profile[0])).data
        return Response(data)

    def patch(self, request):
        from rest_framework import serializers

        class Contact(serializers.Serializer):
            email = serializers.EmailField(required=False, allow_blank=True)
            phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
            address = serializers.CharField(max_length=1000, required=False, allow_blank=True)

        data = Contact(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        address = values.pop("address", None)
        if address is not None and request.user.role in (Role.PARENT, Role.TEACHER):
            relation = "parentprofile" if request.user.role == Role.PARENT else "teacherprofile"
            profile = getattr(request.user, relation)
            profile.address = address
            profile.save(update_fields=["address"])
        for field, value in values.items():
            setattr(request.user, field, value)
        request.user.save()
        return self.get(request)
