"""Rotas canônicas da configuração de períodos e matriz de horários."""

from django.urls import path

from agenda import schedule_views, time_slot_views, views

urlpatterns = [
    path("turmas/", views.schedule_classes_list, name="schedule_classes_list"),
    path("periodos/", time_slot_views.time_slots_list, name="time_slots_list"),
    path("periodos/novo/", time_slot_views.time_slot_create, name="time_slot_create"),
    path("periodos/<uuid:pk>/editar/", time_slot_views.time_slot_edit, name="time_slot_edit"),
    path("turmas/<uuid:class_id>/grade/", views.schedule_weekly, name="schedule_weekly"),
    path(
        "turmas/<uuid:class_id>/grade/celulas/<str:day_of_week>/<uuid:time_slot_id>/nova/",
        schedule_views.schedule_cell_create,
        name="schedule_cell_create",
    ),
    path(
        "turmas/<uuid:class_id>/grade/celulas/<uuid:schedule_id>/editar/",
        schedule_views.schedule_cell_edit,
        name="schedule_cell_edit",
    ),
    path(
        "turmas/<uuid:class_id>/grade/celulas/<uuid:schedule_id>/encerrar/",
        schedule_views.schedule_cell_end,
        name="schedule_cell_end",
    ),
    path(
        "turmas/<uuid:class_id>/grade/copiar/formulario/",
        schedule_views.schedule_day_copy_form,
        name="schedule_day_copy_form",
    ),
    path(
        "turmas/<uuid:class_id>/grade/copiar/",
        schedule_views.schedule_day_copy,
        name="schedule_day_copy",
    ),
]
