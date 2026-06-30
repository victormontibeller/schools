from django.contrib import admin

from dashboard.models import DashboardWidget


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ["name", "widget_type", "datasource", "refresh_interval", "is_visible"]
    list_filter = ["widget_type", "is_visible"]
    search_fields = ["name", "datasource"]
