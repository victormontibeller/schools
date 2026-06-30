from django.urls import path

from dashboard import views

urlpatterns = [
    path("dashboard/", views.school_dashboard, name="school_dashboard"),
    path(
        "dashboard/partial/",
        views.school_dashboard_partial,
        name="school_dashboard_partial",
    ),
    path(
        "dashboard/executive/",
        views.executive_dashboard,
        name="executive_dashboard",
    ),
]
