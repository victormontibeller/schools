"""AccountSelector: consultas somente-leitura para usuários."""

from base.selectors import BaseSelector, PageResult


class AccountSelector(BaseSelector):
    """Consultas somente-leitura para usuários."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from core.models import CustomUser

        return CustomUser

    def get_user_by_email(self, email: str):
        """Retorna o usuário portador do e-mail informado, ou `None`."""
        from core.models import CustomUser

        return CustomUser.objects.filter(email=email).first()

    def list_users(self, filters=None, page=1, page_size=20) -> PageResult:
        """Lista usuários com filtros e paginação."""
        return self.list(filters=filters, page=page, page_size=page_size)
