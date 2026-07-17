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
        "agenda-infantil/publicacao/<uuid:entry_id>/",
        views.diary_publication_detail,
        name="diary_publication_detail",
    ),
    path(
        "agenda-infantil/publicacao/<uuid:entry_id>/visualizada/",
        views.diary_publication_mark_viewed,
        name="diary_publication_mark_viewed",
    ),
    path(
        "agenda-infantil/folha/<uuid:sheet_id>/enviar/",
        views.diary_sheet_submit,
        name="diary_sheet_submit",
    ),
    path(
        "agenda-infantil/folha/<uuid:sheet_id>/aprovar/",
        views.diary_sheet_approve,
        name="diary_sheet_approve",
    ),
    path(
        "agenda-infantil/folha/<uuid:sheet_id>/devolver/",
        views.diary_sheet_request_changes,
        name="diary_sheet_request_changes",
    ),
    path(
        "agenda-infantil/folha/<uuid:sheet_id>/reabrir/",
        views.diary_sheet_reopen,
        name="diary_sheet_reopen",
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
