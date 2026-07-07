"""GuardianSelector: consultas somente-leitura para responsáveis."""

from django.db.models import Q

from base.selectors import BaseSelector, PageResult


class GuardianSelector(BaseSelector):
    """Consultas somente-leitura para responsáveis."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from guardians.models import Guardian

        return Guardian

    def list_guardians(
        self, search="", order_by="user__first_name", page=1, page_size=20
    ) -> PageResult:
        """Lista responsáveis com busca por nome e paginação."""
        qs = self.model_class.objects.select_related("user").prefetch_related("students__student")
        if search:
            qs = qs.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(cpf__icontains=search)
            )
        qs = qs.order_by(order_by, "user__last_name")
        return self._paginate(qs, page=page, page_size=page_size)

    def get_guardian_students(self, guardian_id):
        """Retorna alunos vinculados ao responsavel, com dados do aluno."""
        guardian = self.get_by_id(guardian_id)
        return guardian.students.select_related("student").all()

    def search_by_cpf(self, cpf: str):
        """Busca responsavel por CPF."""
        from guardians.models import Guardian

        return Guardian.objects.filter(cpf__icontains=cpf).first()

    def search_by_phone(self, phone: str):
        """Busca responsavel por telefone/celular."""
        from django.db.models import Q

        from guardians.models import Guardian

        return Guardian.objects.filter(
            Q(phone__icontains=phone)
            | Q(phone_whatsapp__icontains=phone)
            | Q(phone_mobile__icontains=phone)
        ).first()

    def search_by_name(self, query: str, page: int = 1) -> PageResult:
        """Busca responsaveis por nome (via user)."""
        from django.db.models import Q

        from guardians.models import Guardian

        qs = Guardian.objects.select_related("user").filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
        )
        return self._paginate(qs, page=page)

    def _paginate(self, qs, page: int = 1, page_size: int = 20) -> PageResult:
        """Paginação interna para querysets customizados."""
        from base.selectors import MAX_PAGE_SIZE

        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        total = qs.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(qs[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
