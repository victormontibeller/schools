from django.urls import path

from students import views

urlpatterns = [
    path("students/", views.students_list, name="students_list"),
    path("students/novo/", views.student_create, name="student_create"),
    path("students/<uuid:pk>/", views.student_profile, name="student_profile"),
    path("students/<uuid:pk>/editar/", views.student_edit, name="student_edit"),
]
