"""AttendanceService: regras de negócio para controle de frequência."""

from django.utils import timezone

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService

# Limiares de alerta (percentual). 50% = crítica, 75% = alerta.
ALERT_THRESHOLD = 75.0
CRITICAL_THRESHOLD = 50.0


def can_review_justifications(user, action: str) -> bool:
    """Restringe a revisão a administradores escolares e coordenação elegível."""
    from core.access_catalog import COORDINATOR
    from core.permissions import can_access, has_unrestricted_tenant_access, role_name

    return has_unrestricted_tenant_access(user) or (
        role_name(user) == COORDINATOR and can_access(user, "attendance", action)
    )


class _RecordRepo(BaseRepository):
    @property
    def model_class(self):
        from attendance.models import AttendanceRecord

        return AttendanceRecord


class _JustificationRepo(BaseRepository):
    @property
    def model_class(self):
        from attendance.models import AttendanceJustification

        return AttendanceJustification

    def get_for_update(self, object_id):
        """Obtém justificativa com lock pessimista para decisões concorrentes."""
        try:
            return self.model_class.objects.select_for_update().get(pk=object_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError(self.model_class.__name__, str(object_id)) from None


class AttendanceService(BaseService):
    """Serviço de aplicação para o domínio de frequência."""

    def open_attendance(self, data: dict):
        """Abre chamada da turma, disciplina, professor e data com entradas dos alunos ativos."""
        from attendance.models import AttendanceEntry, AttendanceRecord
        from classes.contracts import Class, Enrollment
        from teachers.contracts import Subject, Teacher

        self.validate_required(data, ["class_id", "subject_id", "teacher_id", "date"])
        if not data.get("lesson_content") and not getattr(self.user, "is_superuser", False):
            raise ValidationError(errors={"lesson_content": ["Campo obrigatório."]})

        try:
            cls = Class.objects.get(pk=data["class_id"])
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(data["class_id"])) from None
        try:
            subject = Subject.objects.get(pk=data["subject_id"])
        except Subject.DoesNotExist:
            raise ObjectNotFoundError("Subject", str(data["subject_id"])) from None
        try:
            teacher = Teacher.objects.get(pk=data["teacher_id"])
        except Teacher.DoesNotExist:
            raise ObjectNotFoundError("Teacher", str(data["teacher_id"])) from None

        date = data["date"]
        self._validate_teacher_scope(cls, subject, teacher, date)
        from students.contracts import ImportUsageService

        ImportUsageService(user=self.user).seal_for_use(
            student_ids=Enrollment.objects.filter(class_obj=cls, status="ACTIVE").values_list(
                "student_id", flat=True
            )
        )

        lesson_number = int(data.get("lesson_number", 1) or 1)
        if AttendanceRecord.objects.filter(
            class_obj=cls, date=date, lesson_number=lesson_number
        ).exists():
            raise BusinessRuleViolationError("Já existe chamada para esta turma, data e aula.")

        record = AttendanceRecord.objects.create(
            class_obj=cls,
            subject=subject,
            teacher=teacher,
            date=date,
            lesson_number=lesson_number,
            lesson_content=(data.get("lesson_content") or "Conteúdo não informado").strip(),
            notes=(data.get("notes") or "").strip(),
            created_by=self.user,
            updated_by=self.user,
        )

        # Pré-cadastra todos os alunos ativamente matriculados como PRESENT
        # (o professor ajusta para ABSENT/JUSTIFIED na sequência).
        active_students = Enrollment.objects.filter(
            class_obj=cls, status=Enrollment.Status.ACTIVE
        ).select_related("student")
        entries = [
            AttendanceEntry(
                record=record,
                student=enr.student,
                status=AttendanceEntry.Status.PRESENT,
                created_by=self.user,
                updated_by=self.user,
            )
            for enr in active_students
        ]
        if entries:
            AttendanceEntry.objects.bulk_create(entries)

        self._record_audit("INSERT", record)
        self._log(
            "Chamada aberta",
            record_id=str(record.pk),
            class_id=str(cls.pk),
            students=len(entries),
        )
        return record

    def _validate_teacher_scope(self, class_obj, subject, teacher, attendance_date) -> None:
        """Valida autoria, disciplina e vínculo do professor com a turma."""
        from base.exceptions import PermissionDeniedError
        from core.access_selectors import ObjectAccessSelector
        from core.permissions import role_name

        if not teacher.is_active or not teacher.user.is_active:
            raise PermissionDeniedError("Professor desativado não pode registrar chamadas.")
        if not teacher.subjects.filter(pk=subject.pk).exists():
            raise ValidationError(
                errors={"subject": ["A disciplina não está vinculada ao professor."]}
            )
        if not ObjectAccessSelector.teacher_has_current_class_subject(
            teacher.pk,
            class_obj.pk,
            subject.pk,
            attendance_date,
        ):
            raise ValidationError(
                errors={
                    "class_obj": [
                        "Professor, turma e disciplina não possuem vínculo vigente na grade."
                    ]
                }
            )
        if role_name(self.user) == "TEACHER" and teacher.user_id != self.user.pk:
            raise PermissionDeniedError("Professor não autorizado para esta chamada.")

    # ── Parsing de formulário de chamada ─────────────────────────────────────

    @staticmethod
    def parse_attendance_post(post_data, entries) -> dict:
        """Converte dados do formulario HTTP no formato esperado por record_attendance.

        Formato do POST: chave `status_{student_id}` com valor "STATUS" ou
        "STATUS|justificativa". Alunos nao explicitamente marcados sao PRESENT.
        """
        from attendance.models import AttendanceEntry

        entries_data: dict = {}
        for entry in entries:
            key = f"status_{entry.student_id}"
            raw = post_data.get(key, AttendanceEntry.Status.PRESENT)
            if "|" in raw:
                status, justification = raw.split("|", 1)
            else:
                status, justification = raw, ""
            entries_data[str(entry.student_id)] = {
                "status": status,
                "version": post_data.get(f"version_{entry.student_id}"),
                "justification": justification,
                "note": post_data.get(f"note_{entry.student_id}", ""),
            }
        return entries_data

    # ── Lançamento em lote ───────────────────────────────────────────────────
    def record_attendance(self, record_id, entries_data: dict):
        """Salva atomicamente status, versão vista e observações de cada aluno."""
        from attendance.models import AttendanceEntry

        record = _RecordRepo().get_by_id(record_id)
        self._validate_teacher_attendance_scope(record.pk)

        valid = {
            AttendanceEntry.Status.PRESENT,
            AttendanceEntry.Status.ABSENT,
            AttendanceEntry.Status.JUSTIFIED,
        }
        updated = 0
        for student_id, payload in entries_data.items():
            try:
                entry = record.entries.get(student_id=student_id)
            except AttendanceEntry.DoesNotExist:
                raise ObjectNotFoundError("AttendanceEntry", student_id) from None
            if not isinstance(payload, dict):
                raise ValidationError(errors={"__all__": ["Informe status e versão por aluno."]})
            status = payload.get("status")
            justification = payload.get("justification", "")
            note = payload.get("note", "")
            if status not in valid:
                raise ValidationError(errors={"__all__": ["Status de presença inválido."]})
            try:
                expected_version = int(payload["version"])
            except (KeyError, TypeError, ValueError):
                raise ValidationError(
                    errors={"__all__": ["Recarregue a chamada antes de salvar."]}
                ) from None
            if expected_version != entry.version:
                raise BusinessRuleViolationError(
                    "Esta chamada foi alterada por outra pessoa. Recarregue antes de salvar."
                )

            old = self._snapshot(entry, ["status", "justification", "note"])
            entry.status = status
            if status == AttendanceEntry.Status.JUSTIFIED:
                entry.justification = (justification or "").strip()
            else:
                entry.justification = ""
            entry.note = (note or "").strip()
            entry.updated_by = self.user
            entry.save(
                update_fields=["status", "justification", "note", "updated_by", "updated_at"]
            )
            updated += 1

            self._record_audit("UPDATE", entry, old_values=old)
        self._log("Chamada registrada", record_id=str(record.pk), updated=updated)
        return record

    def update_entry(self, entry_id, status, justification: str = ""):
        """Corrige o lançamento individual de um aluno."""
        from attendance.models import AttendanceEntry

        try:
            entry = AttendanceEntry.objects.get(pk=entry_id)
        except AttendanceEntry.DoesNotExist as exc:
            raise ObjectNotFoundError("AttendanceEntry", str(entry_id)) from exc
        self._validate_teacher_attendance_scope(entry.record_id)

        old = self._snapshot(entry, ["status", "justification"])
        entry.status = status
        if status == AttendanceEntry.Status.JUSTIFIED:
            entry.justification = (justification or "").strip()
        else:
            entry.justification = ""
        entry.updated_by = self.user
        entry.save(update_fields=["status", "justification", "updated_by", "updated_at"])
        self._record_audit("UPDATE", entry, old_values=old)
        self._log(
            "Lançamento individual atualizado",
            entry_id=str(entry.pk),
            record_id=str(entry.record_id),
            status=entry.status,
        )
        return entry

    def _validate_teacher_attendance_scope(self, record_id) -> None:
        """Impede professor de alterar chamada pertencente a outro docente."""
        from core.access_catalog import TEACHER
        from core.access_selectors import ObjectAccessSelector
        from core.permissions import role_name

        if role_name(
            self.user
        ) == TEACHER and not ObjectAccessSelector.teacher_can_access_attendance(
            self.user.pk, record_id
        ):
            raise PermissionDeniedError("Chamada fora do escopo do professor.")

    def _validate_justification_reviewer(self, action: str) -> None:
        """Nega decisões de justificativa a papéis fora do workflow canônico."""
        if not can_review_justifications(self.user, action):
            raise PermissionDeniedError("Sem permissão para revisar justificativas.")

    # ── Justificativas ──────────────────────────────────────────────────────
    def submit_justification(self, data: dict):
        """Aluno/responsável envia justificativa de ausência."""
        from attendance.models import AttendanceJustification
        from core.access_selectors import ObjectAccessSelector
        from core.permissions import CREATE, can_access, role_name
        from students.contracts import Student

        self.validate_required(data, ["student_id", "start_date", "end_date", "reason"])

        if self.user is None or not getattr(self.user, "is_authenticated", False):
            raise PermissionDeniedError("Ator autenticado obrigatório para esta operação.")
        actor_role = role_name(self.user)
        if actor_role == "GUARDIAN":
            if not ObjectAccessSelector.guardian_can_access_student(
                self.user.pk, data["student_id"]
            ):
                raise PermissionDeniedError("Aluno fora do escopo deste responsável.")
        elif actor_role == "TEACHER":
            if not can_access(self.user, "attendance", CREATE):
                raise PermissionDeniedError("Sem permissão para enviar justificativas.")
            if not ObjectAccessSelector.teacher_can_access_student(
                self.user.pk, data["student_id"]
            ):
                raise PermissionDeniedError("Aluno fora do escopo deste professor.")
        elif not can_access(self.user, "attendance", CREATE):
            raise PermissionDeniedError("Sem permissão para enviar justificativas.")

        from students.contracts import ImportUsageService

        try:
            ImportUsageService(user=self.user).seal_for_use(student_ids=[data["student_id"]])
            student = Student.objects.get(pk=data["student_id"])
        except (Student.DoesNotExist, ObjectNotFoundError) as exc:
            raise ValidationError(errors={"student_id": ["Aluno não encontrado."]}) from exc

        if data["end_date"] < data["start_date"]:
            raise ValidationError(errors={"end_date": ["Término deve ser após o início."]})

        just = AttendanceJustification.objects.create(
            student=student,
            start_date=data["start_date"],
            end_date=data["end_date"],
            reason=data["reason"].strip(),
            document=data.get("document"),
            status=AttendanceJustification.Status.PENDING,
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", just)
        self._log("Justificativa enviada", justification_id=str(just.pk))
        return just

    def approve_justification(self, justification_id):
        """Coordenador aprova justificativa pendente."""
        from attendance.models import AttendanceJustification
        from core.access_catalog import EDIT

        self._validate_justification_reviewer(EDIT)
        just = _JustificationRepo().get_for_update(justification_id)
        if just.status != AttendanceJustification.Status.PENDING:
            raise BusinessRuleViolationError("Justificativa já foi processada.")
        old = {"status": just.status}
        just.status = AttendanceJustification.Status.APPROVED
        just.approved_by = self.user
        just.approved_at = timezone.now()
        just.updated_by = self.user
        just.save(
            update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"]
        )
        self._record_audit("UPDATE", just, old_values=old)
        self._log("Justificativa aprovada", justification_id=str(just.pk))
        return just

    def reject_justification(self, justification_id, reason: str = ""):
        """Coordenador rejeita justificativa pendente."""
        from attendance.models import AttendanceJustification
        from core.access_catalog import EDIT

        self._validate_justification_reviewer(EDIT)
        just = _JustificationRepo().get_for_update(justification_id)
        if just.status != AttendanceJustification.Status.PENDING:
            raise BusinessRuleViolationError("Justificativa já foi processada.")
        old = {"status": just.status}
        just.status = AttendanceJustification.Status.REJECTED
        just.rejection_reason = (reason or "").strip()
        just.approved_by = self.user
        just.updated_by = self.user
        just.save(
            update_fields=["status", "rejection_reason", "approved_by", "updated_by", "updated_at"]
        )
        self._record_audit("UPDATE", just, old_values=old)
        self._log("Justificativa rejeitada", justification_id=str(just.pk))
        return just

    def calculate_attendance_rate(self, student_id, class_id):
        """Percentual das chamadas lançadas; ausências justificadas não contam."""
        from attendance.selectors import AttendanceSelector

        return AttendanceSelector().get_student_attendance_rate(student_id, class_id)

    def get_attendance_threshold(self, student_id, class_id):
        """Classifica o aluno: OK / ALERTA (75%) / CRÍTICO (50%)."""
        rate = self.calculate_attendance_rate(student_id, class_id)
        if rate is None:
            return {"rate": None, "level": "UNKNOWN"}
        if rate < CRITICAL_THRESHOLD:
            level = "CRITICAL"
        elif rate < ALERT_THRESHOLD:
            level = "ALERT"
        else:
            level = "OK"
        return {"rate": rate, "level": level}
