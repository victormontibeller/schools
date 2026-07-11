"""SchoolSelector: consultas somente-leitura para escolas."""

from base.selectors import BaseSelector, PageResult


class BusinessUnitSelector(BaseSelector):
    """Consultas read-only para empresas do tenant."""

    @property
    def model_class(self):
        from core.models import BusinessUnit

        return BusinessUnit

    def list_business_units(
        self, search: str = "", order_by: str = "name", page: int = 1, page_size: int = 20
    ) -> PageResult:
        """Lista unidades ativas do tenant, com busca e ordenação."""
        filters = {"name__icontains": search} if search else None
        return self.list(filters=filters, page=page, page_size=page_size, order_by=order_by)


class SchoolSelector(BaseSelector):
    """Consultas read-only para escolas."""

    @property
    def model_class(self):
        from tenancy.models import School

        return School

    def get_current_school(self):
        """Retorna a escola do tenant ativo, ou None."""
        from tenancy.models import School

        return School.objects.order_by("name").first()
