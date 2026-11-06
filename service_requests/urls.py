from django.urls import path

from service_requests import configuration_views, views

urlpatterns = [
    path("service-requests/", views.service_request_list, name="service_request_list"),
    path("service-requests/new/", views.service_request_create, name="service_request_create"),
    path(
        "service-requests/configuration/",
        configuration_views.service_request_configuration,
        name="service_request_configuration",
    ),
    path(
        "service-requests/<uuid:pk>/", views.service_request_detail, name="service_request_detail"
    ),
    path(
        "service-requests/<uuid:pk>/respond/",
        views.service_request_respond,
        name="service_request_respond",
    ),
    path(
        "service-requests/<uuid:pk>/action/",
        views.service_request_action,
        name="service_request_action",
    ),
    path(
        "service-requests/attachments/<uuid:pk>/",
        views.service_request_attachment,
        name="service_request_attachment",
    ),
]
