"""URLs do modulo de enderecos."""

from django.urls import path

from addresses import views

app_name = "addresses"

urlpatterns = [
    path("addresses/city-options/", views.address_city_options, name="city_options"),
    path(
        "addresses/card/<str:entity_type>/<uuid:entity_id>/",
        views.address_card,
        name="address_card",
    ),
    path(
        "addresses/create/<str:entity_type>/<uuid:entity_id>/",
        views.address_create_for_entity,
        name="address_create",
    ),
    path("addresses/<uuid:address_id>/edit/", views.address_edit, name="address_edit"),
    path(
        "addresses/<uuid:address_id>/deactivate/",
        views.address_deactivate,
        name="address_deactivate",
    ),
]
