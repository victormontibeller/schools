from django.urls import path

from students import views

urlpatterns = [
    path("students/", views.students_list, name="students_list"),
    path("students/novo/", views.student_create, name="student_create"),
    path("students/<uuid:pk>/", views.student_profile, name="student_profile"),
    path("students/<uuid:pk>/foto/", views.student_photo, name="student_photo"),
    path("students/<uuid:pk>/editar/", views.student_edit, name="student_edit"),
    path(
        "students/<uuid:pk>/responsaveis/",
        views.student_guardians_component,
        name="student_guardians_component",
    ),
    path(
        "students/<uuid:pk>/responsaveis/novo/",
        views.student_guardian_create,
        name="student_guardian_create",
    ),
    path(
        "students/<uuid:pk>/responsaveis/buscar/",
        views.student_guardian_search,
        name="student_guardian_search",
    ),
    path(
        "students/<uuid:pk>/responsaveis/<uuid:guardian_pk>/vincular/",
        views.student_guardian_link,
        name="student_guardian_link",
    ),
    path(
        "students/<uuid:pk>/responsaveis/vinculos/<uuid:link_pk>/editar/",
        views.student_guardian_link_edit,
        name="student_guardian_link_edit",
    ),
    path(
        "students/<uuid:pk>/responsaveis/vinculos/<uuid:link_pk>/contato/editar/",
        views.student_guardian_contact_edit,
        name="student_guardian_contact_edit",
    ),
    path(
        "students/<uuid:pk>/responsaveis/vinculos/<uuid:link_pk>/desvincular/",
        views.student_guardian_unlink,
        name="student_guardian_unlink",
    ),
]
