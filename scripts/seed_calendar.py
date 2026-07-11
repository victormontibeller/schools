"""Popula o calendário acadêmico realista de 2026 no tenant ``demo``.

Uso: ``python manage.py shell < scripts/seed_calendar.py``.
"""

from django_tenants.utils import tenant_context

from core.demo_seed import get_demo_seed_service
from tenancy.models import School

school = School.objects.get(schema_name="demo")
with tenant_context(school):
    get_demo_seed_service().populate_calendar()
