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
