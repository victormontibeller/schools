"""Contrato público do domínio de notificações."""

from notifications.channels.smtp_recovery import send_recovery_email
from notifications.models import (
    Announcement,
    AnnouncementAttachment,
    AnnouncementRecipient,
    AnnouncementRevision,
    MessageLog,
    MessageTemplate,
    Notification,
    WebhookEventReceipt,
)

__all__ = [
    "send_recovery_email",
    "Announcement",
    "AnnouncementRevision",
    "AnnouncementRecipient",
    "AnnouncementAttachment",
    "MessageLog",
    "MessageTemplate",
    "Notification",
    "WebhookEventReceipt",
]
