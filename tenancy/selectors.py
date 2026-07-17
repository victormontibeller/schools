"""Selectors somente-leitura do catálogo compartilhado de tenants."""

from django.db.models import Q

from base.exceptions import ObjectNotFoundError
from base.selectors import BaseSelector, PageResult


class SchoolSelector(BaseSelector):
    """Consultas de escolas no schema público."""

    @property
    def model_class(self):
        from tenancy.models import School

        return School

    def list_active(self, page: int = 1, page_size: int = 50) -> PageResult:
        """Lista escolas ativas para operadores da plataforma."""
        return self.list(page=page, page_size=page_size, order_by="name")

    def get_current_school(self):
        """Retorna a escola correspondente à conexão atual."""
        from django.db import connection

        from tenancy.models import School

        schema = getattr(connection, "schema_name", "public")
        return School.objects.filter(schema_name=schema).first()

    def get_platform_overview(self) -> dict:
        """Retorna indicadores seguros do catálogo compartilhado."""
        from tenancy.models import Domain, School

        tenant_scope = School.all_objects.exclude(schema_name="public")
        return {
            "total_tenants": tenant_scope.count(),
            "active_tenants": tenant_scope.filter(
                is_active=True,
                deleted_at__isnull=True,
            ).count(),
            "total_domains": Domain.objects.exclude(tenant__schema_name="public").count(),
        }

    def list_platform_tenants(
        self,
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PageResult:
        """Lista escolas da plataforma sem incluir o schema público."""
        from tenancy.models import School

        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        queryset = (
            School.all_objects.exclude(schema_name="public")
            .prefetch_related("domains")
            .order_by("name")
        )
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(schema_name__icontains=search))
        total = queryset.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_platform_school(self, school_id):
        """Retorna uma escola provisionada, excluindo o schema público."""
        from tenancy.models import School

        try:
            return (
                School.all_objects.exclude(schema_name="public")
                .prefetch_related("domains")
                .get(pk=school_id)
            )
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", str(school_id)) from None

    def get_active_by_schema(self, schema_name: str):
        """Resolve um tenant ativo para integrações assinadas no schema público."""
        from tenancy.models import School

        try:
            return School.objects.get(
                schema_name=schema_name,
                is_active=True,
                deleted_at__isnull=True,
            )
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", schema_name) from None
