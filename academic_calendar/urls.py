"""URLs do módulo de calendário acadêmico."""

from django.urls import path

from academic_calendar import views

urlpatterns = [
    path("calendario/", views.calendar_month, name="calendar_month"),
    path(
        "calendario/<int:year>/<int:month>/",
        views.calendar_month,
        name="calendar_month_specific",
    ),
    path("eventos/", views.events_list, name="events_list"),
    path("eventos/novo/", views.event_create, name="event_create"),
    path("eventos/<uuid:pk>/", views.event_detail, name="event_detail"),
    path("eventos/<uuid:pk>/cancelar/", views.event_cancel, name="event_cancel"),
    path("feriados/", views.holidays_list, name="holidays_list"),
    path("feriados/novo/", views.holiday_create, name="holiday_create"),
    path("anos-letivos/", views.academic_years_list, name="academic_years_list"),
    path("anos-letivos/novo/", views.academic_year_create, name="academic_year_create"),
]
