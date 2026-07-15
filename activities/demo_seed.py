"""Seed DEMO de atividades e resultados."""

import datetime as dt
from decimal import Decimal


class ActivityDemoSeedMixin:
    """Cria atividades e submissões demonstrativas."""

    def populate_activities(self, *, classes, class_specs, subjects, teachers) -> None:
        from activities.contracts import Activity, ActivitySubmission

        for class_index, cls in enumerate(classes):
            for activity_index, (activity_type, title) in enumerate(
                (
                    (Activity.Type.HOMEWORK, "Lista de exercícios"),
                    (Activity.Type.PROJECT, "Projeto interdisciplinar"),
                ),
                start=1,
            ):
                subject_code = ("MAT", "POR", "CIE")[class_index]
                description = (
                    f"Atividade DEMO de {subjects[subject_code].name.lower()} "
                    "com critérios de avaliação descritos."
                )
                activity = self._ensure(
                    Activity,
                    {"class_obj": cls, "title": title},
                    {
                        "subject": subjects[subject_code],
                        "teacher": teachers[subject_code],
                        "description": description,
                        "type": activity_type,
                        "due_date": dt.date(2026, 3 + class_index, 10 + activity_index),
                        "max_score": Decimal("10.00"),
                        "weight": Decimal("1.00"),
                    },
                )
                for student_index, student in enumerate(class_specs[class_index][4], start=1):
                    self._ensure(
                        ActivitySubmission,
                        {"activity": activity, "student": student},
                        {
                            "score": Decimal(f"{7 + ((student_index + activity_index) % 3)}.00"),
                            "feedback": "Bom domínio dos objetivos de aprendizagem.",
                            "submitted_at": dt.datetime(
                                2026,
                                3 + class_index,
                                8 + activity_index,
                                14,
                                0,
                                tzinfo=dt.UTC,
                            ),
                        },
                    )
