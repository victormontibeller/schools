"""Rotas do módulo de professores."""

from django.urls import path

from teachers import views

urlpatterns = [
    path("teachers/", views.teachers_list, name="teachers_list"),
    path("teachers/novo/", views.teacher_create, name="teacher_create"),
    path("teachers/<uuid:pk>/", views.teacher_detail, name="teacher_detail"),
]
