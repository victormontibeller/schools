"""Seed de demonstração: superuser (shared) + dados de exemplo no tenant `demo`.

Pré-requisitos (já executados pelo setup):
- `migrate_schemas --shared`
- tenant School(schema_name="demo") + Domain("localhost")
- `migrate_schemas` (fase tenant)

Uso: `python manage.py shell < scripts/seed_demo.py`
"""

import datetime as dt

from django_tenants.utils import tenant_context

from core.models import CustomUser, School

school = School.objects.get(schema_name="demo")
print(f"Tenant: {school.schema_name} | {school.name}")

# ── Superuser (compartilhado, vive no schema public) ───────────────────────────
admin, created = CustomUser.objects.get_or_create(
    email="admin@demo.com",
    defaults={"first_name": "Admin", "last_name": "Demo"},
)
if created:
    admin.set_password("Senha123")
    admin.save()
print(f"Superuser: {admin.email} (Senha123) — {'criado' if created else 'existente'}")

# ── Dados de demo no schema do tenant ──────────────────────────────────────────
with tenant_context(school):
    prof_user, _ = CustomUser.objects.get_or_create(
        email="professor@demo.com",
        defaults={"first_name": "Ana", "last_name": "Souza"},
    )
    if not prof_user.password:
        prof_user.set_password("Senha123")
        prof_user.save()

    from activities.models import Activity
    from agenda.models import TimeSlot
    from classes.models import Class, Enrollment
    from rooms.models import Room
    from students.models import Student
    from teachers.models import Subject, Teacher

    subject, _ = Subject.objects.get_or_create(
        code="MAT",
        defaults={"name": "Matemática", "workload": 120, "created_by": admin, "updated_by": admin},
    )

    teacher, _ = Teacher.objects.get_or_create(
        registration_number="PROF-001",
        defaults={
            "user": prof_user,
            "hire_date": dt.date(2022, 3, 1),
            "created_by": admin,
            "updated_by": admin,
        },
    )
    teacher.subjects.add(subject)

    for first, last, num, birth in [
        ("João", "Silva", "2026001", dt.date(2013, 5, 10)),
        ("Maria", "Oliveira", "2026002", dt.date(2013, 8, 22)),
    ]:
        Student.objects.get_or_create(
            enrollment_number=num,
            defaults={
                "first_name": first,
                "last_name": last,
                "birth_date": birth,
                "created_by": admin,
                "updated_by": admin,
            },
        )

    for code, name, cap, bld, flr, rtype in [
        ("SALA-01", "Sala 01", 35, "Bloco A", "Térreo", Room.Type.CLASSROOM),
        ("LAB-01", "Laboratório de Ciências", 25, "Bloco B", "1º Andar", Room.Type.LAB),
    ]:
        Room.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "capacity": cap,
                "type": rtype,
                "building": bld,
                "floor": flr,
                "created_by": admin,
                "updated_by": admin,
            },
        )

    for day, n, start, end in [
        ("MON", 1, dt.time(7, 30), dt.time(8, 20)),
        ("MON", 2, dt.time(8, 20), dt.time(9, 10)),
        ("TUE", 1, dt.time(7, 30), dt.time(8, 20)),
        ("WED", 1, dt.time(7, 30), dt.time(8, 20)),
        ("THU", 1, dt.time(7, 30), dt.time(8, 20)),
        ("FRI", 1, dt.time(7, 30), dt.time(8, 20)),
    ]:
        TimeSlot.objects.get_or_create(
            day_of_week=day,
            start_time=start,
            end_time=end,
            defaults={"slot_number": n, "created_by": admin, "updated_by": admin},
        )

    cls, _ = Class.objects.get_or_create(
        name="6º A",
        academic_year=2026,
        defaults={
            "grade": "6º ano",
            "shift": Class.Shift.MORNING,
            "max_students": 30,
            "class_teacher": teacher,
            "created_by": admin,
            "updated_by": admin,
        },
    )

    stud = Student.objects.get(enrollment_number="2026001")
    Enrollment.objects.get_or_create(
        student=stud,
        class_obj=cls,
        defaults={
            "enrollment_date": dt.date.today(),
            "status": Enrollment.Status.ACTIVE,
            "created_by": admin,
            "updated_by": admin,
        },
    )

    Activity.objects.get_or_create(
        title="Prova de Matemática — Unidade 1",
        class_obj=cls,
        defaults={
            "subject": subject,
            "teacher": teacher,
            "description": "Conteúdo: conjuntos e operações.",
            "type": Activity.Type.EXAM,
            "due_date": dt.date.today() + dt.timedelta(days=7),
            "max_score": 10,
            "weight": 1,
            "created_by": admin,
            "updated_by": admin,
        },
    )

    print(
        "Seed concluído: disciplina, professor, 2 alunos, 2 salas, 6 horários, 1 turma, 1 matrícula, 1 atividade."
    )
