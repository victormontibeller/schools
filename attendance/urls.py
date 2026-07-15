"""URLs do módulo de frequência."""

from django.urls import path

from attendance import views

urlpatterns = [
    path("frequencia/", views.attendance_records_list, name="attendance_records_list"),
    path("frequencia/nova/", views.attendance_record_create, name="attendance_record_create"),
    path(
        "frequencia/<uuid:record_id>/chamada/",
        views.attendance_record_fill,
        name="attendance_record_fill",
    ),
    path(
        "frequencia/turma/<uuid:class_id>/",
        views.class_attendance_summary,
        name="class_attendance_summary",
    ),
    path(
        "frequencia/aluno/<uuid:student_id>/",
        views.student_attendance,
        name="student_attendance",
    ),
    path(
        "frequencia/aluno/<uuid:student_id>/turma/<uuid:class_id>/",
        views.student_attendance,
        name="student_attendance_class",
    ),
    path("frequencia/risco/", views.students_at_risk, name="students_at_risk"),
    path("justificativas/", views.justifications_list, name="justifications_list"),
    path("justificativas/nova/", views.justification_create, name="justification_create"),
    path(
        "justificativas/<uuid:pk>/documento/",
        views.justification_document,
        name="justification_document",
    ),
    path(
        "justificativas/<uuid:pk>/aprovar/",
        views.justification_approve,
        name="justification_approve",
    ),
    path(
        "justificativas/<uuid:pk>/rejeitar/",
        views.justification_reject,
        name="justification_reject",
    ),
]
