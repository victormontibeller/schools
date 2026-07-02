"""TeacherSelector: consultas somente-leitura para professores."""

from base.selectors import BaseSelector, PageResult


class TeacherSelector(BaseSelector):
    """Consultas somente-leitura para professores."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from teachers.models import Teacher

        return Teacher

    def list_teachers(self, filters=None, page=1, page_size=20) -> PageResult:
        """Lista professores com filtros e paginação."""
        return self.list(filters=filters, page=page, page_size=page_size)

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

    def list_subjects(self, filters=None, page=1, page_size=50) -> PageResult:
        """Lista disciplinas com filtros e paginação."""
        return self.list(filters=filters, page=page, page_size=page_size)
