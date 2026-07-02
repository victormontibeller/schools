"""StudentSelector: consultas somente-leitura para alunos."""

from base.selectors import BaseSelector, PageResult


class StudentSelector(BaseSelector):
    """Consultas somente-leitura para alunos."""

    @property
    def model_class(self):
        """Modelo alvo das consultas deste seletor."""
        from students.models import Student

        return Student

    def list_students(self, filters=None, page=1, page_size=20) -> PageResult:
        """Lista alunos com filtros e paginação."""
        return self.list(filters=filters, page=page, page_size=page_size)

    def get_student_by_id(self, student_id):
        """Retorna o aluno pelo id ou lança `ObjectNotFoundError`."""
        return self.get_by_id(student_id)

    def get_student_guardians(self, student_id):
        """Retorna vinculos de responsaveis do aluno, com dados do guardian e user."""
        student = self.get_by_id(student_id)
        return student.guardians.select_related("guardian__user").all()

    def get_student_by_enrollment(self, enrollment_number: str):
        """Retorna o aluno portador da matrícula informada, ou `None`."""
        from students.models import Student

        return Student.objects.filter(enrollment_number=enrollment_number).first()

    def search_by_cpf(self, cpf: str):
        """Busca aluno por CPF."""
        from students.models import Student

        return Student.objects.filter(cpf__icontains=cpf).first()

    def search_by_email(self, email: str):
        """Busca aluno por email."""
        from students.models import Student

        return Student.objects.filter(email__iexact=email).first()

    def search_by_name(self, query: str, page: int = 1) -> PageResult:
        """Busca alunos por nome."""
        from django.db.models import Q

        from students.models import Student

        qs = Student.objects.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
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
