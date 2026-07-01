"""Seed de frequência: uma chamada com ambos os alunos da turma 6º A."""

import datetime as dt

from django_tenants.utils import tenant_context

from core.models import School

school = School.objects.get(schema_name="demo")

with tenant_context(school):
    from classes.models import Class, Enrollment
    from teachers.models import Subject, Teacher

    cls = Class.objects.get(name="6º A", academic_year=2026)
    subject = Subject.objects.get(code="MAT")
    teacher = Teacher.objects.get()

    from attendance.services import AttendanceService

    svc = AttendanceService()
    # Data letiva — usa um dia útil arbitrário.
    record = svc.open_attendance(
        {
            "class_id": cls.pk,
            "subject_id": subject.pk,
            "teacher_id": teacher.pk,
            "date": dt.date(2026, 3, 16),
            "lesson_number": 1,
            "notes": "Chamada de demonstração.",
        }
    )
    print("Registro aberto:", record)

    # Marca: primeiro aluno presente, segundo ausente (justificado por while).
    students = list(
        Enrollment.objects.filter(class_obj=cls, status=Enrollment.Status.ACTIVE)
        .select_related("student")
        .order_by("student__first_name")
    )
    if len(students) >= 2:
        entries_data = {
            str(students[0].student_id): {"status": "PRESENT", "justification": ""},
            str(students[1].student_id): {"status": "ABSENT", "justification": ""},
        }
        svc.record_attendance(record.pk, entries_data)
        print("Chamada registrada:", entries_data)

    # Submete uma justificativa pendente para o 2º aluno.
    from students.models import Student

    stu2 = students[1].student if len(students) >= 2 else Student.objects.first()
    if stu2:
        just = AttendanceService().submit_justification(
            {
                "student_id": stu2.pk,
                "start_date": dt.date(2026, 3, 16),
                "end_date": dt.date(2026, 3, 16),
                "reason": "Consulta médica",
            }
        )
        print("Justificativa:", just)

    # Calcula frequência do 1º aluno na turma.
    if students:
        rate = svc.calculate_attendance_rate(students[0].student_id, cls.pk)
        print(f"Frequência {students[0].student.get_full_name()}: {rate}%")
    print("Seed de frequência concluído.")
