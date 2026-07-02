"""Tarefa Celery: importação em lote de alunos via CSV."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from celery import shared_task

from base.context import tenant_schema_context

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="students.import_students_csv")
def import_students_csv(
    self, tenant_schema: str, csv_content: str, created_by_id: str
) -> dict[str, Any]:
    """
    Importa alunos a partir de conteúdo CSV.

    Colunas esperadas: first_name, last_name, birth_date, enrollment_number,
                       gender (opcional), blood_type (opcional)
    Retorna: {"created": N, "errors": [{"row": N, "message": "..."}]}
    """
    with tenant_schema_context(tenant_schema):
        from core.models import CustomUser
        from students.services import StudentService

        try:
            user = CustomUser.all_objects.get(pk=created_by_id)
        except CustomUser.DoesNotExist:
            return {
                "created": 0,
                "errors": [{"row": 0, "message": "Usuário executor não encontrado."}],
            }

        service = StudentService(user=user)
        created = 0
        errors: list[dict] = []

        reader = csv.DictReader(io.StringIO(csv_content))
        for row_num, row in enumerate(reader, start=2):  # linha 1 = cabeçalho
            try:
                service.create_student(
                    {
                        "first_name": row.get("first_name", "").strip(),
                        "last_name": row.get("last_name", "").strip(),
                        "birth_date": row.get("birth_date", "").strip(),
                        "enrollment_number": row.get("enrollment_number", "").strip(),
                        "gender": row.get("gender", "NI").strip() or "NI",
                        "blood_type": row.get("blood_type", "").strip(),
                    }
                )
                created += 1
            except Exception as exc:
                logger.warning("Falha ao importar linha CSV %d: %s", row_num, exc)
                errors.append({"row": row_num, "message": str(exc)})

        logger.info(
            "Importação CSV concluída",
            extra={"created": created, "errors_count": len(errors)},
        )
        return {"created": created, "errors": errors}
