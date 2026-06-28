from django.urls import path

from teachers import views

urlpatterns = [
    path("teachers/", views.teachers_list, name="teachers_list"),
    path("teachers/<uuid:pk>/", views.teacher_detail, name="teacher_detail"),
]
