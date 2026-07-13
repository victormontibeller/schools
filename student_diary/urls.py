"""Rotas da Agenda escolar."""

from django.urls import path

from student_diary import views

urlpatterns = [
    path("agenda-infantil/", views.diary_daily, name="diary_daily"),
    path(
        "agenda-infantil/aluno/<uuid:student_id>/",
        views.diary_student_history,
        name="diary_student_history",
    ),
    path(
        "agenda-infantil/configuracao/",
        views.diary_configuration,
        name="diary_configuration",
    ),
    path(
        "agenda-infantil/configuracao/aspectos/<uuid:category_id>/",
        views.diary_aspect_detail,
        name="diary_aspect_detail",
    ),
    path(
        "agenda-infantil/configuracao/aspectos/<uuid:category_id>/ativacao/",
        views.diary_aspect_toggle,
        name="diary_aspect_toggle",
    ),
]
