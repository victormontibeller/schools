from django.contrib import admin

from notifications.models import Announcement, MessageLog, MessageTemplate, Notification


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "channel", "type", "created_at"]
    list_filter = ["channel", "type"]
    search_fields = ["name"]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "audience", "author", "published_at", "created_at"]
    list_filter = ["audience", "status"]
    search_fields = ["title"]
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "recipient", "type", "source", "read_at", "created_at"]
    list_filter = ["type", "source"]
    search_fields = ["title", "recipient__email"]
    readonly_fields = ["correlation_id"]


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ["channel", "recipient_address", "status", "created_at"]
    list_filter = ["channel", "status"]
    search_fields = ["recipient_address"]

    fields = (
        "id",
        "channel",
        "status",
        "dispatch_state",
        "reason_code",
        "attempts",
        "created_at",
        "updated_at",
    )
    readonly_fields = fields
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
