"""TeacherSelector: consultas somente-leitura para professores."""

from django.db.models import Q

from base.selectors import BaseSelector, PageResult


class TeacherSelector(BaseSelector):
    """Consultas somente-leitura para professores."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from teachers.models import Teacher

        return Teacher

    def list_teachers(
        self, search="", order_by="user__first_name", page=1, page_size=20
    ) -> PageResult:
        """Lista professores com busca por nome e paginação."""
        qs = self.model_class.objects.select_related("user").prefetch_related("subjects")
        if search:
            qs = qs.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(registration_number__icontains=search)
                | Q(cpf__icontains=search)
            )
        qs = qs.order_by(order_by, "user__last_name")
        return self._paginate(qs, page=page, page_size=page_size)

    def get_teacher_by_id(self, teacher_id):
        """Retorna o professor pelo id ou lança `ObjectNotFoundError`."""
        return self.get_by_id(teacher_id)

    def list_teacher_subjects(self, teacher_id):
        """Lista as disciplinas atribuídas ao professor informado."""
        teacher = self.get_by_id(teacher_id)
        return teacher.subjects.all()

    def search_by_cpf(self, cpf: str):
        """Busca professor por CPF."""
        from teachers.models import Teacher

        return Teacher.objects.filter(cpf__icontains=cpf).first()

    def search_by_name(self, query: str, page: int = 1) -> PageResult:
        """Busca professores por nome (via user)."""
        from django.db.models import Q

        from teachers.models import Teacher

        qs = Teacher.objects.select_related("user").filter(
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


class SubjectSelector(BaseSelector):
    """Consultas somente-leitura para disciplinas."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from teachers.models import Subject

        return Subject

    def list_subjects(
        self,
        filters=None,
        order_by="name",
        page=1,
        page_size=50,
        user_id=None,
        role_name: str = "",
    ) -> PageResult:
        """Lista disciplinas com filtros e paginação."""
        if role_name != "TEACHER":
            return self.list(filters=filters, order_by=order_by, page=page, page_size=page_size)
        queryset = self.model_class.objects.filter(
            teachers__user_id=user_id,
            **(filters or {}),
        ).distinct()
        return self._paginate(queryset.order_by(order_by), page=page, page_size=page_size)

    @staticmethod
    def teacher_can_access_subject(user_id, subject_id) -> bool:
        """Confirma atribuição da disciplina ao professor autenticado."""
        from teachers.models import Subject

        return Subject.objects.filter(pk=subject_id, teachers__user_id=user_id).exists()

    @staticmethod
    def _paginate(queryset, *, page: int, page_size: int) -> PageResult:
        """Pagina o queryset restrito sem expor ORM à view."""
        from base.selectors import MAX_PAGE_SIZE

        page = max(1, page)
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        total = queryset.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
