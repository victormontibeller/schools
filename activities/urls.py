"""URLs do módulo de atividades."""

from django.urls import path

from activities import views

urlpatterns = [
    path("activities/", views.activities_list, name="activities_list"),
    path("activities/nova/", views.activity_create, name="activity_create"),
    path("activities/<uuid:pk>/", views.activity_detail, name="activity_detail"),
    path("activities/<uuid:pk>/editar/", views.activity_edit, name="activity_edit"),
    path(
        "activities/<uuid:pk>/score/",
        views.activity_record_score,
        name="activity_record_score",
    ),
    path("activities/<uuid:pk>/grupos/", views.activity_group_save, name="activity_group_create"),
    path(
        "activities/<uuid:pk>/grupos/<uuid:group_id>/",
        views.activity_group_save,
        name="activity_group_edit",
    ),
    path(
        "activities/<uuid:pk>/grupos/<uuid:group_id>/resultado/",
        views.activity_group_apply_result,
        name="activity_group_apply_result",
    ),
    path(
        "activities/<uuid:pk>/grupos/<uuid:group_id>/desativar/",
        views.activity_group_deactivate,
        name="activity_group_deactivate",
    ),
]
