"""Rotas do módulo de responsáveis."""

from django.urls import path

from guardians import views

urlpatterns = [
    path("guardians/", views.guardians_list, name="guardians_list"),
    path("guardians/novo/", views.guardian_create, name="guardian_create"),
    path("guardians/<uuid:pk>/", views.guardian_detail, name="guardian_detail"),
    path("guardians/<uuid:pk>/editar/", views.guardian_edit, name="guardian_edit"),
]
