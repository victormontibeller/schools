from django.urls import path

from notifications import announcement_views, delivery_views, views

urlpatterns = [
    path(
        "communications/deliveries/",
        delivery_views.communication_delivery_list,
        name="communication_delivery_list",
    ),
    path(
        "communications/deliveries/<uuid:pk>/retry/",
        delivery_views.communication_delivery_retry,
        name="communication_delivery_retry",
    ),
    path("webhooks/resend/email/", views.resend_email_webhook, name="resend_email_webhook"),
    path("notifications/", views.notification_list, name="notification_list"),
    path(
        "notifications/<uuid:pk>/read/",
        views.notification_mark_read,
        name="notification_mark_read",
    ),
    path(
        "notifications/mark-all-read/",
        views.notification_mark_all_read,
        name="notification_mark_all_read",
    ),
    path("notifications/unread-count/", views.unread_count, name="unread_count"),
    path("announcements/new/", announcement_views.announcement_create, name="announcement_create"),
    path(
        "announcements/<uuid:pk>/edit/",
        announcement_views.announcement_edit,
        name="announcement_edit",
    ),
    path(
        "announcements/<uuid:pk>/action/",
        announcement_views.announcement_action,
        name="announcement_action",
    ),
    path(
        "announcements/<uuid:pk>/upload/",
        announcement_views.announcement_upload,
        name="announcement_upload",
    ),
    path(
        "announcements/attachments/<uuid:pk>/",
        announcement_views.announcement_attachment,
        name="announcement_attachment",
    ),
    path(
        "announcements/revisions/<uuid:pk>/acknowledge/",
        announcement_views.announcement_acknowledge,
        name="announcement_acknowledge",
    ),
    path(
        "announcements/deliveries/<uuid:pk>/retry/",
        announcement_views.announcement_retry,
        name="announcement_retry",
    ),
    path("announcements/", announcement_views.announcement_list, name="announcement_list"),
    path(
        "announcements/<uuid:pk>/",
        announcement_views.announcement_detail,
        name="announcement_detail",
    ),
]
