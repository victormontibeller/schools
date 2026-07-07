"""TeacherService: regras de negócio para professores e disciplinas."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from teachers.models import Subject, Teacher

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


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

    def create_teacher(self, data: dict) -> Teacher:
        """Cria um professor validando usuário, matrícula única e registra auditoria."""
        from teachers.models import Teacher

        user_id = data.get("user_id")
        if not user_id:
            raise ValidationError(errors={"user_id": ["Usuário é obrigatório."]})

        from core.models import CustomUser

        try:
            user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            raise ObjectNotFoundError("CustomUser", str(user_id)) from None

        if Teacher.objects.filter(user=user).exists():
            raise BusinessRuleViolationError("Este usuário já possui perfil de professor.")

        reg = data.get("registration_number", "").strip()
        if not reg:
            raise ValidationError(errors={"registration_number": ["Matrícula é obrigatória."]})
        if Teacher.objects.filter(registration_number=reg).exists():
            raise ValidationError(errors={"registration_number": ["Matrícula já cadastrada."]})

        cpf_cleaned = self._validate_cpf(data)
        self._validate_rg_state(data)

        teacher = Teacher.objects.create(
            user=user,
            registration_number=reg,
            hire_date=data.get("hire_date"),
            birth_date=data.get("birth_date"),
            gender=data.get("gender", Teacher.Gender.NOT_INFORMED),
            nationality=data.get("nationality", "Brasileiro(a)"),
            cpf=cpf_cleaned,
            rg_number=data.get("rg_number", ""),
            rg_issuer=data.get("rg_issuer", ""),
            rg_state=data.get("rg_state", ""),
            phone_mobile=data.get("phone_mobile", ""),
            created_by=self.user,
            updated_by=self.user,
        )
        subjects = data.get("subjects")
        if subjects:
            teacher.subjects.set(subjects)
        self._record_audit("INSERT", teacher)
        self._log("Professor criado", teacher_id=str(teacher.pk))
        return teacher

    def update_teacher(self, teacher_id, data: dict) -> Teacher:
        """Atualiza dados do professor e registra auditoria com valores antigos."""
        repo = _TeacherRepo()
        teacher = repo.get_by_id(teacher_id)
        old = {
            "registration_number": teacher.registration_number,
            "hire_date": teacher.hire_date,
            "birth_date": teacher.birth_date,
            "gender": teacher.gender,
            "nationality": teacher.nationality,
            "cpf": teacher.cpf,
            "rg_number": teacher.rg_number,
            "rg_issuer": teacher.rg_issuer,
            "rg_state": teacher.rg_state,
            "phone_mobile": teacher.phone_mobile,
        }
        user_old = {
            "first_name": teacher.user.first_name,
            "last_name": teacher.user.last_name,
            "avatar": teacher.user.avatar.name if teacher.user.avatar else "",
        }

        self.validate_required(
            data,
            [
                "first_name",
                "last_name",
                "registration_number",
                "hire_date",
                "birth_date",
                "gender",
                "nationality",
                "cpf",
                "rg_number",
                "rg_issuer",
                "rg_state",
                "phone_mobile",
            ],
        )

        allowed = {
            "hire_date",
            "birth_date",
            "gender",
            "nationality",
            "rg_number",
            "rg_issuer",
            "rg_state",
            "phone_mobile",
        }
        updates = {k: v for k, v in data.items() if k in allowed}

        if "registration_number" in data:
            reg = data["registration_number"].strip()
            if not reg:
                raise ValidationError(errors={"registration_number": ["Matrícula é obrigatória."]})
            from teachers.models import Teacher

            if Teacher.objects.filter(registration_number=reg).exclude(pk=teacher_id).exists():
                raise ValidationError(errors={"registration_number": ["Matrícula já cadastrada."]})
            updates["registration_number"] = reg

        if "cpf" in data:
            cpf_cleaned = self._validate_cpf(data, exclude_id=teacher_id)
            updates["cpf"] = cpf_cleaned

        if "rg_state" in data:
            self._validate_rg_state(data)

        user_updates = {
            "first_name": data["first_name"].strip(),
            "last_name": data["last_name"].strip(),
            "updated_by": self.user,
        }
        avatar = data.get("avatar")
        if avatar:
            user_updates["avatar"] = avatar

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
        teacher.subjects.add(subject)
        self._record_audit("UPDATE", teacher)
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
        teacher.subjects.remove(subject_id)
        self._record_audit("UPDATE", teacher)
        self._log(
            "Disciplina removida do professor",
            teacher_id=str(teacher.pk),
            subject_id=str(subject_id),
        )
        return teacher

    def set_subjects(self, teacher_id, subjects) -> Teacher:
        """Sincroniza as disciplinas ministradas pelo professor."""
        teacher = _TeacherRepo().get_by_id(teacher_id)
        subject_ids = [subject.pk for subject in subjects]
        teacher.subjects.set(subject_ids)
        teacher.updated_by = self.user
        teacher.save(update_fields=["updated_by", "updated_at"])
        self._record_audit("UPDATE", teacher)
        self._log(
            "Disciplinas do professor atualizadas",
            teacher_id=str(teacher.pk),
            subject_count=len(subject_ids),
        )
        return teacher

    def _validate_cpf(self, data: dict, exclude_id=None) -> str | None:
        """Valida CPF: formato e unicidade. Retorna CPF limpo ou None."""
        from base.validators import validate_cpf
        from teachers.models import Teacher

        cpf = data.get("cpf", "")
        if not cpf:
            return None
        try:
            cpf_clean = validate_cpf(cpf)
        except Exception as e:
            raise ValidationError(errors={"cpf": [str(e)]}) from e

        qs = Teacher.objects.filter(cpf=cpf_clean)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError(errors={"cpf": ["CPF já cadastrado para outro professor."]})
        return cpf_clean

    def _validate_rg_state(self, data: dict) -> None:
        """Valida UF do RG."""
        from base.validators import validate_uf

        rg_state = data.get("rg_state", "")
        if not rg_state:
            return
        try:
            validate_uf(rg_state)
        except Exception as e:
            raise ValidationError(errors={"rg_state": [str(e)]}) from e
