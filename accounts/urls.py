from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetDoneView,
)
from django.urls import path

from accounts import staff_views, views
from accounts.invitation_views import guardian_invitation_view
from accounts.recovery_views import SchoolPasswordResetConfirmView, SchoolPasswordResetView

urlpatterns = [
    path("users/novo/", staff_views.staff_user_create, name="staff_user_create"),
    path("users/<uuid:pk>/convidar/", staff_views.staff_user_invite, name="staff_user_invite"),
    path("convite-equipe/", staff_views.staff_invitation, name="staff_invitation"),
    path("demo/cadastro/", views.demo_signup_view, name="demo_signup"),
    path("demo/verificar/<str:token>/", views.demo_verify_view, name="demo_verify"),
    path(
        "convite-professor/<str:token>/",
        views.teacher_invitation_view,
        name="teacher_invitation",
    ),
    path("convite-responsavel/", guardian_invitation_view, name="guardian_invitation"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/change-password/", views.change_password_view, name="change_password"),
    path("users/", views.users_list_view, name="users_list"),
    path("users/<uuid:pk>/", views.user_detail_view, name="user_detail"),
    path("users/<uuid:pk>/avatar/", views.user_avatar, name="user_avatar"),
    path("users/<uuid:pk>/editar/", views.user_edit_view, name="user_edit"),
    path(
        "platform/usuarios/",
        views.platform_user_list_view,
        name="platform_user_list",
    ),
    path(
        "platform/usuarios/novo/",
        views.platform_user_create_view,
        name="platform_user_create",
    ),
    path(
        "platform/usuarios/<uuid:pk>/editar/",
        views.platform_user_edit_view,
        name="platform_user_edit",
    ),
    # Recuperação mantém protocolo Django com confirmação auditada.
    path(
        "password-reset/",
        SchoolPasswordResetView.as_view(template_name="auth/password_reset_form.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(template_name="auth/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        SchoolPasswordResetConfirmView.as_view(template_name="auth/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        PasswordResetCompleteView.as_view(template_name="auth/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
