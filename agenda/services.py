"""ScheduleService: regras para grade horária com validação de conflitos."""

import logging

from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    ValidationError,
)
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _ScheduleRepo(BaseRepository):
    @property
    def model_class(self):
        from agenda.models import Schedule

        return Schedule


class _TimeSlotRepo(BaseRepository):
    @property
    def model_class(self):
        from agenda.models import TimeSlot

        return TimeSlot


class ScheduleService(BaseService):
    """Serviço de aplicação para o domínio de grade horária."""

    def create_schedule(self, data: dict):
        """Cria entrada de grade; valida conflito de professor e sala."""
        from agenda.models import Schedule

        self.validate_required(
            data,
            ["class_obj_id", "teacher_id", "subject_id", "time_slot_id", "valid_from"],
        )

        from agenda.models import TimeSlot
        from classes.models import Class
        from teachers.models import Subject, Teacher

        try:
            class_obj = Class.objects.get(pk=data["class_obj_id"])
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(data["class_obj_id"])) from None

        try:
            teacher = Teacher.objects.get(pk=data["teacher_id"])
        except Teacher.DoesNotExist:
            raise ObjectNotFoundError("Teacher", str(data["teacher_id"])) from None

        try:
            subject = Subject.objects.get(pk=data["subject_id"])
        except Subject.DoesNotExist:
            raise ObjectNotFoundError("Subject", str(data["subject_id"])) from None

        try:
            time_slot = TimeSlot.objects.get(pk=data["time_slot_id"])
        except TimeSlot.DoesNotExist:
            raise ObjectNotFoundError("TimeSlot", str(data["time_slot_id"])) from None

        room = None
        if room_id := data.get("room_id"):
            from rooms.models import Room

            try:
                room = Room.objects.get(pk=room_id)
            except Room.DoesNotExist:
                raise ObjectNotFoundError("Room", str(room_id)) from None

        # Conflito de professor: mesmo professor, mesmo horário, válido no período.
        self._assert_teacher_available(teacher, time_slot, data["valid_from"])

        # Conflito de sala (se informada).
        if room is not None:
            self._assert_room_available(room, time_slot, data["valid_from"])

        schedule = Schedule.objects.create(
            class_obj=class_obj,
            teacher=teacher,
            subject=subject,
            room=room,
            time_slot=time_slot,
            valid_from=data["valid_from"],
            valid_until=data.get("valid_until"),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", schedule)
        self._log("Grade criada", schedule_id=str(schedule.pk))
        return schedule

    def update_schedule(self, schedule_id, data: dict):
        """Atualiza uma entrada da grade (validando novos conflitos)."""
        from agenda.models import TimeSlot

        schedule = _ScheduleRepo().get_by_id(schedule_id)
        old = {
            "teacher_id": str(schedule.teacher_id),
            "room_id": str(schedule.room_id) if schedule.room_id else None,
            "time_slot_id": str(schedule.time_slot_id),
        }

        updates = {}
        if "valid_from" in data:
            updates["valid_from"] = data["valid_from"]
        if "valid_until" in data:
            updates["valid_until"] = data["valid_until"]

        if "time_slot_id" in data:
            try:
                updates["time_slot"] = TimeSlot.objects.get(pk=data["time_slot_id"])
            except TimeSlot.DoesNotExist:
                raise ObjectNotFoundError("TimeSlot", str(data["time_slot_id"])) from None

        if "teacher_id" in data:
            from teachers.models import Teacher

            try:
                updates["teacher"] = Teacher.objects.get(pk=data["teacher_id"])
            except Teacher.DoesNotExist:
                raise ObjectNotFoundError("Teacher", str(data["teacher_id"])) from None

        if "room_id" in data:
            from rooms.models import Room

            if data["room_id"]:
                try:
                    updates["room"] = Room.objects.get(pk=data["room_id"])
                except Room.DoesNotExist:
                    raise ObjectNotFoundError("Room", str(data["room_id"])) from None
            else:
                updates["room"] = None

        # Re-valida conflitos para professor/sala/horário atuais.
        teacher = updates.get("teacher", schedule.teacher)
        time_slot = updates.get("time_slot", schedule.time_slot)
        room = updates.get("room", schedule.room)
        valid_from = updates.get("valid_from", schedule.valid_from)
        if teacher and time_slot and valid_from:
            self._assert_teacher_available(
                teacher, time_slot, valid_from, exclude_schedule=schedule
            )
            if room is not None:
                self._assert_room_available(room, time_slot, valid_from, exclude_schedule=schedule)

        updates["updated_by"] = self.user
        schedule = _ScheduleRepo().update(schedule, **updates)
        self._record_audit("UPDATE", schedule, old_values=old)
        return schedule

    def create_time_slot(self, data: dict):
        """Cria uma faixa de horário recorrente para a grade escolar."""
        from agenda.models import TimeSlot

        self.validate_required(data, ["day_of_week", "start_time", "end_time"])

        if data["end_time"] <= data["start_time"]:
            raise ValidationError(
                errors={"end_time": ["Horário final deve ser maior que o inicial."]}
            )

        day = data["day_of_week"]
        start = data["start_time"]
        end = data["end_time"]
        if TimeSlot.objects.filter(day_of_week=day, start_time=start, end_time=end).exists():
            raise ValidationError(
                errors={"__all__": ["Já existe um horário idêntico para este dia."]}
            )

        slot = TimeSlot.objects.create(
            day_of_week=day,
            start_time=start,
            end_time=end,
            slot_number=int(data.get("slot_number", 1) or 1),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", slot)
        self._log("Horário criado", time_slot_id=str(slot.pk))
        return slot

    def update_time_slot(self, time_slot_id, data: dict):
        """Atualiza horário sem alterar grades já vinculadas."""
        from agenda.models import Schedule, TimeSlot

        slot = _TimeSlotRepo().get_by_id(time_slot_id)
        if Schedule.objects.filter(time_slot=slot).exists():
            raise BusinessRuleViolationError(
                "Este horário já está em uso na grade. Crie outro horário para alterações futuras."
            )
        self.validate_required(data, ["day_of_week", "start_time", "end_time"])
        if data["end_time"] <= data["start_time"]:
            raise ValidationError(
                errors={"end_time": ["Horário final deve ser maior que o inicial."]}
            )
        if (
            TimeSlot.objects.filter(
                day_of_week=data["day_of_week"],
                start_time=data["start_time"],
                end_time=data["end_time"],
            )
            .exclude(pk=slot.pk)
            .exists()
        ):
            raise ValidationError(
                errors={"__all__": ["Já existe um horário idêntico para este dia."]}
            )
        old = self._snapshot(slot, ["day_of_week", "slot_number", "start_time", "end_time"])
        slot = _TimeSlotRepo().update(
            slot,
            day_of_week=data["day_of_week"],
            slot_number=data["slot_number"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            updated_by=self.user,
        )
        self._record_audit("UPDATE", slot, old_values=old)
        self._log("horário_atualizado", time_slot_id=str(slot.pk))
        return slot

    def _assert_teacher_available(self, teacher, time_slot, valid_from, exclude_schedule=None):
        """Garante que o professor nao esta atribuido a outra turma no mesmo horario."""
        self._assert_slot_available(
            {"teacher": teacher},
            time_slot,
            valid_from,
            "Professor ja esta atribuido a outro item da grade neste horario.",
            exclude_schedule,
        )

    def _assert_room_available(self, room, time_slot, valid_from, exclude_schedule=None):
        """Garante que a sala nao esta em uso concorrente no mesmo horario."""
        self._assert_slot_available(
            {"room": room},
            time_slot,
            valid_from,
            "Sala ja em uso neste horario.",
            exclude_schedule,
        )

    def _assert_slot_available(
        self, filter_kw: dict, time_slot, valid_from, message: str, exclude_schedule=None
    ):
        """Verifica conflito de horario para um recurso (professor ou sala)."""
        from django.db.models import Q

        from agenda.models import Schedule

        qs = Schedule.objects.filter(
            **filter_kw,
            time_slot=time_slot,
            is_active=True,
            valid_from__lte=valid_from,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=valid_from))
        if exclude_schedule is not None:
            qs = qs.exclude(pk=exclude_schedule.pk)
        if qs.exists():
            raise BusinessRuleViolationError(message)
