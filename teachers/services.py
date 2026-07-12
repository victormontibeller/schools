"""TeacherService: regras de negócio para professores e disciplinas."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from teachers.models import Subject, Teacher

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)

TEACHER_REQUIRED_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "hire_date",
    "birth_date",
    "gender",
    "cpf",
    "rg_number",
    "phone_mobile",
]
TEACHER_EDIT_REQUIRED_FIELDS = ["first_name", "last_name", *TEACHER_REQUIRED_FIELDS[3:]]


class _SubjectRepo(BaseRepository):
    """Repositorio de acesso a dados de Subject."""

    @property
    def model_class(self):
        from teachers.models import Subject

        return Subject


class _TeacherRepo(BaseRepository):
    """Repositorio de acesso a dados de Teacher."""

    @property
    def model_class(self):
        from teachers.models import Teacher

        return Teacher


class SubjectService(BaseService):
    """Serviço de regras de negócio para disciplinas."""

    def create_subject(self, data: dict) -> Subject:
        """Cria uma disciplina validando código único."""
        from teachers.models import Subject

        self.validate_required(data, ["name", "code"])

        code = data["code"].strip().upper()
        if Subject.objects.filter(code=code).exists():
            raise ValidationError(errors={"code": ["Código já cadastrado."]})

        subject = Subject.objects.create(
            name=data["name"].strip(),
            code=code,
            workload=data.get("workload", 0),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", subject)
        self._log("Disciplina criada", subject_id=str(subject.pk))
        return subject

    def update_subject(self, subject_id, data: dict) -> Subject:
        """Atualiza dados da disciplina."""
        from teachers.models import Subject

        try:
            subject = Subject.objects.get(pk=subject_id)
        except Subject.DoesNotExist:
            raise ObjectNotFoundError("Subject", str(subject_id)) from None

        old = {"name": subject.name, "code": subject.code}

        if "code" in data:
            new_code = data["code"].strip().upper()
            if Subject.objects.filter(code=new_code).exclude(pk=subject_id).exists():
                raise ValidationError(errors={"code": ["Código já cadastrado."]})
            subject.code = new_code

        if "name" in data:
            subject.name = data["name"].strip()

        if "workload" in data:
            subject.workload = data["workload"]

        subject.updated_by = self.user
        subject.save()

        self._record_audit("UPDATE", subject, old_values=old)
        self._log("Disciplina atualizada", subject_id=str(subject.pk))
        return subject

    def deactivate_subject(self, subject_id) -> Subject:
        """Aplica exclusão lógica na disciplina."""
        from teachers.models import Subject

        return self._deactivate(Subject, subject_id, "Subject")


class TeacherService(BaseService):
    """Serviço de regras de negócio para professores e atribuição de disciplinas."""

    @transaction.atomic
    def create_teacher(self, data: dict) -> Teacher:
        """Cria um professor validando usuário, matrícula única e registra auditoria."""
        from teachers.models import Teacher

        legacy_user_id = data.get("user_id")
        required = TEACHER_REQUIRED_FIELDS if not legacy_user_id else TEACHER_REQUIRED_FIELDS[3:]
        self.validate_required(data, required)

        from core.models import CustomUser, Role
        from core.services import RegistrationSequenceService

        if legacy_user_id:
            try:
                user = CustomUser.objects.get(pk=legacy_user_id)
            except CustomUser.DoesNotExist:
                raise ObjectNotFoundError("CustomUser", str(legacy_user_id)) from None
            email = user.email
        else:
            email = data["email"].strip().lower()
            user = CustomUser.all_objects.filter(
                email__iexact=email, deleted_at__isnull=True
            ).first()
        if user is None:
            role = Role.objects.filter(name=Role.Name.TEACHER).first()
            if role is None:
                role = Role.objects.create(
                    name=Role.Name.TEACHER, created_by=self.user, updated_by=self.user
                )
                self._record_audit("INSERT", role)
            user = CustomUser(
                email=email,
                first_name=data["first_name"].strip(),
                last_name=data["last_name"].strip(),
                role=role,
                is_active=False,
                created_by=self.user,
                updated_by=self.user,
            )
            user.set_unusable_password()
            user.save()
            self._record_audit("INSERT", user)

        if Teacher.objects.filter(user=user).exists():
            raise BusinessRuleViolationError("Este usuário já possui perfil de professor.")

        reg = RegistrationSequenceService(user=self.user).next_number("teacher")

        cpf_cleaned = self._validate_cpf(data)
        teacher = Teacher.objects.create(
            user=user,
            registration_number=reg,
            hire_date=data.get("hire_date"),
            birth_date=data.get("birth_date"),
            gender=data.get("gender", Teacher.Gender.NOT_INFORMED),
            cpf=cpf_cleaned,
            rg_number=data.get("rg_number", ""),
            phone_mobile=data.get("phone_mobile", ""),
            accepts_email_notifications=bool(data.get("accepts_email_notifications")),
            accepts_whatsapp_notifications=bool(data.get("accepts_whatsapp_notifications")),
            created_by=self.user,
            updated_by=self.user,
        )
        subjects = data.get("subjects")
        if subjects:
            teacher.subjects.set(subjects)
        if data.get("avatar"):
            user.avatar = data["avatar"]
            user.updated_by = self.user
            user.save(update_fields=["avatar", "updated_by", "updated_at"])
        self._record_audit("INSERT", teacher)
        self._log("Professor criado", teacher_id=str(teacher.pk))
        return teacher

    def update_teacher(self, teacher_id, data: dict) -> Teacher:
        """Atualiza dados do professor e registra auditoria com valores antigos."""
        repo = _TeacherRepo()
        teacher = repo.get_by_id(teacher_id)

        self.validate_required(data, TEACHER_EDIT_REQUIRED_FIELDS)

        allowed = {
            "hire_date",
            "birth_date",
            "gender",
            "rg_number",
            "phone_mobile",
            "accepts_email_notifications",
            "accepts_whatsapp_notifications",
        }
        old = self._snapshot(teacher, [*allowed, "registration_number", "cpf"])
        user_old = self._person_user_old_values(teacher.user)
        updates = {k: v for k, v in data.items() if k in allowed}

        if "cpf" in data:
            cpf_cleaned = self._validate_cpf(data, exclude_id=teacher_id)
            updates["cpf"] = cpf_cleaned

        user_updates = self._person_user_updates(data)
        if "email" in data:
            from core.models import CustomUser

            email = data["email"].strip().lower()
            if (
                CustomUser.all_objects.filter(email__iexact=email)
                .exclude(pk=teacher.user_id)
                .exists()
            ):
                raise ValidationError(errors={"email": ["Este e-mail já está em uso."]})
            user_updates["email"] = email
        for field, value in user_updates.items():
            setattr(teacher.user, field, value)
        teacher.user.save(update_fields=[*user_updates.keys(), "updated_at"])

        updates["updated_by"] = self.user
        teacher = repo.update(teacher, **updates)
        self._record_audit("UPDATE", teacher.user, old_values=user_old)
        self._record_audit("UPDATE", teacher, old_values=old)
        self._log("Professor atualizado", teacher_id=str(teacher.pk))
        return teacher

    def deactivate_teacher(self, teacher_id) -> Teacher:
        """Aplica exclusão lógica no professor e registra auditoria."""
        from teachers.models import Teacher

        return self._deactivate(Teacher, teacher_id, "Teacher")

    def assign_subject(self, teacher_id, subject_id):
        """Atribui uma disciplina ao professor e registra auditoria."""
        teacher = _TeacherRepo().get_by_id(teacher_id)
        subject = _SubjectRepo().get_by_id(subject_id)
        if teacher.subjects.filter(pk=subject_id).exists():
            raise BusinessRuleViolationError("Disciplina já atribuída ao professor.")
        old = {"subject_ids": [str(pk) for pk in teacher.subjects.values_list("pk", flat=True)]}
        teacher.subjects.add(subject)
        new = {"subject_ids": [str(pk) for pk in teacher.subjects.values_list("pk", flat=True)]}
        self._record_audit("UPDATE", teacher, old_values=old, new_values=new)
        self._log(
            "Disciplina atribuida ao professor",
            teacher_id=str(teacher.pk),
            subject_id=str(subject.pk),
        )
        return teacher

    def remove_subject(self, teacher_id, subject_id):
        """Remove a disciplina atribuída ao professor e registra auditoria."""
        teacher = _TeacherRepo().get_by_id(teacher_id)
        _SubjectRepo().get_by_id(subject_id)
        old = {"subject_ids": [str(pk) for pk in teacher.subjects.values_list("pk", flat=True)]}
        teacher.subjects.remove(subject_id)
        new = {"subject_ids": [str(pk) for pk in teacher.subjects.values_list("pk", flat=True)]}
        self._record_audit("UPDATE", teacher, old_values=old, new_values=new)
        self._log(
            "Disciplina removida do professor",
            teacher_id=str(teacher.pk),
            subject_id=str(subject_id),
        )
        return teacher

    def set_subjects(self, teacher_id, subjects) -> Teacher:
        """Sincroniza as disciplinas ministradas pelo professor."""
        teacher = _TeacherRepo().get_by_id(teacher_id)
        old = {"subject_ids": [str(pk) for pk in teacher.subjects.values_list("pk", flat=True)]}
        subject_ids = [subject.pk for subject in subjects]
        teacher.subjects.set(subject_ids)
        teacher.updated_by = self.user
        teacher.save(update_fields=["updated_by", "updated_at"])
        new = {"subject_ids": [str(pk) for pk in teacher.subjects.values_list("pk", flat=True)]}
        self._record_audit("UPDATE", teacher, old_values=old, new_values=new)
        self._log(
            "Disciplinas do professor atualizadas",
            teacher_id=str(teacher.pk),
            subject_count=len(subject_ids),
        )
        return teacher

    def _validate_cpf(self, data: dict, exclude_id=None) -> str | None:
        """Valida CPF: formato e unicidade. Retorna CPF limpo ou None."""
        from teachers.models import Teacher

        return self._validate_unique_cpf(
            data,
            Teacher,
            "CPF já cadastrado para outro professor.",
            exclude_id=exclude_id,
        )
