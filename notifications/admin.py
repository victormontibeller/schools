from django.contrib import admin

from notifications.models import Announcement, MessageLog, MessageTemplate, Notification


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "channel", "type", "created_at"]
    list_filter = ["channel", "type"]
    search_fields = ["name"]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "audience", "author", "sent_at", "created_at"]
    list_filter = ["audience", "send_email", "send_whatsapp"]
    search_fields = ["title"]


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
