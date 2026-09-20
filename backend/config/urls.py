"""Only process liveness is exposed in Checkpoint 1."""

from django.urls import include, path

from common.dashboard import DashboardView
from common.views import ProfileView, ScopeView
from institutes.api import LogoView, SettingsView

from .views import health

urlpatterns = [
    path("api/dashboard/", DashboardView.as_view()),
    path("api/profile/", ProfileView.as_view()),
    path("api/scope/", ScopeView.as_view()),
    path("api/settings/", SettingsView.as_view()),
    path("api/branding/logo/", LogoView.as_view()),
    path("api/", include("config.api")),
    path("health/", health, name="health"),
    path("api/auth/", include("accounts.urls")),
]
