"""GuardianSelector: consultas somente-leitura para responsáveis."""

from base.selectors import BaseSelector, PageResult


class GuardianSelector(BaseSelector):
    """Consultas somente-leitura para responsáveis."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from guardians.models import Guardian

        return Guardian

    def list_guardians(self, filters=None, page=1, page_size=20) -> PageResult:
        """Lista responsáveis com filtros e paginação."""
        return self.list(filters=filters, page=page, page_size=page_size)
