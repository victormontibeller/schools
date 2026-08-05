"""Rotas canônicas do workflow interno de matrículas."""

from django.urls import path

from enrollments import document_views, reenrollment_views, requirement_views, views

urlpatterns = [
    path(
        "matriculas/requisitos/",
        requirement_views.document_requirement_list,
        name="document_requirement_list",
    ),
    path(
        "matriculas/requisitos/novo/",
        requirement_views.document_requirement_create,
        name="document_requirement_create",
    ),
    path(
        "matriculas/requisitos/<uuid:pk>/editar/",
        requirement_views.document_requirement_edit,
        name="document_requirement_edit",
    ),
    path(
        "matriculas/requisitos/<uuid:pk>/desativar/",
        requirement_views.document_requirement_deactivate,
        name="document_requirement_deactivate",
    ),
    path("matriculas/", views.enrollment_application_list, name="enrollment_application_list"),
    path(
        "matriculas/nova/",
        views.enrollment_application_create,
        name="enrollment_application_create",
    ),
    path(
        "matriculas/alunos/buscar/",
        views.enrollment_student_search,
        name="enrollment_student_search",
    ),
    path(
        "matriculas/<uuid:pk>/",
        views.enrollment_application_detail,
        name="enrollment_application_detail",
    ),
    path(
        "matriculas/<uuid:pk>/acao/",
        views.enrollment_application_action,
        name="enrollment_application_action",
    ),
    path(
        "matriculas/<uuid:pk>/corrigir/",
        views.enrollment_application_correct,
        name="enrollment_application_correct",
    ),
    path(
        "matriculas/<uuid:pk>/lembretes/",
        views.enrollment_reminder_send,
        name="enrollment_reminder_send",
    ),
    path(
        "matriculas/documentos/<uuid:pk>/entrega/",
        document_views.enrollment_document_delivery,
        name="enrollment_document_delivery",
    ),
    path(
        "matriculas/documentos/<uuid:pk>/acao/",
        document_views.enrollment_document_action,
        name="enrollment_document_action",
    ),
    path(
        "matriculas/documentos/<uuid:pk>/download/",
        document_views.enrollment_document_download,
        name="enrollment_document_download",
    ),
    path(
        "matriculas/rematricula/",
        reenrollment_views.reenrollment_batch,
        name="reenrollment_batch",
    ),
    path(
        "matriculas/rematricula/confirmar/",
        reenrollment_views.reenrollment_batch_confirm,
        name="reenrollment_batch_confirm",
    ),
]
