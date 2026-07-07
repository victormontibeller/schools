"""Admin do app locations."""

from django.contrib import admin

from locations.models import City, State


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by", "version")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "ibge_code", "is_active")
    search_fields = ("name", "ibge_code")
    list_filter = ("state", "is_active")
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by", "version")
