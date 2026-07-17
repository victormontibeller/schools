"""Seed institucional e acadêmico coordenado pelo core."""

from __future__ import annotations

import datetime as dt
from typing import Any


class CoreDemoSeedMixin:
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
            instance.save()
            self._record_audit("UPDATE", instance, old_values=old)
            self._log("demo_seed_updated", entity_type=model.__name__, entity_id=str(instance.pk))
        return instance

    def _ensure_address(self, link_model, entity_field: str, entity, data: dict[str, str]):
        """Garante um endereço principal e o vínculo com sua entidade proprietária."""
        from addresses.contracts import Address

        address = self._ensure(Address, {"recipient": data["recipient"]}, data)
        self._ensure(
            link_model,
            {entity_field: entity, "address": address},
            {"is_primary": True},
        )
        return address

    def populate_core(self, school) -> dict[str, int]:
        """Popula escola, unidades, pessoas, turmas, salas e atividades do DEMO."""
        from addresses.contracts import (
            BusinessUnitAddress,
            GuardianAddress,
            SchoolAddress,
            StudentAddress,
            TeacherAddress,
        )
        from classes.contracts import Class, Enrollment
        from core.models import BusinessUnit, CustomUser, Role
        from guardians.contracts import Guardian, StudentGuardian
        from students.contracts import Student
        from teachers.contracts import Subject, Teacher

        teacher_role, _ = Role.objects.get_or_create(name=Role.Name.TEACHER)
        merged_settings = dict(school.settings or {})
        merged_settings.update({"timezone": "America/Sao_Paulo", "locale": "pt_BR"})
        diary_settings = dict(merged_settings.get("student_diary", {}))
        diary_settings["interactive_enabled"] = True
        merged_settings["student_diary"] = diary_settings
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
            "settings": merged_settings,
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
            ("2026011", "Alice", "Campos"),
            ("2026012", "Miguel", "Duarte"),
            ("2026013", "Lívia", "Pires"),
        ]
        students: list[Any] = []
        for index, (enrollment, first, last) in enumerate(student_names, start=1):
            student = self._ensure(
                Student,
                {"enrollment_number": enrollment},
                {
                    "first_name": first,
                    "last_name": last,
                    "birth_date": (
                        dt.date(2013, index, 12) if index <= 10 else dt.date(2021, index - 10, 12)
                    ),
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
            ("6º A", Class.Grade.ELEMENTARY_6, Class.Shift.MORNING, "MAT", students[:4]),
            (
                "6º B",
                Class.Grade.ELEMENTARY_6,
                Class.Shift.AFTERNOON,
                "POR",
                students[4:7],
            ),
            (
                "7º A",
                Class.Grade.ELEMENTARY_7,
                Class.Shift.MORNING,
                "CIE",
                students[7:10],
            ),
        ]
        classes: list[Any] = []
        for name, grade, shift, subject_code, class_students in class_specs:
            cls = self._ensure(
                Class,
                {"name": name, "academic_year": 2026},
                {
                    "grade": grade,
                    "education_stage": Class.EducationStage.ELEMENTARY_II,
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

        early_childhood_class = self._ensure(
            Class,
            {"name": "Infantil A", "academic_year": 2026},
            {
                "grade": Class.Grade.EARLY_PRE_2,
                "education_stage": Class.EducationStage.EARLY_CHILDHOOD,
                "shift": Class.Shift.FULL,
                "max_students": 20,
                "class_teacher": teachers["ART"],
            },
        )
        for student in students[10:]:
            self._ensure(
                Enrollment,
                {"student": student, "class_obj": early_childhood_class},
                {
                    "enrollment_date": dt.date(2026, 2, 2),
                    "status": Enrollment.Status.ACTIVE,
                    "cancel_reason": "",
                },
            )

        self.populate_rooms()
        self.populate_activities(
            classes=classes,
            class_specs=class_specs,
            subjects=subjects,
            teachers=teachers,
        )
        return {
            "students": len(students),
            "teachers": len(teachers),
            "classes": len(classes) + 1,
        }
