"""Provisiona ambiente local idempotente com public e tenant DEMO."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context, tenant_context

from base import context
from tenancy.contracts import Domain, School


class Command(BaseCommand):
    """Cria operadores, tenant DEMO, domínio e administrador local."""

    help = "Provisiona public e DEMO para desenvolvimento local"

    @staticmethod
    def _ensure_admin(user_model, *, email: str, password: str, defaults: dict):
        """Garante uma conta administrativa sem salvar novamente um usuário novo."""
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={**defaults, "password": make_password(password)},
        )
        if created:
            return user

        changed = False
        for field, value in defaults.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if not user.check_password(password):
            user.set_password(password)
            changed = True
        if changed:
            user.save()
        return user

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
                domain=settings.PLATFORM_DOMAIN,
                defaults={"tenant": public_school, "is_primary": True},
            )
            user_model = get_user_model()
            self._ensure_admin(
                user_model,
                email="platform-admin@schools.local",
                password=platform_password,
                defaults={
                    "first_name": "Platform",
                    "last_name": "Admin",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )

            demo, _ = School.objects.get_or_create(
                schema_name=getattr(settings, "DEMO_SCHEMA_NAME", "demo"),
                defaults={
                    "name": "Escola Demonstração",
                    "settings": {"student_diary": {"interactive_enabled": True}},
                },
            )
            demo_settings = dict(demo.settings)
            diary_settings = dict(demo_settings.get("student_diary", {}))
            diary_settings["interactive_enabled"] = True
            demo_settings["student_diary"] = diary_settings
            if demo.settings != demo_settings:
                demo.settings = demo_settings
                demo.save(update_fields=["settings", "updated_at"])
            Domain.objects.update_or_create(
                domain=f"{demo.schema_name}.{settings.TENANT_BASE_DOMAIN}",
                defaults={"tenant": demo, "is_primary": True},
            )

        with tenant_context(demo):
            tenant_token = context.current_tenant.set(demo.schema_name)
            try:
                from core.access.services import AccessConfigurationService
                from core.models import CustomUser, Role

                AccessConfigurationService().create_missing_access_defaults()

                role, _ = Role.objects.get_or_create(name=Role.Name.ADMIN)
                admin = self._ensure_admin(
                    CustomUser,
                    email="admin@demo.com",
                    password=demo_password,
                    defaults={
                        "first_name": "Admin",
                        "last_name": "Demo",
                        "role": role,
                        "is_staff": True,
                        "is_superuser": True,
                        "is_active": True,
                    },
                )

                from core.demo_seed import DemoSeedService

                demo_seed = DemoSeedService(user=admin)
                demo_seed.populate_core(demo)
                demo_seed.populate_calendar()
                demo_seed.populate_attendance()
                demo_seed.populate_finance()
            finally:
                context.current_tenant.reset(tenant_token)

        self.stdout.write(self.style.SUCCESS("Public e DEMO provisionados com sucesso."))
        self.stdout.write("Public: platform-admin@schools.local")
        self.stdout.write("DEMO: admin@demo.com")
