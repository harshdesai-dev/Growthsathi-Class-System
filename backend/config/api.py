from rest_framework.routers import DefaultRouter

from academics.api import (
    AssignmentViewSet,
    BatchViewSet,
    ClassViewSet,
    LinkViewSet,
    ParentViewSet,
    StudentViewSet,
    SubjectViewSet,
    TeacherViewSet,
    YearViewSet,
)
from accounts.management import UserViewSet
from announcements.api import AnnouncementViewSet
from attendance.api import AttendanceViewSet, TeacherAttendanceViewSet
from exams.api import ExamViewSet, ResultViewSet
from fees.api import FeeViewSet
from institutes.api import DomainViewSet, InstituteViewSet, PlanViewSet, SubscriptionViewSet
from materials.api import FileViewSet, MaterialViewSet
from notifications.api import NotificationViewSet
from timetable.api import TimetableViewSet

router = DefaultRouter()
for name, view in [
    ("users", UserViewSet),
    ("students", StudentViewSet),
    ("teachers", TeacherViewSet),
    ("parents", ParentViewSet),
    ("batches", BatchViewSet),
    ("academic-years", YearViewSet),
    ("academic-classes", ClassViewSet),
    ("subjects", SubjectViewSet),
    ("teacher-assignments", AssignmentViewSet),
    ("parent-links", LinkViewSet),
]:
    router.register(name, view, basename=name)
router.register("timetable", TimetableViewSet, basename="timetable")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("teacher-attendance", TeacherAttendanceViewSet, basename="teacher-attendance")
router.register("fees", FeeViewSet, basename="fees")
router.register("files", FileViewSet, basename="files")
router.register("materials", MaterialViewSet, basename="materials")
router.register("exams", ExamViewSet, basename="exams")
router.register("results", ResultViewSet, basename="results")
router.register("announcements", AnnouncementViewSet, basename="announcements")
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("super-admin/institutes", InstituteViewSet, basename="institutes")
router.register("super-admin/plans", PlanViewSet, basename="plans")
router.register("super-admin/domains", DomainViewSet, basename="domains")
router.register("super-admin/subscriptions", SubscriptionViewSet, basename="subscriptions")
urlpatterns = router.urls
