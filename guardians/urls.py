"""Rotas do módulo de responsáveis."""

from django.urls import path

from guardians import views

urlpatterns = [
    path("guardians/", views.guardians_list, name="guardians_list"),
    path("guardians/novo/", views.guardian_create, name="guardian_create"),
    path("guardians/<uuid:pk>/", views.guardian_detail, name="guardian_detail"),
    path("guardians/<uuid:pk>/convidar/", views.guardian_invite, name="guardian_invite"),
    path("guardians/<uuid:pk>/foto/", views.guardian_avatar, name="guardian_avatar"),
    path("guardians/<uuid:pk>/editar/", views.guardian_edit, name="guardian_edit"),
    path(
        "guardians/<uuid:pk>/alunos/buscar/",
        views.guardian_student_search,
        name="guardian_student_search",
    ),
    path(
        "guardians/<uuid:pk>/alunos/<uuid:student_id>/vincular/",
        views.guardian_student_link,
        name="guardian_student_link",
    ),
    path(
        "guardians/<uuid:pk>/alunos/<uuid:student_id>/desvincular/",
        views.guardian_student_unlink,
        name="guardian_student_unlink",
    ),
]
