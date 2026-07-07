"""SchoolSelector: consultas somente-leitura para escolas."""

from base.selectors import BaseSelector, PageResult


class BusinessUnitSelector(BaseSelector):
    """Consultas read-only para empresas do tenant."""

    @property
    def model_class(self):
        from core.models import BusinessUnit

        return BusinessUnit

    def list_business_units(self, page=1, page_size=20) -> PageResult:
        """Lista empresas ativas do tenant."""
        return self.list(page=page, page_size=page_size, order_by="name")


class SchoolSelector(BaseSelector):
    """Consultas read-only para escolas."""

    @property
    def model_class(self):
        from core.models import School

        return School

    def get_current_school(self):
        """Retorna a escola do tenant ativo, ou None."""
        from core.models import School

        return School.objects.order_by("name").first()
