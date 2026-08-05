"""Popula pessoas, estrutura e atividades realistas no tenant ``demo``.

Uso: ``python manage.py shell < scripts/seed_demo.py``.
"""

from django_tenants.utils import tenant_context

from core.demo_seed import DemoSeedService
from core.models import CustomUser
from tenancy.models import School

school = School.objects.get(schema_name="demo")
with tenant_context(school):
    admin = CustomUser.objects.filter(
        email="admin@demo.com",
        role__name="ADMIN",
        is_active=True,
    ).first()
    if admin is None:
        raise RuntimeError(
            "Administrador DEMO ausente. Execute `python manage.py seed_dev` primeiro."
        )
    service = DemoSeedService(user=admin)
    service.populate_core(school)
    service.populate_calendar()
    service.populate_attendance()
    service.populate_finance()
