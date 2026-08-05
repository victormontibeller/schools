"""Fachada pública dos comandos auditáveis da matriz de horários."""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Q

from agenda.schedule_commands import ScheduleCommandMixin
from agenda.shift_policy import is_time_slot_compatible
from agenda.time_slot_commands import TimeSlotCommandMixin
from base.exceptions import (
    BusinessRuleViolationError,
    ObjectNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from base.services import BaseService


class ScheduleService(ScheduleCommandMixin, TimeSlotCommandMixin, BaseService):
    """Expõe os comandos de períodos e matriz e concentra seus invariantes compartilhados."""

    def _resolve_schedule_data(self, data: dict) -> dict:
        from agenda.contracts import TimeSlot
        from classes.contracts import Class
        from rooms.contracts import Room
        from teachers.contracts import Subject, Teacher

        self.validate_required(
            data,
            [
                "class_obj_id",
                "teacher_id",
                "subject_id",
                "time_slot_id",
                "day_of_week",
                "valid_from",
            ],
        )
        self._validate_day(data["day_of_week"], "day_of_week")
        valid_from = data["valid_from"]
        valid_until = data.get("valid_until")
        if not isinstance(valid_from, date):
            raise ValidationError(errors={"valid_from": ["Informe uma data de vigência válida."]})
        if valid_until is not None and not isinstance(valid_until, date):
            raise ValidationError(
                errors={"valid_until": ["Informe uma data de encerramento válida."]}
            )
        valid_from = self._week_monday(valid_from)
        valid_until = self._week_sunday(valid_until) if valid_until is not None else None
        if valid_until is not None and valid_until < valid_from:
            raise ValidationError(
                errors={"valid_until": ["O encerramento não pode ser anterior ao início."]}
            )

        class_obj = self._get_object(Class, data["class_obj_id"], "Class")
        teacher = self._get_object(Teacher, data["teacher_id"], "Teacher")
        subject = self._get_object(Subject, data["subject_id"], "Subject")
        time_slot = self._get_object(TimeSlot, data["time_slot_id"], "TimeSlot")
        room = self._get_object(Room, data["room_id"], "Room") if data.get("room_id") else None
        if not is_time_slot_compatible(class_obj.shift, time_slot.shift):
            raise BusinessRuleViolationError(
                "O período informado não pertence ao turno desta turma."
            )
        self._assert_teacher_subject_enabled(teacher, subject)
        return {
            "class_obj": class_obj,
            "teacher": teacher,
            "subject": subject,
            "room": room,
            "time_slot": time_slot,
            "day_of_week": data["day_of_week"],
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

    def _get_class_in_scope(self, class_id, *, as_of: date):
        """Resolve a turma pelo selector, restringindo comandos de professores ao próprio escopo."""
        from agenda.selectors import ScheduleSelector
        from core.permissions import role_name

        return ScheduleSelector().get_class_for_matrix(
            class_id,
            user_id=getattr(self.user, "pk", None),
            role_name=role_name(self.user),
            as_of=as_of,
        )

    def _assert_class_in_scope(self, class_id, *, as_of: date) -> None:
        """Nega a escrita antes de qualquer mutação quando a turma não pertence ao professor."""
        self._get_class_in_scope(class_id, as_of=as_of)

    def _assert_locked_class_in_scope(self, class_obj, *, as_of: date) -> None:
        """Revalida o escopo docente depois que a turma já está bloqueada."""
        from agenda.selectors import ScheduleSelector
        from core.permissions import role_name

        if role_name(self.user) != "TEACHER":
            return
        if not ScheduleSelector.teacher_can_access_class(
            class_obj.pk,
            user_id=getattr(self.user, "pk", None),
            as_of=as_of,
        ):
            raise PermissionDeniedError("Turma fora do escopo do professor.")

    def _lock_class_and_revalidate_scope(self, class_id, *, as_of: date):
        """Bloqueia a turma e valida novamente o escopo antes de uma escrita."""
        from classes.contracts import Class

        try:
            class_obj = Class.objects.select_for_update().get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None
        self._assert_locked_class_in_scope(class_obj, as_of=as_of)
        return class_obj

    @staticmethod
    def _assert_teacher_subject_enabled(teacher, subject) -> None:
        """Confirma a habilitação disciplinar usando o professor mais recente."""
        if not teacher.subjects.filter(pk=subject.pk).exists():
            raise BusinessRuleViolationError(
                "O professor não está habilitado para esta disciplina."
            )

    def _assert_schedule_available(self, data: dict, exclude_schedule=None) -> None:
        common = (data["day_of_week"], data["time_slot"], data["valid_from"], data["valid_until"])
        self._assert_resource_available(
            {"class_obj": data["class_obj"]},
            *common,
            "A turma já possui uma célula neste período.",
            exclude_schedule,
        )
        self._assert_resource_available(
            {"teacher": data["teacher"]},
            *common,
            "O professor já está alocado neste período.",
            exclude_schedule,
        )
        if data["room"] is not None:
            self._assert_resource_available(
                {"room": data["room"]},
                *common,
                "A sala já está alocada neste período.",
                exclude_schedule,
            )

    @staticmethod
    def _assert_schedule_shift_compatible(data: dict) -> None:
        """Revalida a compatibilidade usando as instâncias mais recentes dos recursos."""
        if not is_time_slot_compatible(data["class_obj"].shift, data["time_slot"].shift):
            raise BusinessRuleViolationError(
                "O período informado não pertence ao turno desta turma."
            )

    def _lock_schedule_resources(self, schedule_data_items: tuple[dict, ...] | list[dict]) -> None:
        """Trava recursos e substitui snapshots antigos pelas instâncias bloqueadas."""
        for field in ("class_obj", "teacher", "room", "time_slot"):
            resources = {
                (type(item[field]), item[field].pk): item[field]
                for item in schedule_data_items
                if item[field] is not None
            }
            locked_resources = {}
            for _identity, resource in sorted(resources.items(), key=lambda item: str(item[0][1])):
                locked_resources[_identity] = (
                    type(resource).objects.select_for_update().get(pk=resource.pk)
                )
            for item in schedule_data_items:
                resource = item[field]
                if resource is not None:
                    item[field] = locked_resources[(type(resource), resource.pk)]
        for item in schedule_data_items:
            self._assert_schedule_shift_compatible(item)
            self._assert_locked_class_in_scope(item["class_obj"], as_of=item["valid_from"])
            self._assert_teacher_subject_enabled(item["teacher"], item["subject"])

    @staticmethod
    def _lock_time_slot_catalog() -> None:
        """Serializa mutações do catálogo por tenant no PostgreSQL."""
        from django.db import connection

        if connection.vendor != "postgresql":
            return
        from tenancy.contracts import School

        try:
            School.objects.select_for_update().only("pk").get(schema_name=connection.schema_name)
        except School.DoesNotExist:
            raise ObjectNotFoundError("School", connection.schema_name) from None

    @staticmethod
    def _is_effective_on(schedule, as_of: date) -> bool:
        return schedule.valid_from <= as_of and (
            schedule.valid_until is None or schedule.valid_until >= as_of
        )

    @staticmethod
    def _week_monday(value: date) -> date:
        """Converte qualquer data da semana ao identificador canônico de segunda-feira."""
        return value - timedelta(days=value.weekday())

    @classmethod
    def _week_sunday(cls, value: date) -> date:
        """Converte qualquer data da semana ao seu limite inclusivo de domingo."""
        return cls._week_monday(value) + timedelta(days=6)

    def _assert_resource_available(
        self,
        filters: dict,
        day_of_week,
        time_slot,
        valid_from,
        valid_until,
        message,
        exclude_schedule,
    ) -> None:
        from agenda.contracts import Schedule

        candidates = Schedule.objects.filter(
            **filters,
            day_of_week=day_of_week,
            time_slot=time_slot,
            is_active=True,
            valid_from__lte=valid_until if valid_until is not None else date.max,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=valid_from))
        if exclude_schedule is not None:
            candidates = candidates.exclude(pk=exclude_schedule.pk)
        if candidates.exists():
            raise BusinessRuleViolationError(message)

    def _create_resolved_schedule(self, data: dict):
        from agenda.contracts import Schedule

        return Schedule.objects.create(**data, created_by=self.user, updated_by=self.user)

    @staticmethod
    def _get_object(model_class, object_id, label: str):
        try:
            return model_class.objects.get(pk=object_id)
        except model_class.DoesNotExist:
            raise ObjectNotFoundError(label, str(object_id)) from None

    def _get_schedule_for_update(self, schedule_id):
        from agenda.contracts import Schedule

        try:
            return Schedule.objects.select_for_update().get(pk=schedule_id)
        except Schedule.DoesNotExist:
            raise ObjectNotFoundError("Schedule", str(schedule_id)) from None

    @staticmethod
    def _validate_day(day_of_week: str, field: str) -> None:
        from agenda.contracts import Schedule

        if day_of_week not in Schedule.Day.values:
            raise ValidationError(errors={field: ["Informe um dia letivo válido."]})

    @staticmethod
    def _validate_time_slot_interval(start_time, end_time) -> None:
        if end_time <= start_time:
            raise ValidationError(errors={"end_time": ["O fim deve ser posterior ao início."]})

    @staticmethod
    def _validate_version_value(version) -> None:
        if not isinstance(version, int):
            raise ValidationError(errors={"version": ["Versão inválida."]})

    @staticmethod
    def _time_slot_overlaps(start_time, end_time, exclude_slot=None) -> bool:
        from agenda.contracts import TimeSlot

        slots = TimeSlot.objects.filter(start_time__lt=end_time, end_time__gt=start_time)
        if exclude_slot is not None:
            slots = slots.exclude(pk=exclude_slot.pk)
        return slots.exists()
