"""SchoolSelector: consultas somente-leitura para escolas."""

from base.selectors import BaseSelector


class SchoolSelector(BaseSelector):
    """Consultas read-only para escolas."""

    @property
    def model_class(self):
        from core.models import School

        return School

    def get_current_school(self):
        """Retorna a escola do tenant ativo, ou None."""
        from core.models import School

        return School.objects.first()
