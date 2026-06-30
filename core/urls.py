"""URLs principais do projeto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import dashboard, handler404, handler500, health, index

handler404 = handler404
handler500 = handler500

urlpatterns = [
    path("", index, name="index"),
    path("app/", dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("", include("accounts.urls")),
    path("", include("teachers.urls")),
    path("", include("students.urls")),
    path("", include("guardians.urls")),
    path("", include("classes.urls")),
    path("", include("rooms.urls")),
    path("", include("agenda.urls")),
    path("", include("activities.urls")),
    path("", include("academic_calendar.urls")),
    path("", include("attendance.urls")),
    path("", include("notifications.urls")),
    path("", include("dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
