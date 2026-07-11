"""URLs do modulo de matriculas e secretaria."""

from django.urls import path

from enrollments import views

urlpatterns = [
    path("secretaria/", views.secretary_dashboard, name="secretary_dashboard"),
    path(
        "secretaria/solicitacao/nova/",
        views.application_create,
        name="application_create",
    ),
    path(
        "secretaria/solicitacao/<uuid:pk>/",
        views.application_detail,
        name="application_detail",
    ),
    path(
        "secretaria/solicitacao/<uuid:pk>/revisar/",
        views.application_review,
        name="application_review",
    ),
    path(
        "secretaria/solicitacao/<uuid:pk>/efetivar/",
        views.application_complete_enrollment,
        name="application_complete_enrollment",
    ),
    path(
        "secretaria/solicitacao/<uuid:pk>/cancelar/",
        views.application_cancel,
        name="application_cancel",
    ),
    path(
        "secretaria/rematricula/",
        views.bulk_reenroll_view,
        name="bulk_reenroll",
    ),
    path(
        "secretaria/documento/novo/",
        views.document_add,
        name="document_add",
    ),
    path(
        "secretaria/solicitacao/<uuid:application_id>/documento/novo/",
        views.document_add,
        name="document_add_for_application",
    ),
    path(
        "secretaria/documento/<uuid:pk>/verificar/",
        views.document_verify,
        name="document_verify",
    ),
    path(
        "secretaria/documento/<uuid:pk>/recusar/",
        views.document_reject,
        name="document_reject",
    ),
    path(
        "secretaria/documento/<uuid:pk>/download/",
        views.document_download,
        name="document_download",
    ),
    path(
        "secretaria/aluno/<uuid:student_id>/notificar-pendencias/",
        views.notify_pending_documents,
        name="notify_pending_documents",
    ),
]
