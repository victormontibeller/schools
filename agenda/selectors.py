"""Consultas somente-leitura para períodos e matriz de horários."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Q
from django.utils import timezone

from agenda.shift_policy import compatible_time_slot_shifts
from base.exceptions import ObjectNotFoundError, PermissionDeniedError
from base.selectors import BaseSelector


@dataclass(frozen=True, slots=True)
class ScheduleMatrixRow:
    """Uma linha da matriz: período comum e suas cinco células ordenadas."""

    time_slot: object
    cells: tuple


@dataclass(frozen=True, slots=True)
class ScheduleMatrixCell:
    """Uma célula identificada pelo dia, vazia ou preenchida por uma versão vigente."""

    day_of_week: str
    schedule: object | None


class ScheduleSelector(BaseSelector):
    """Lê a matriz vigente de turmas e as opções de seus formulários de célula."""

    @property
    def model_class(self):
        """Resolve o modelo sem expor acesso ORM às views."""
        from agenda.contracts import Schedule

        return Schedule

    def get_class_matrix(self, class_id, as_of: date) -> tuple[ScheduleMatrixRow, ...]:
        """Monta a grade de segunda a sexta efetiva na segunda de referência."""
        from agenda.contracts import Schedule, TimeSlot
        from classes.contracts import Class

        try:
            class_shift = Class.objects.values_list("shift", flat=True).get(pk=class_id)
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None
        slots = list(
            TimeSlot.objects.filter(shift__in=compatible_time_slot_shifts(class_shift)).order_by(
                "start_time", "end_time", "slot_number"
            )
        )
        schedules = (
            Schedule.objects.filter(
                class_obj_id=class_id,
                valid_from__lte=as_of,
                is_active=True,
            )
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=as_of))
            .select_related("teacher__user", "subject", "room", "time_slot")
        )
        by_cell = {
            (schedule.day_of_week, schedule.time_slot_id): schedule for schedule in schedules
        }
        return tuple(
            ScheduleMatrixRow(
                time_slot=slot,
                cells=tuple(
                    ScheduleMatrixCell(day, by_cell.get((day, slot.pk)))
                    for day in Schedule.Day.values
                ),
            )
            for slot in slots
        )

    def list_classes_for_matrix(
        self,
        *,
        user_id,
        role_name: str,
        search: str = "",
        order_by: str = "-academic_year",
        page: int = 1,
    ):
        """Lista as turmas que o ator pode selecionar para abrir a matriz."""
        from classes.contracts import Class

        queryset = Class.objects.select_related("class_teacher__user")
        if role_name == "TEACHER":
            queryset = queryset.filter(
                self._teacher_class_scope(user_id, timezone.localdate())
            ).distinct()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(academic_year__icontains=search)
                | Q(grade__icontains=search)
                | Q(education_stage__icontains=search)
                | Q(shift__icontains=search)
            )
        return self._paginate(queryset.order_by(order_by, "name"), page=page)

    def get_class_for_matrix(self, class_id, *, user_id, role_name: str, as_of: date):
        """Retorna a turma da matriz, negando explicitamente escopo docente inválido."""
        from classes.contracts import Class

        queryset = Class.objects.select_related("class_teacher__user").filter(pk=class_id)
        if role_name == "TEACHER":
            queryset = queryset.filter(self._teacher_class_scope(user_id, as_of)).distinct()
            class_obj = queryset.first()
            if class_obj is None:
                raise PermissionDeniedError("Turma fora do escopo do professor.")
            return class_obj
        try:
            return queryset.get()
        except Class.DoesNotExist:
            raise ObjectNotFoundError("Class", str(class_id)) from None

    @staticmethod
    def _teacher_class_scope(user_id, as_of: date) -> Q:
        """Limita o escopo docente à titularidade ou grade vigente na referência."""
        from core.access_selectors import ObjectAccessSelector

        return Q(pk__in=ObjectAccessSelector.teacher_classes(user_id, as_of).values("pk"))

    @classmethod
    def teacher_can_access_class(cls, class_id, *, user_id, as_of: date) -> bool:
        """Revalida o escopo docente sobre o estado atual da turma bloqueada."""
        from classes.contracts import Class

        return (
            Class.objects.filter(pk=class_id)
            .filter(cls._teacher_class_scope(user_id, as_of))
            .exists()
        )

    @staticmethod
    def day_choices() -> tuple[tuple[str, str], ...]:
        """Expõe os cinco dias letivos com seus rótulos para views e forms."""
        from agenda.contracts import Schedule

        return tuple(Schedule.Day.choices)

    def get_schedule_for_class(self, class_id, schedule_id):
        """Retorna uma célula da turma somente quando seu período ainda é compatível."""
        from agenda.contracts import Schedule
        from classes.contracts import Class

        try:
            class_shift = Class.objects.values_list("shift", flat=True).get(pk=class_id)
            return Schedule.objects.select_related(
                "class_obj", "teacher__user", "subject", "room", "time_slot"
            ).get(
                pk=schedule_id,
                class_obj_id=class_id,
                time_slot__shift__in=compatible_time_slot_shifts(class_shift),
            )
        except (Class.DoesNotExist, Schedule.DoesNotExist):
            raise ObjectNotFoundError("Schedule", str(schedule_id)) from None

    def get_effective_schedule(self, class_id, day_of_week, time_slot_id, as_of: date):
        """Retorna a versão visível em uma célula na data de referência."""
        from agenda.contracts import Schedule

        return (
            Schedule.objects.filter(
                class_obj_id=class_id,
                day_of_week=day_of_week,
                time_slot_id=time_slot_id,
                valid_from__lte=as_of,
                is_active=True,
            )
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=as_of))
            .select_related("teacher__user", "subject", "room")
            .first()
        )

    @staticmethod
    def has_schedule_history(class_id) -> bool:
        """Indica se a turma possui qualquer versão de grade, inclusive inativa."""
        from agenda.contracts import Schedule

        return Schedule.all_objects.filter(class_obj_id=class_id).exists()

    @staticmethod
    def get_cell_choices() -> dict[str, tuple[tuple[str, str], ...]]:
        """Fornece choices read-only sem ORM em forms ou views."""
        from rooms.contracts import Room
        from teachers.contracts import Subject, Teacher

        return {
            "teachers": tuple(
                (str(teacher.pk), teacher.full_name)
                for teacher in Teacher.objects.select_related("user").order_by(
                    "user__first_name", "user__last_name"
                )
            ),
            "subjects": tuple(
                (str(subject.pk), str(subject)) for subject in Subject.objects.order_by("name")
            ),
            "rooms": (("", "Sem sala"),)
            + tuple((str(room.pk), str(room)) for room in Room.objects.order_by("name")),
        }


class TimeSlotSelector(BaseSelector):
    """Leituras dos períodos comuns configurados para a escola."""

    @property
    def model_class(self):
        """Resolve o contrato público dos períodos."""
        from agenda.contracts import TimeSlot

        return TimeSlot

    def list_ordered(self, page: int = 1):
        """Lista todos os períodos em ordem de uso na matriz."""
        return self._paginate(
            self.model_class.objects.order_by("start_time", "end_time", "slot_number"), page=page
        )

    def get_compatible_for_class(self, time_slot_id, class_id):
        """Resolve um período somente quando ele é compatível com o turno da turma."""
        from classes.contracts import Class

        try:
            class_shift = Class.objects.values_list("shift", flat=True).get(pk=class_id)
            return self.model_class.objects.get(
                pk=time_slot_id,
                shift__in=compatible_time_slot_shifts(class_shift),
            )
        except (Class.DoesNotExist, self.model_class.DoesNotExist):
            raise ObjectNotFoundError("TimeSlot", str(time_slot_id)) from None
