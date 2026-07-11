"""URLs do módulo de grade horária."""

from django.urls import path

from agenda import views

urlpatterns = [
    path("horarios/", views.time_slots_list, name="time_slots_list"),
    path("horarios/novo/", views.time_slot_create, name="time_slot_create"),
    path("horarios/<uuid:pk>/editar/", views.time_slot_edit, name="time_slot_edit"),
    path(
        "classes/<uuid:class_id>/schedule/",
        views.schedule_weekly,
        name="schedule_weekly",
    ),
    path(
        "teachers/<uuid:teacher_id>/schedule/",
        views.teacher_schedule,
        name="teacher_schedule",
    ),
    path(
        "classes/<uuid:class_id>/schedule/novo/",
        views.schedule_create,
        name="schedule_create",
    ),
]
