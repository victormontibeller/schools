"""Admin do modulo de enderecos."""

from django.contrib import admin

from addresses.models import (
    Address,
    GuardianAddress,
    SchoolAddress,
    StudentAddress,
    TeacherAddress,
)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("street", "number", "city", "state", "postal_code", "is_active")
    list_filter = ("state", "city", "is_active")
    search_fields = ("street", "district", "city", "postal_code")
    readonly_fields = ("id", "created_at", "updated_at", "created_by", "updated_by", "version")


@admin.register(SchoolAddress)
class SchoolAddressAdmin(admin.ModelAdmin):
    list_display = ("school", "address", "is_primary", "is_active")
    list_filter = ("is_active",)


@admin.register(TeacherAddress)
class TeacherAddressAdmin(admin.ModelAdmin):
    list_display = ("teacher", "address", "is_primary", "is_active")
    list_filter = ("is_active",)


@admin.register(StudentAddress)
class StudentAddressAdmin(admin.ModelAdmin):
    list_display = ("student", "address", "is_primary", "is_active")
    list_filter = ("is_active",)


@admin.register(GuardianAddress)
class GuardianAddressAdmin(admin.ModelAdmin):
    list_display = ("guardian", "address", "is_primary", "is_active")
    list_filter = ("is_active",)
