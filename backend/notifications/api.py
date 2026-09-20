from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from academics.scopes import students_for
from accounts.models import Role
from accounts.permissions import ActiveTenantUser
from announcements.api import announcements_for
from exams.api import exams_for
from materials.api import materials_for

from .models import UserNotification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "kind", "object_id", "created_at", "read_at"]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [ActiveTenantUser]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        rows = UserNotification.objects.filter(institute_id=user.institute_id, user=user).order_by(
            "-created_at"
        )
        allowed_students = set(students_for(user).values_list("pk", flat=True))
        announcements = set(announcements_for(user).values_list("pk", flat=True))
        exams = set(exams_for(user).values_list("pk", flat=True))
        results = set(
            exams_for(user).filter(published_at__isnull=False).values_list("pk", flat=True)
        )
        materials = set(materials_for(user).values_list("pk", flat=True))
        allowed = []
        for row in rows:
            if row.student_id and row.student_id not in allowed_students:
                continue
            if row.kind == "fees" and user.role == Role.TEACHER:
                continue
            permitted = {
                "announcements": announcements,
                "exams": exams,
                "results": results,
                "materials": materials,
            }
            if row.kind in permitted and row.object_id not in permitted[row.kind]:
                continue
            if row.kind == "timetable":
                from timetable.api import TimetableViewSet

                view = TimetableViewSet()
                view.request = self.request
                if user.role == Role.PARENT:
                    # Parent still requires linked child; no timetable module or details exposed.
                    if not row.student_id:
                        continue
                elif not view.get_queryset().filter(pk=row.object_id).exists():
                    continue
            allowed.append(row.pk)
        return rows.filter(pk__in=allowed)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
        return Response(self.get_serializer(notification).data)
