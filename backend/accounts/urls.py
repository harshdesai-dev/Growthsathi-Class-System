from django.urls import path

from .views import (
    ActivationView,
    ChangePasswordView,
    ContextView,
    LoginView,
    LogoutView,
    MeView,
    RecoveryConfirmView,
    RefreshView,
    ResetRequestView,
)

urlpatterns = [
    path("context/", ContextView.as_view()),
    path("login/", LoginView.as_view()),
    path("refresh/", RefreshView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("me/", MeView.as_view()),
    path("password/", ChangePasswordView.as_view()),
    path("reset/", ResetRequestView.as_view()),
    path("reset/confirm/", RecoveryConfirmView.as_view()),
    path("activate/", ActivationView.as_view()),
]
