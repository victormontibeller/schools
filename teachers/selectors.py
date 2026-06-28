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
