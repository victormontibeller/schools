"""Provisiona ambiente local idempotente com public e tenant DEMO."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context, tenant_context

from tenancy.models import Domain, School


class Command(BaseCommand):
    """Cria operadores, tenant DEMO, domínio e administrador local."""

    help = "Provisiona public e DEMO para desenvolvimento local"

    def handle(self, *args, **options):
        """Executa o provisionamento sem duplicar registros."""
        platform_password = settings.DEV_PLATFORM_ADMIN_PASSWORD
        demo_password = settings.DEV_DEMO_ADMIN_PASSWORD
        if not platform_password or not demo_password:
            raise CommandError(
                "Defina DEV_PLATFORM_ADMIN_PASSWORD e DEV_DEMO_ADMIN_PASSWORD no ambiente."
            )
        with schema_context("public"):
            public_school, _ = School.objects.get_or_create(
                schema_name="public",
                defaults={"name": "School Manager Platform"},
            )
            Domain.objects.update_or_create(
                domain="platform.localhost",
                defaults={"tenant": public_school, "is_primary": True},
            )
            user_model = get_user_model()
            platform_user, _ = user_model.objects.get_or_create(
                email="platform-admin@schools.local",
                defaults={
                    "first_name": "Platform",
                    "last_name": "Admin",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            platform_user.is_staff = True
            platform_user.is_superuser = True
            platform_user.is_active = True
            platform_user.set_password(platform_password)
            platform_user.save()

            demo, _ = School.objects.get_or_create(
                schema_name=getattr(settings, "DEMO_SCHEMA_NAME", "demo"),
                defaults={"name": "Escola Demonstração"},
            )
            Domain.objects.update_or_create(
                domain="demo.localhost",
                defaults={"tenant": demo, "is_primary": True},
            )
            Domain.objects.update_or_create(
                domain="localhost",
                defaults={"tenant": demo, "is_primary": False},
            )

        with tenant_context(demo):
            from core.models import CustomUser, Role

            role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
            admin, _ = CustomUser.objects.get_or_create(
                email="admin@demo.com",
                defaults={
                    "first_name": "Admin",
                    "last_name": "Demo",
                    "role": role,
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            admin.role = role
            admin.is_staff = True
            admin.is_superuser = True
            admin.is_active = True
            admin.set_password(demo_password)
            admin.save()

        self.stdout.write(self.style.SUCCESS("Public e DEMO provisionados com sucesso."))
        self.stdout.write("Public: platform-admin@schools.local")
        self.stdout.write("DEMO: admin@demo.com")
