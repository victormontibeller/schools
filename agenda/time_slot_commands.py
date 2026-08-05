"""Implementação dos comandos públicos de períodos comuns."""

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository


class _TimeSlotRepository(BaseRepository):
    @property
    def model_class(self):
        from agenda.contracts import TimeSlot

        return TimeSlot

    def get_for_update(self, time_slot_id):
        """Retorna o período ativo sob lock pessimista."""
        try:
            return self.model_class.objects.select_for_update().get(pk=time_slot_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError("TimeSlot", str(time_slot_id)) from None


class TimeSlotCommandMixin:
    """Reúne as escritas de períodos usadas pela fachada ScheduleService."""

    def create_time_slot(self, data: dict):
        """Cria um período de turno após validar intervalo e sobreposição global."""
        self.validate_required(data, ["slot_number", "shift", "start_time", "end_time"])
        self._validate_time_slot_interval(data["start_time"], data["end_time"])
        from agenda.contracts import TimeSlot

        if data["shift"] not in TimeSlot.Shift.values:
            raise ValidationError(errors={"shift": ["Selecione um turno válido."]})
        self._lock_time_slot_catalog()
        if self._time_slot_overlaps(data["start_time"], data["end_time"]):
            raise ValidationError(errors={"__all__": ["O período se sobrepõe a outro cadastrado."]})
        slot = TimeSlot.objects.create(
            slot_number=data["slot_number"],
            shift=data["shift"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit(
            "INSERT",
            slot,
            new_values=self._snapshot(slot, ["slot_number", "shift", "start_time", "end_time"]),
        )
        self._log("time_slot_created", time_slot_id=str(slot.pk))
        return slot

    def update_time_slot(self, time_slot_id, data: dict):
        """Atualiza período ainda sem uso, conservando sua identidade comum."""
        from agenda.contracts import Schedule

        self._lock_time_slot_catalog()
        slot = _TimeSlotRepository().get_for_update(time_slot_id)
        if Schedule.all_objects.filter(time_slot=slot).exists():
            raise BusinessRuleViolationError(
                "Este período já está em uso na matriz e não pode ser alterado."
            )
        self.validate_required(data, ["slot_number", "shift", "start_time", "end_time", "version"])
        self._validate_version_value(data["version"])
        self._validate_time_slot_interval(data["start_time"], data["end_time"])
        from agenda.contracts import TimeSlot

        if data["shift"] not in TimeSlot.Shift.values:
            raise ValidationError(errors={"shift": ["Selecione um turno válido."]})
        if self._time_slot_overlaps(data["start_time"], data["end_time"], exclude_slot=slot):
            raise ValidationError(errors={"__all__": ["O período se sobrepõe a outro cadastrado."]})
        old_values = self._snapshot(
            slot, ["slot_number", "shift", "start_time", "end_time", "version"]
        )
        slot = _TimeSlotRepository().update(
            slot,
            slot_number=data["slot_number"],
            shift=data["shift"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            updated_by=self.user,
            expected_version=data["version"],
        )
        self._record_audit(
            "UPDATE",
            slot,
            old_values=old_values,
            new_values=self._snapshot(slot, ["slot_number", "shift", "start_time", "end_time"]),
        )
        self._log("time_slot_updated", time_slot_id=str(slot.pk))
        return slot
