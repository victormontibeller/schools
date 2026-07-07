"""URLs do módulo de turmas e matrículas."""

from django.urls import path

from classes import views

urlpatterns = [
    path("classes/", views.classes_list, name="classes_list"),
    path("classes/nova/", views.class_create, name="class_create"),
    path("classes/<uuid:pk>/", views.class_detail, name="class_detail"),
    path("classes/<uuid:pk>/editar/", views.class_edit, name="class_edit"),
    path("classes/<uuid:class_id>/enroll/", views.class_enroll, name="class_enroll"),
]
