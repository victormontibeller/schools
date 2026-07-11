"""Rotas de acesso temporário da plataforma."""

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
    path("platform/support/", views.support_access_create, name="support_access_create"),
    path("support/consume/", views.support_access_consume, name="support_access_consume"),
    path("support/end/", views.support_access_end, name="support_access_end"),
]
