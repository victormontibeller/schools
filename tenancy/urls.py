"""Rotas do catálogo público de escolas."""

from django.urls import path

from tenancy import views

urlpatterns = [
    path("platform/", views.platform_dashboard, name="platform_dashboard"),
    path("platform/escolas/", views.platform_school_list, name="platform_school_list"),
    path(
        "platform/escolas/nova/",
        views.platform_school_create,
        name="platform_school_create",
    ),
    path(
        "platform/escolas/<uuid:pk>/editar/",
        views.platform_school_edit,
        name="platform_school_edit",
    ),
]
