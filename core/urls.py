"""URLs principais do projeto."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import (
    business_unit_create,
    business_unit_detail,
    business_unit_edit,
    business_unit_list,
    dashboard,
    handler404,
    handler500,
    health,
    index,
    metrics,
    school_detail,
    school_edit,
)

handler404 = handler404
handler500 = handler500

urlpatterns = [
    path("", index, name="index"),
    path("app/", dashboard, name="dashboard"),
    path("app/empresas/", business_unit_list, name="business_unit_list"),
    path("app/empresas/nova/", business_unit_create, name="business_unit_create"),
    path("app/empresas/<uuid:pk>/", business_unit_detail, name="business_unit_detail"),
    path("app/empresas/<uuid:pk>/editar/", business_unit_edit, name="business_unit_edit"),
    path("app/escola/", school_detail, name="school_settings_detail"),
    path("app/escola/editar/", school_edit, name="school_settings_edit"),
    path("app/empresa/", school_detail, name="school_detail"),
    path("app/empresa/editar/", school_edit, name="school_edit"),
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("metrics/", metrics, name="metrics"),
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
    path("", include("enrollments.urls")),
    path("", include("financeiro.urls")),
    path("", include("notifications.urls")),
    path("", include("dashboard.urls")),
    path("", include("addresses.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
