"""Rotas do módulo de professores."""

from django.urls import path

from teachers import views

urlpatterns = [
    path("teachers/", views.teachers_list, name="teachers_list"),
    path("teachers/novo/", views.teacher_create, name="teacher_create"),
    path("teachers/<uuid:pk>/", views.teacher_detail, name="teacher_detail"),
    path("teachers/<uuid:pk>/foto/", views.teacher_avatar, name="teacher_avatar"),
    path("teachers/<uuid:pk>/editar/", views.teacher_edit, name="teacher_edit"),
    path(
        "teachers/<uuid:pk>/disciplinas/",
        views.teacher_subjects_edit,
        name="teacher_subjects_edit",
    ),
    path("subjects/", views.subjects_list, name="subjects_list"),
    path("subjects/novo/", views.subject_create, name="subject_create"),
    path("subjects/<uuid:pk>/", views.subject_detail, name="subject_detail"),
    path("subjects/<uuid:pk>/editar/", views.subject_edit, name="subject_edit"),
    path("subjects/<uuid:pk>/desativar/", views.subject_deactivate, name="subject_deactivate"),
]
