"""AttendanceService: regras de negócio para controle de frequência."""

import logging

from django.db import transaction
from django.utils import timezone

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)

# Limiares de alerta (percentual). 50% = crítica, 75% = alerta.
ALERT_THRESHOLD = 75.0
CRITICAL_THRESHOLD = 50.0


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


class AttendanceService(BaseService):
    """Serviço de aplicação para o domínio de frequência."""

    # ── Abertura de chamada ──────────────────────────────────────────────────
    @transaction.atomic
    def open_attendance(self, data: dict):
        """Cria o registro de chamada e pré-cadastra entradas para todos os alunos ativos.

        Espera em `data`: class_id, subject_id, teacher_id, date, lesson_number, notes?
        """
        from attendance.models import AttendanceEntry, AttendanceRecord
        from classes.models import Class, Enrollment
        from teachers.models import Subject, Teacher

        required = ["class_id", "subject_id", "teacher_id", "date"]
        errors: dict[str, list[str]] = {}
        for field in required:
            if not data.get(field):
                errors[field] = ["Campo obrigatório."]
        if errors:
            raise ValidationError(errors=errors)

        try:
            cls = Class.objects.get(pk=data["class_id"])
        except Class.DoesNotExist as exc:
            raise ValidationError(errors={"class_id": ["Turma não encontrada."]}) from exc
        try:
            subject = Subject.objects.get(pk=data["subject_id"])
        except Subject.DoesNotExist as exc:
            raise ValidationError(errors={"subject_id": ["Disciplina não encontrada."]}) from exc
        try:
            teacher = Teacher.objects.get(pk=data["teacher_id"])
        except Teacher.DoesNotExist as exc:
            raise ValidationError(errors={"teacher_id": ["Professor não encontrado."]}) from exc

        date = data["date"]
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

    # ── Lançamento em lote ───────────────────────────────────────────────────
    @transaction.atomic
    def record_attendance(self, record_id, entries_data: dict):
        """Atualiza as presenças a partir de um dict {student_id: status}.

        `status` ∈ {PRESENT, ABSENT, JUSTIFIED}. Para JUSTIFIED, permite
        `justification` informado por aluno via dict {"status":..., "justification":...}.
        """
        from attendance.models import AttendanceEntry

        record = _RecordRepo().get_by_id(record_id)

        valid = {
            AttendanceEntry.Status.PRESENT,
            AttendanceEntry.Status.ABSENT,
            AttendanceEntry.Status.JUSTIFIED,
        }
        updated = 0
        for student_id, payload in entries_data.items():
            # Suporta valor simples (str) ou dict com justification.
            if isinstance(payload, dict):
                status = payload.get("status")
                justification = payload.get("justification", "")
            else:
                status = payload
                justification = ""

            if status not in valid:
                raise ValidationError(errors={"__all__": [f"Status inválido: {status}"]})
            try:
                entry = record.entries.get(student_id=student_id)
            except AttendanceEntry.DoesNotExist:
                raise ObjectNotFoundError("AttendanceEntry", student_id) from None

            entry.status = status
            if status == AttendanceEntry.Status.JUSTIFIED:
                entry.justification = (justification or "").strip()
            else:
                entry.justification = ""
            entry.updated_by = self.user
            entry.save(update_fields=["status", "justification", "updated_by", "updated_at"])
            updated += 1

            self._record_audit("UPDATE", entry)
        self._log("Chamada registrada", record_id=str(record.pk), updated=updated)
        return record

    def update_entry(self, entry_id, status, justification: str = ""):
        """Corrige o lançamento individual de um aluno."""
        from attendance.models import AttendanceEntry

        try:
            entry = AttendanceEntry.objects.get(pk=entry_id)
        except AttendanceEntry.DoesNotExist as exc:
            raise ObjectNotFoundError("AttendanceEntry", str(entry_id)) from exc

        old = {"status": entry.status}
        entry.status = status
        if status == AttendanceEntry.Status.JUSTIFIED:
            entry.justification = (justification or "").strip()
        else:
            entry.justification = ""
        entry.updated_by = self.user
        entry.save(update_fields=["status", "justification", "updated_by", "updated_at"])
        self._record_audit("UPDATE", entry, old_values=old)
        return entry

    # ── Justificativas ──────────────────────────────────────────────────────
    def submit_justification(self, data: dict):
        """Aluno/responsável envia justificativa de ausência."""
        from attendance.models import AttendanceJustification
        from students.models import Student

        required = ["student_id", "start_date", "end_date", "reason"]
        errors: dict[str, list[str]] = {}
        for field in required:
            if not data.get(field):
                errors[field] = ["Campo obrigatório."]
        if errors:
            raise ValidationError(errors=errors)

        try:
            student = Student.objects.get(pk=data["student_id"])
        except Student.DoesNotExist as exc:
            raise ValidationError(errors={"student_id": ["Aluno não encontrado."]}) from exc

        if data["end_date"] < data["start_date"]:
            raise ValidationError(errors={"end_date": ["Término deve ser após o início."]})

        just = AttendanceJustification.objects.create(
            student=student,
            start_date=data["start_date"],
            end_date=data["end_date"],
            reason=data["reason"].strip(),
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

        just = _JustificationRepo().get_by_id(justification_id)
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

        just = _JustificationRepo().get_by_id(justification_id)
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

    # ── Cálculo de frequência ───────────────────────────────────────────────
    def calculate_attendance_rate(self, student_id, class_id):
        """Retorna o percentual de frequência (0-100) do aluno na turma.

        Considera apenas as chamadas já lançadas. Os ausentes justificados não
        contam como faltas.
        """
        from attendance.models import AttendanceEntry

        entries = AttendanceEntry.objects.filter(
            student_id=student_id, record__class_obj_id=class_id
        )
        total = entries.count()
        if total == 0:
            return None  # sem chamadas registradas

        presences = entries.filter(
            status__in=[AttendanceEntry.Status.PRESENT, AttendanceEntry.Status.JUSTIFIED]
        ).count()
        return round((presences / total) * 100, 2)

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
