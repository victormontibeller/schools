"""Serviço idempotente que popula o tenant DEMO com dados educacionais de 2026."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from base.services import BaseService


class DemoSeedService(BaseService):
    """Cria e reconcilia o conjunto determinístico de dados do tenant DEMO."""

    def _ensure(self, model, lookup: dict[str, Any], values: dict[str, Any]):
        """Cria ou atualiza uma entidade DEMO, restaurando-a quando necessário."""
        instance = model.all_objects.filter(**lookup).first()
        if instance is None:
            instance = model.objects.create(
                **{**lookup, **values}, created_by=self.user, updated_by=self.user
            )
            self._record_audit("INSERT", instance)
            self._log("demo_seed_created", entity_type=model.__name__, entity_id=str(instance.pk))
            return instance

        old = self._snapshot(instance, list(values))
        changed = False
        for field, value in values.items():
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                changed = True
        if instance.is_deleted:
            instance.deleted_at = None
            instance.deleted_by = None
            instance.is_active = True
            changed = True
        if changed:
            instance.updated_by = self.user
            instance.version += 1
            instance.save()
            self._record_audit("UPDATE", instance, old_values=old)
            self._log("demo_seed_updated", entity_type=model.__name__, entity_id=str(instance.pk))
        return instance

    def _ensure_address(self, link_model, entity_field: str, entity, data: dict[str, str]):
        """Garante um endereço principal e o vínculo com sua entidade proprietária."""
        from addresses.models import Address

        address = self._ensure(Address, {"recipient": data["recipient"]}, data)
        self._ensure(
            link_model,
            {entity_field: entity, "address": address},
            {"is_primary": True},
        )
        return address

    def populate_core(self, school) -> dict[str, int]:
        """Popula escola, unidades, pessoas, turmas, salas e atividades do DEMO."""
        from activities.models import Activity, ActivitySubmission
        from addresses.models import (
            BusinessUnitAddress,
            GuardianAddress,
            SchoolAddress,
            StudentAddress,
            TeacherAddress,
        )
        from classes.models import Class, Enrollment
        from core.models import BusinessUnit, CustomUser, Role
        from guardians.models import Guardian, StudentGuardian
        from rooms.models import Room
        from students.models import Student
        from teachers.models import Subject, Teacher

        teacher_role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
        school_data = {
            "name": "Colégio Horizonte Paulista",
            "cnpj": "12.345.678/0001-95",
            "legal_name": "Horizonte Paulista Educação Básica Ltda.",
            "trade_name": "Colégio Horizonte Paulista",
            "state_registration": "114.782.390.118",
            "municipal_registration": "5.812.904-7",
            "phone": "(11) 3456-7800",
            "email": "contato@colegiohorizonte.demo",
            "contact_full_name": "Marina de Almeida",
            "contact_role": "Diretora Pedagógica",
            "contact_phone": "(11) 3456-7801",
            "contact_email": "diretoria@colegiohorizonte.demo",
            "academic_year_start": dt.date(2026, 2, 2),
            "academic_year_end": dt.date(2026, 12, 18),
            "address": {
                "street": "Rua das Acácias",
                "number": "450",
                "district": "Vila Mariana",
                "city": "São Paulo",
                "state": "SP",
                "postal_code": "04010-010",
            },
            "settings": {"timezone": "America/Sao_Paulo", "locale": "pt_BR"},
        }
        for field, value in school_data.items():
            setattr(school, field, value)
        school.save()
        self._ensure_address(
            SchoolAddress,
            "school",
            school,
            {
                "recipient": "Colégio Horizonte Paulista",
                "street": "Rua das Acácias",
                "number": "450",
                "complement": "Prédio principal",
                "district": "Vila Mariana",
                "postal_code": "04010-010",
                "city": "São Paulo",
                "state": "SP",
            },
        )

        units = [
            ("Unidade Vila Mariana", "12.345.678/0002-76", "Rua das Acácias", "450"),
            ("Unidade Saúde", "12.345.678/0003-57", "Avenida Jabaquara", "1680"),
        ]
        for name, cnpj, street, number in units:
            unit = self._ensure(
                BusinessUnit,
                {"name": name},
                {
                    "cnpj": cnpj,
                    "legal_name": f"Horizonte Paulista Educação Básica Ltda. — {name}",
                    "trade_name": name,
                    "state_registration": "114.782.390.118",
                    "municipal_registration": "5.812.904-7",
                    "phone": "(11) 3456-7800",
                    "email": f"{name.lower().replace(' ', '.')}@colegiohorizonte.demo",
                    "contact_full_name": "Marina de Almeida",
                    "contact_role": "Diretora Pedagógica",
                    "contact_phone": "(11) 3456-7801",
                    "contact_email": "diretoria@colegiohorizonte.demo",
                    "academic_year_start": dt.date(2026, 2, 2),
                    "academic_year_end": dt.date(2026, 12, 18),
                },
            )
            self._ensure_address(
                BusinessUnitAddress,
                "business_unit",
                unit,
                {
                    "recipient": name,
                    "street": street,
                    "number": number,
                    "complement": "Recepção",
                    "district": "Vila Mariana" if "Mariana" in name else "Saúde",
                    "postal_code": "04010-010" if "Mariana" in name else "04002-003",
                    "city": "São Paulo",
                    "state": "SP",
                },
            )

        subjects_data = [
            ("MAT", "Matemática", 160),
            ("POR", "Língua Portuguesa", 160),
            ("CIE", "Ciências", 120),
            ("HIS", "História", 100),
            ("GEO", "Geografia", 100),
            ("ING", "Língua Inglesa", 80),
            ("ART", "Arte", 60),
            ("EDF", "Educação Física", 80),
            ("TEC", "Tecnologia e Inovação", 60),
            ("FIL", "Projeto de Vida", 40),
        ]
        subjects = {
            code: self._ensure(Subject, {"code": code}, {"name": name, "workload": workload})
            for code, name, workload in subjects_data
        }
        teachers_data = [
            ("PROF-2026-001", "Ana", "Carvalho", "MAT", "111.444.777-35"),
            ("PROF-2026-002", "Bruno", "Mendes", "POR", "529.982.247-25"),
            ("PROF-2026-003", "Carla", "Nogueira", "CIE", "168.995.350-09"),
            ("PROF-2026-004", "Diego", "Ramos", "HIS", "453.178.287-91"),
            ("PROF-2026-005", "Elisa", "Freitas", "GEO", "111.444.777-35"),
            ("PROF-2026-006", "Felipe", "Azevedo", "ING", "529.982.247-25"),
            ("PROF-2026-007", "Gabriela", "Lima", "ART", "168.995.350-09"),
            ("PROF-2026-008", "Henrique", "Costa", "EDF", "453.178.287-91"),
            ("PROF-2026-009", "Isabela", "Moraes", "TEC", "111.444.777-35"),
            ("PROF-2026-010", "João", "Pereira", "FIL", "529.982.247-25"),
        ]
        teachers: dict[str, Any] = {}
        for index, (registration, first, last, subject_code, cpf) in enumerate(
            teachers_data, start=1
        ):
            email = f"{first.lower()}.{last.lower()}@colegiohorizonte.demo"
            user = self._ensure(
                CustomUser,
                {"email": email},
                {
                    "first_name": first,
                    "last_name": last,
                    "phone": f"(11) 9{index:04d}-1000",
                    "role": teacher_role,
                },
            )
            teacher = self._ensure(
                Teacher,
                {"registration_number": registration},
                {
                    "user": user,
                    "hire_date": dt.date(2022, 2, 1),
                    "birth_date": dt.date(1980 + index, index, 10),
                    "gender": (
                        Teacher.Gender.FEMALE if index in {1, 3, 5, 7, 9} else Teacher.Gender.MALE
                    ),
                    "cpf": f"{cpf[:-2]}{index:02d}",
                    "rg_number": f"{32 + index}.456.7{index}0-{index}",
                    "rg_issuer": "SSP",
                    "rg_state": "SP",
                    "phone_mobile": f"(11) 9{index:04d}-1000",
                },
            )
            teacher.subjects.set([subjects[subject_code]])
            teachers[subject_code] = teacher
            self._ensure_address(
                TeacherAddress,
                "teacher",
                teacher,
                {
                    "recipient": teacher.full_name,
                    "street": "Rua dos Professores",
                    "number": str(100 + index),
                    "complement": "Apartamento 12",
                    "district": "Saúde",
                    "postal_code": "04002-003",
                    "city": "São Paulo",
                    "state": "SP",
                },
            )

        student_names = [
            ("2026001", "Lucas", "Alves"),
            ("2026002", "Mariana", "Santos"),
            ("2026003", "Pedro", "Rocha"),
            ("2026004", "Sofia", "Barbosa"),
            ("2026005", "Rafael", "Teixeira"),
            ("2026006", "Beatriz", "Moreira"),
            ("2026007", "Gustavo", "Ferreira"),
            ("2026008", "Helena", "Cardoso"),
            ("2026009", "Caio", "Martins"),
            ("2026010", "Laura", "Ribeiro"),
        ]
        students: list[Any] = []
        for index, (enrollment, first, last) in enumerate(student_names, start=1):
            student = self._ensure(
                Student,
                {"enrollment_number": enrollment},
                {
                    "first_name": first,
                    "last_name": last,
                    "birth_date": dt.date(2013, index, 12),
                    "gender": Student.Gender.FEMALE if index % 2 == 0 else Student.Gender.MALE,
                    "blood_type": Student.BloodType.O_POS,
                    "observations": "",
                    "nationality": "Brasileiro(a)",
                    "cpf": f"390.533.447-{index:02d}",
                    "rg_number": f"{58 + index}.234.567-{index}",
                    "rg_issuer": "SSP",
                    "rg_state": "SP",
                    "phone_mobile": f"(11) 9{index:04d}-2000",
                    "email": f"{first.lower()}.{last.lower()}@aluno.demo",
                },
            )
            students.append(student)
            address_data = {
                "recipient": f"Família {last}",
                "street": "Rua das Famílias",
                "number": str(200 + index),
                "complement": "Casa",
                "district": "Vila Mariana",
                "postal_code": "04010-010",
                "city": "São Paulo",
                "state": "SP",
            }
            address = self._ensure_address(StudentAddress, "student", student, address_data)
            for guardian_index, relationship in enumerate(
                (Guardian.Relationship.MOTHER, Guardian.Relationship.FATHER), start=1
            ):
                guardian = self._ensure(
                    Guardian,
                    {"email": f"resp{guardian_index}.{enrollment}@familia.demo"},
                    {
                        "first_name": "Patrícia" if guardian_index == 1 else "Ricardo",
                        "last_name": last,
                        "birth_date": dt.date(1975 + index, guardian_index, 15),
                        "gender": (
                            Guardian.Gender.FEMALE if guardian_index == 1 else Guardian.Gender.MALE
                        ),
                        "nationality": "Brasileiro(a)",
                        "cpf": f"{index:03d}.456.789-{guardian_index}{index % 10}",
                        "rg_number": f"{44 + index}.321.654-{guardian_index}",
                        "rg_issuer": "SSP",
                        "rg_state": "SP",
                        "phone": f"(11) 3456-{7000 + index}",
                        "phone_whatsapp": f"(11) 9{index:04d}-{3000 + guardian_index}",
                        "phone_mobile": f"(11) 9{index:04d}-{3000 + guardian_index}",
                    },
                )
                self._ensure(
                    GuardianAddress,
                    {"guardian": guardian, "address": address},
                    {"is_primary": True},
                )
                self._ensure(
                    StudentGuardian,
                    {"student": student, "guardian": guardian},
                    {
                        "relationship_type": relationship,
                        "is_primary": guardian_index == 1,
                        "has_custody": True,
                        "can_pickup": True,
                    },
                )

        class_specs = [
            ("6º A", "6º ano", Class.Shift.MORNING, "MAT", students[:4]),
            ("6º B", "6º ano", Class.Shift.AFTERNOON, "POR", students[4:7]),
            ("7º A", "7º ano", Class.Shift.MORNING, "CIE", students[7:]),
        ]
        classes: list[Any] = []
        for name, grade, shift, subject_code, class_students in class_specs:
            cls = self._ensure(
                Class,
                {"name": name, "academic_year": 2026},
                {
                    "grade": grade,
                    "shift": shift,
                    "max_students": 30,
                    "class_teacher": teachers[subject_code],
                },
            )
            classes.append(cls)
            for student in class_students:
                self._ensure(
                    Enrollment,
                    {"student": student, "class_obj": cls},
                    {
                        "enrollment_date": dt.date(2026, 2, 2),
                        "status": Enrollment.Status.ACTIVE,
                        "cancel_reason": "",
                    },
                )

        for code, name, capacity, room_type, resources in [
            (
                "SALA-101",
                "Sala 101",
                32,
                Room.Type.CLASSROOM,
                {"projector": True, "air_conditioning": True},
            ),
            (
                "SALA-102",
                "Sala 102",
                32,
                Room.Type.CLASSROOM,
                {"projector": True, "whiteboard": True},
            ),
            (
                "LAB-CIE",
                "Laboratório de Ciências",
                28,
                Room.Type.LAB,
                {"microscopes": 12, "sink": True},
            ),
            (
                "BIB-001",
                "Biblioteca Monteiro Lobato",
                45,
                Room.Type.LIBRARY,
                {"computers": 10, "reading_tables": 8},
            ),
            (
                "QUADRA",
                "Quadra Poliesportiva",
                80,
                Room.Type.GYM,
                {"covered": True, "bleachers": True},
            ),
        ]:
            self._ensure(
                Room,
                {"code": code},
                {
                    "name": name,
                    "capacity": capacity,
                    "type": room_type,
                    "resources": resources,
                    "floor": "Térreo",
                    "building": "Bloco A",
                },
            )

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
        return {"students": len(students), "teachers": len(teachers), "classes": len(classes)}

    def populate_calendar(self) -> int:
        """Cria ano letivo, 13 feriados e seis eventos da agenda de 2026."""
        from academic_calendar.models import AcademicYear, CalendarEvent, Holiday
        from classes.models import Class

        academic_year = self._ensure(
            AcademicYear,
            {"name": "2026", "start_date": dt.date(2026, 2, 2)},
            {"end_date": dt.date(2026, 12, 18), "status": AcademicYear.Status.IN_PROGRESS},
        )
        holidays = [
            ("Confraternização Universal", dt.date(2026, 1, 1), Holiday.Type.NATIONAL),
            ("Aniversário da Cidade de São Paulo", dt.date(2026, 1, 25), Holiday.Type.MUNICIPAL),
            ("Paixão de Cristo", dt.date(2026, 4, 3), Holiday.Type.NATIONAL),
            ("Tiradentes", dt.date(2026, 4, 21), Holiday.Type.NATIONAL),
            ("Dia Mundial do Trabalho", dt.date(2026, 5, 1), Holiday.Type.NATIONAL),
            ("Corpus Christi", dt.date(2026, 6, 4), Holiday.Type.MUNICIPAL),
            ("Data Magna do Estado de São Paulo", dt.date(2026, 7, 9), Holiday.Type.STATE),
            ("Independência do Brasil", dt.date(2026, 9, 7), Holiday.Type.NATIONAL),
            ("Nossa Senhora Aparecida", dt.date(2026, 10, 12), Holiday.Type.NATIONAL),
            ("Finados", dt.date(2026, 11, 2), Holiday.Type.NATIONAL),
            ("Proclamação da República", dt.date(2026, 11, 15), Holiday.Type.NATIONAL),
            (
                "Dia Nacional de Zumbi e da Consciência Negra",
                dt.date(2026, 11, 20),
                Holiday.Type.NATIONAL,
            ),
            ("Natal", dt.date(2026, 12, 25), Holiday.Type.NATIONAL),
        ]
        for name, date, holiday_type in holidays:
            self._ensure(
                Holiday, {"name": name, "date": date}, {"type": holiday_type, "is_recurring": False}
            )
        event_specs = [
            (
                "Reunião de responsáveis — 1º bimestre",
                dt.date(2026, 4, 9),
                CalendarEvent.Type.MEETING,
                CalendarEvent.Audience.GUARDIANS,
                None,
            ),
            (
                "Conselho de classe — 1º bimestre",
                dt.date(2026, 4, 16),
                CalendarEvent.Type.MEETING,
                CalendarEvent.Audience.TEACHERS,
                None,
            ),
            (
                "Avaliação diagnóstica — 6º A",
                dt.date(2026, 3, 17),
                CalendarEvent.Type.ASSESSMENT,
                CalendarEvent.Audience.CLASS,
                "6º A",
            ),
            (
                "Feira de Ciências",
                dt.date(2026, 8, 22),
                CalendarEvent.Type.SCHOOL_EVENT,
                CalendarEvent.Audience.ALL,
                None,
            ),
            (
                "Mostra cultural — 6º B",
                dt.date(2026, 9, 18),
                CalendarEvent.Type.SCHOOL_EVENT,
                CalendarEvent.Audience.CLASS,
                "6º B",
            ),
            (
                "Reunião pedagógica de encerramento",
                dt.date(2026, 12, 16),
                CalendarEvent.Type.MEETING,
                CalendarEvent.Audience.TEACHERS,
                None,
            ),
        ]
        for title, date, event_type, audience, class_name in event_specs:
            class_obj = (
                Class.objects.filter(name=class_name, academic_year=2026).first()
                if class_name
                else None
            )
            self._ensure(
                CalendarEvent,
                {"title": title, "start_date": date},
                {
                    "description": "Evento institucional do calendário DEMO.",
                    "end_date": date,
                    "start_time": (
                        dt.time(18, 30) if event_type == CalendarEvent.Type.MEETING else None
                    ),
                    "end_time": (
                        dt.time(20, 0) if event_type == CalendarEvent.Type.MEETING else None
                    ),
                    "type": event_type,
                    "recurrence": {},
                    "audience": audience,
                    "class_obj": class_obj,
                    "academic_year": academic_year,
                    "is_public": True,
                    "is_cancelled": False,
                    "cancel_reason": "",
                },
            )
        return len(holidays)

    def populate_attendance(self) -> int:
        """Cria vinte chamadas completas e seus lançamentos individuais."""
        from attendance.models import AttendanceEntry, AttendanceRecord
        from classes.models import Class, Enrollment
        from teachers.models import Subject, Teacher

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
                {"subject": subject, "teacher": teacher, "notes": "Chamada DEMO preenchida."},
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


def get_demo_seed_service() -> DemoSeedService:
    """Retorna o serviço do seed associado ao administrador do tenant DEMO."""
    from core.models import CustomUser

    return DemoSeedService(user=CustomUser.objects.get(email="admin@demo.com"))
