"""AccountSelector: consultas somente-leitura para usuários."""

from django.db.models import Q

from base.selectors import MAX_PAGE_SIZE, BaseSelector, PageResult


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

    def list_users(self, search="", order_by="first_name", page=1, page_size=20) -> PageResult:
        """Lista usuários com busca por nome/e-mail e paginação."""
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        qs = self.model_class.objects.select_related("role")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )
        qs = qs.order_by(order_by, "last_name")
        total = qs.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
