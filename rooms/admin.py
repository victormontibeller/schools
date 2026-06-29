"""Configuração do Django Admin para salas."""

from django.contrib import admin

from rooms.models import Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    """Admin para listar e buscar salas rapidamente."""

    list_display = ["code", "name", "capacity", "type", "building", "floor"]
    list_filter = ["type", "building"]
    search_fields = ["name", "code"]
    ordering = ["building", "floor", "name"]
