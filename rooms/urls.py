"""URLs do módulo de salas."""

from django.urls import path

from rooms import views

urlpatterns = [
    path("rooms/", views.rooms_list, name="rooms_list"),
    path("rooms/nova/", views.room_create, name="room_create"),
    path("rooms/<uuid:pk>/", views.room_detail, name="room_detail"),
    path("rooms/<uuid:pk>/editar/", views.room_edit, name="room_edit"),
]
