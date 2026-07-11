from django.urls import path

from notifications import views

urlpatterns = [
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
    path("announcements/", views.announcement_list, name="announcement_list"),
    path("announcements/<uuid:pk>/", views.announcement_detail, name="announcement_detail"),
]
