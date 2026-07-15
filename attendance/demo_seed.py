"""Seed DEMO de frequência escolar."""

import datetime as dt


class AttendanceDemoSeedMixin:
    """Cria registros demonstrativos de frequência."""

    def populate_attendance(self) -> int:
        """Cria vinte chamadas completas e seus lançamentos individuais."""
        from attendance.contracts import AttendanceEntry, AttendanceRecord
        from classes.contracts import Class, Enrollment
        from teachers.contracts import Subject, Teacher

        class_subjects = [("6º A", "MAT"), ("6º B", "POR"), ("7º A", "CIE")]
        teacher_registrations = {
            "MAT": "PROF-2026-001",
            "POR": "PROF-2026-002",
            "CIE": "PROF-2026-003",
        }
        dates = [
            dt.date(2026, 3, day)
            for day in (2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 23, 24, 25, 26, 27)
        ]
        for index, date in enumerate(dates):
            class_name, subject_code = class_subjects[index % len(class_subjects)]
            cls = Class.objects.get(name=class_name, academic_year=2026)
            subject = Subject.objects.get(code=subject_code)
            teacher = Teacher.objects.get(registration_number=teacher_registrations[subject_code])
            record = self._ensure(
                AttendanceRecord,
                {"class_obj": cls, "date": date, "lesson_number": 1},
                {
                    "subject": subject,
                    "teacher": teacher,
                    "lesson_content": "Conteúdo da aula DEMO.",
                    "notes": "Chamada DEMO preenchida.",
                },
            )
            for student_index, student_id in enumerate(
                Enrollment.objects.filter(
                    class_obj=cls, status=Enrollment.Status.ACTIVE
                ).values_list("student_id", flat=True)
            ):
                status = (
                    AttendanceEntry.Status.JUSTIFIED
                    if (index + student_index) % 17 == 0
                    else (
                        AttendanceEntry.Status.ABSENT
                        if (index + student_index) % 11 == 0
                        else AttendanceEntry.Status.PRESENT
                    )
                )
                self._ensure(
                    AttendanceEntry,
                    {"record": record, "student_id": student_id},
                    {
                        "status": status,
                        "justification": (
                            "Consulta médica" if status == AttendanceEntry.Status.JUSTIFIED else ""
                        ),
                    },
                )
        return len(dates)
