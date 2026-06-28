"""Testes do `students/tasks.py` — importação CSV via Celery."""

import pytest

from students.tasks import import_students_csv


@pytest.mark.django_db
class TestImportStudentsCsv:
    HEADER = "first_name,last_name,birth_date,enrollment_number,gender,blood_type\n"

    def _csv(self, rows: list[list[str]]) -> str:
        lines = [self.HEADER] + [",".join(r) for r in rows]
        return "\n".join(lines) + "\n"

    def test_valid_rows_create_students(self, user):
        csv_content = self._csv(
            [
                ["Ana", "Silva", "2010-01-01", "IMP-001", "F", ""],
                ["Bruno", "Souza", "2011-05-10", "IMP-002", "M", ""],
            ]
        )
        result = import_students_csv.apply(args=[csv_content, str(user.pk)]).get()

        assert result["created"] == 2
        assert result["errors"] == []

        from students.models import Student

        assert Student.objects.filter(enrollment_number__startswith="IMP-").count() == 2

    def test_invalid_rows_reported_but_valid_rows_created(self, user):
        # Linha 2: faltando campos obrigatórios (linha em branco / lacks required fields).
        # Linha 3: matrícula duplicada com a linha 2.
        rows = [
            ["Ana", "Silva", "2010-01-01", "IMP-OK1", "F", ""],
            ["", "", "", "", "", ""],  # invalid — esperar ValidationError
            ["Bruno", "Souza", "2011-05-10", "IMP-1", "M", ""],
            ["Bruno2", "Souza", "2011-05-10", "IMP-1", "M", ""],  # duplicate
        ]
        csv_content = self._csv(rows)
        result = import_students_csv.apply(args=[csv_content, str(user.pk)]).get()

        # Linhas válidas: 1 + 3 → 2 criados; linha 4 falha (duplicate).
        # Linha 2 (vazia) falha por ValidationError.
        assert result["created"] >= 1
        assert len(result["errors"]) >= 1

    def test_creator_not_found(self):
        import uuid

        result = import_students_csv.apply(
            args=["coluna,foo\nAna,Silva\n", str(uuid.uuid4())]
        ).get()
        assert result["created"] == 0
        assert "Usuário executor" in result["errors"][0]["message"]

    def test_empty_csv(self, user):
        csv_content = self.HEADER  # só o cabeçalho, sem rows
        result = import_students_csv.apply(args=[csv_content, str(user.pk)]).get()
        assert result["created"] == 0
        assert result["errors"] == []
