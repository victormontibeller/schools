"""Implementação dos comandos públicos da matriz de horários."""

from __future__ import annotations

from datetime import date, timedelta

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.repositories import BaseRepository
from base.services import service_command


class _ScheduleRepository(BaseRepository):
    @property
    def model_class(self):
        from agenda.contracts import Schedule

        return Schedule


class ScheduleCommandMixin:
    """Reúne as escritas auditáveis da matriz usadas pela fachada ScheduleService."""

    def create_schedule(self, data: dict):
        """Cria uma célula da matriz para um período efetivo informado."""
        self.validate_required(data, ["class_obj_id"])
        schedule_data = self._resolve_schedule_data(data)
        self._assert_class_in_scope(data["class_obj_id"], as_of=schedule_data["valid_from"])
        self._lock_schedule_resources((schedule_data,))
        self._assert_schedule_available(schedule_data)
        schedule = self._create_resolved_schedule(schedule_data)
        self._record_audit("INSERT", schedule)
        self._log("schedule_created", schedule_id=str(schedule.pk))
        return schedule

    def create_schedule_successor(self, schedule_id, data: dict):
        """Fecha a versão atual e cria sua sucessora a partir da nova vigência."""
        current = self._get_schedule_for_update(schedule_id)
        self.validate_required(data, ["version"])
        self._validate_version_value(data["version"])
        effective_from = data.get("valid_from")
        if not isinstance(effective_from, date):
            raise ValidationError(errors={"valid_from": ["Informe uma data de vigência válida."]})
        effective_from = self._week_monday(effective_from)
        self._assert_class_in_scope(current.class_obj_id, as_of=effective_from)
        if effective_from <= current.valid_from:
            raise BusinessRuleViolationError(
                "A nova versão deve iniciar após o início da versão atual."
            )
        if current.valid_until is not None and effective_from > current.valid_until:
            raise BusinessRuleViolationError("A data informada está fora da vigência desta versão.")

        successor_data = self._resolve_schedule_data(
            {
                "class_obj_id": data.get("class_obj_id", current.class_obj_id),
                "teacher_id": data.get("teacher_id", current.teacher_id),
                "subject_id": data.get("subject_id", current.subject_id),
                "room_id": data.get("room_id", current.room_id),
                "time_slot_id": data.get("time_slot_id", current.time_slot_id),
                "day_of_week": data.get("day_of_week", current.day_of_week),
                "valid_from": effective_from,
                "valid_until": data.get("valid_until", current.valid_until),
            }
        )
        if (
            successor_data["class_obj"].pk != current.class_obj_id
            or successor_data["day_of_week"] != current.day_of_week
            or successor_data["time_slot"].pk != current.time_slot_id
        ):
            raise BusinessRuleViolationError(
                "Uma versão sucessora não pode mudar a célula da matriz."
            )
        self._lock_schedule_resources((successor_data,))
        self._assert_schedule_available(successor_data, exclude_schedule=current)

        old_values = self._snapshot(current, ["valid_until", "version"])
        current = _ScheduleRepository().update(
            current,
            valid_until=effective_from - timedelta(days=1),
            updated_by=self.user,
            expected_version=data["version"],
        )
        self._record_audit("UPDATE", current, old_values=old_values)
        self._log("schedule_version_ended", schedule_id=str(current.pk))

        successor = self._create_resolved_schedule(successor_data)
        self._record_audit("INSERT", successor, new_values={"predecessor_id": str(current.pk)})
        self._log(
            "schedule_successor_created",
            schedule_id=str(successor.pk),
            predecessor_id=str(current.pk),
        )
        return successor

    @service_command
    def end_schedule(self, schedule_id, data: dict):
        """Encerra uma célula na data inclusiva solicitada, sem apagar seu histórico."""
        schedule = self._get_schedule_for_update(schedule_id)
        self.validate_required(data, ["version"])
        self._validate_version_value(data["version"])
        end_date = data.get("valid_until")
        if not isinstance(end_date, date):
            raise ValidationError(
                errors={"valid_until": ["Informe uma data de encerramento válida."]}
            )
        end_date = self._week_monday(end_date) - timedelta(days=1)
        self._lock_class_and_revalidate_scope(
            schedule.class_obj_id, as_of=end_date + timedelta(days=1)
        )
        if end_date < schedule.valid_from:
            raise ValidationError(
                errors={"valid_until": ["O encerramento não pode ser anterior ao início."]}
            )
        if schedule.valid_until is not None and end_date > schedule.valid_until:
            raise BusinessRuleViolationError("A data informada está fora da vigência desta versão.")

        old_values = self._snapshot(schedule, ["valid_until", "version"])
        schedule = _ScheduleRepository().update(
            schedule,
            valid_until=end_date,
            updated_by=self.user,
            expected_version=data["version"],
        )
        self._record_audit("UPDATE", schedule, old_values=old_values)
        self._log("schedule_ended", schedule_id=str(schedule.pk))
        return schedule

    @service_command
    def copy_schedule_day(self, class_id, data: dict) -> tuple:
        """Copia atomicamente o dia de uma turma para outro dia na data de referência."""
        from agenda.contracts import Schedule

        self.validate_required(data, ["source_day", "target_day", "as_of"])
        source_day = data["source_day"]
        target_day = data["target_day"]
        as_of = data["as_of"]
        self._validate_day(source_day, "source_day")
        self._validate_day(target_day, "target_day")
        if source_day == target_day:
            raise ValidationError(errors={"target_day": ["Escolha um dia diferente para destino."]})
        if not isinstance(as_of, date):
            raise ValidationError(errors={"as_of": ["Informe uma data de referência válida."]})
        as_of = self._week_monday(as_of)
        class_obj = self._get_class_in_scope(class_id, as_of=as_of)
        locked_schedules = list(
            Schedule.objects.select_for_update()
            .filter(class_obj=class_obj, day_of_week__in=[source_day, target_day], is_active=True)
            .select_related("teacher", "subject", "room", "time_slot")
        )
        source = [
            schedule
            for schedule in locked_schedules
            if schedule.day_of_week == source_day and self._is_effective_on(schedule, as_of)
        ]
        if not source:
            raise BusinessRuleViolationError(
                "Não há células vigentes para copiar no dia de origem."
            )

        copies = []
        for schedule in source:
            copies.append(
                self._resolve_schedule_data(
                    {
                        "class_obj_id": class_obj.pk,
                        "teacher_id": schedule.teacher_id,
                        "subject_id": schedule.subject_id,
                        "room_id": schedule.room_id,
                        "time_slot_id": schedule.time_slot_id,
                        "day_of_week": target_day,
                        "valid_from": as_of,
                        "valid_until": schedule.valid_until,
                    }
                )
            )
        self._lock_schedule_resources(copies)
        for copied_data in copies:
            self._assert_schedule_available(copied_data)

        created = []
        for copied_data in copies:
            schedule = self._create_resolved_schedule(copied_data)
            self._record_audit("INSERT", schedule, new_values={"copied_from_day": source_day})
            self._log("schedule_day_cell_copied", schedule_id=str(schedule.pk))
            created.append(schedule)
        self._log("schedule_day_copied", class_id=str(class_obj.pk), copied_count=len(created))
        return tuple(created)
