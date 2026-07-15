"""Views públicas do domínio core."""

from core.views.access import access_settings
from core.views.dashboard import dashboard
from core.views.organization import (
    business_unit_create,
    business_unit_detail,
    business_unit_edit,
    business_unit_list,
    school_detail,
    school_edit,
)
from core.views.public import handler404, handler500, health, index, metrics, readiness

__all__ = [
    "access_settings",
    "business_unit_create",
    "business_unit_detail",
    "business_unit_edit",
    "business_unit_list",
    "dashboard",
    "handler404",
    "handler500",
    "health",
    "index",
    "metrics",
    "readiness",
    "school_detail",
    "school_edit",
]
