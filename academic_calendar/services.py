"""CalendarService: regras de negócio para o calendário acadêmico."""

import datetime as dt
import logging

from base.exceptions import BusinessRuleViolationError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _EventRepo(BaseRepository):
    @property
    def model_class(self):
        from academic_calendar.models import CalendarEvent

        return CalendarEvent


class _HolidayRepo(BaseRepository):
    @property
    def model_class(self):
        from academic_calendar.models import Holiday

        return Holiday


class _AcademicYearRepo(BaseRepository):
    @property
    def model_class(self):
        from academic_calendar.models import AcademicYear

        return AcademicYear


class CalendarService(BaseService):
    """Serviço de aplicação para o domínio de calendário acadêmico."""

    # ── Ano letivo ────────────────────────────────────────────────────────────
    def create_academic_year(self, data: dict):
        """Cria um ano letivo validando janela de datas."""
        from academic_calendar.models import AcademicYear

        required = ["name", "start_date", "end_date"]
        errors: dict[str, list[str]] = {}
        for field in required:
            if not data.get(field):
                errors[field] = ["Campo obrigatório."]
        if errors:
            raise ValidationError(errors=errors)

        start = data["start_date"]
        end = data["end_date"]
        if end < start:
            raise ValidationError(errors={"end_date": ["Término deve ser após o início."]})

        name = data["name"].strip()
        if AcademicYear.objects.filter(name=name, start_date=start).exists():
            raise ValidationError(errors={"name": ["Já existe ano letivo com este nome e início."]})

        ay = AcademicYear.objects.create(
            name=name,
            start_date=start,
            end_date=end,
            status=data.get("status", AcademicYear.Status.PLANNED),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", ay)
        self._log("Ano letivo criado", academic_year_id=str(ay.pk))
        return ay

    # ── Eventos ───────────────────────────────────────────────────────────────
    def create_event(self, data: dict):
        """Cria um evento de calendário. Público CLASS exige turma informada."""
        from academic_calendar.models import CalendarEvent

        required = ["title", "start_date", "end_date", "type"]
        errors: dict[str, list[str]] = {}
        for field in required:
            if not data.get(field):
                errors[field] = ["Campo obrigatório."]
        if errors:
            raise ValidationError(errors=errors)

        start = data["start_date"]
        end = data["end_date"]
        if end < start:
            raise ValidationError(errors={"end_date": ["Término deve ser após o início."]})

        audience = data.get("audience", CalendarEvent.Audience.ALL)
        class_obj_id = data.get("class_obj_id")
        if audience == CalendarEvent.Audience.CLASS and not class_obj_id:
            raise ValidationError(
                errors={"class_obj_id": ["Informe a turma para público 'Turma específica'."]}
            )

        class_obj = None
        if class_obj_id:
            from classes.models import Class

            try:
                class_obj = Class.objects.get(pk=class_obj_id)
            except Class.DoesNotExist as exc:
                raise ValidationError(errors={"class_obj_id": ["Turma não encontrada."]}) from exc

        academic_year = None
        if ay_id := data.get("academic_year_id"):
            from academic_calendar.models import AcademicYear

            try:
                academic_year = AcademicYear.objects.get(pk=ay_id)
            except AcademicYear.DoesNotExist as exc:
                raise ValidationError(
                    errors={"academic_year_id": ["Ano letivo não encontrado."]}
                ) from exc

        event = CalendarEvent.objects.create(
            title=data["title"].strip(),
            description=(data.get("description") or "").strip(),
            start_date=start,
            end_date=end,
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            type=data["type"],
            recurrence=data.get("recurrence", {}),
            audience=audience,
            class_obj=class_obj,
            academic_year=academic_year,
            is_public=bool(data.get("is_public", False)),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", event)
        self._log("Evento criado", event_id=str(event.pk))
        return event

    def update_event(self, event_id, data: dict):
        """Atualiza campos permitidos de um evento existente."""
        repo = _EventRepo()
        event = repo.get_by_id(event_id)
        old = {"title": event.title, "start_date": str(event.start_date)}

        allowed = {
            "title",
            "description",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "type",
            "recurrence",
            "audience",
            "is_public",
        }
        updates = {k: v for k, v in data.items() if k in allowed and v is not None}

        if {"start_date", "end_date"} & set(updates) and updates.get(
            "end_date", event.end_date
        ) < updates.get("start_date", event.start_date):
            raise ValidationError(errors={"end_date": ["Término deve ser após o início."]})

        if "class_obj_id" in data:
            if data["class_obj_id"]:
                from classes.models import Class

                try:
                    updates["class_obj"] = Class.objects.get(pk=data["class_obj_id"])
                except Class.DoesNotExist as exc:
                    raise ValidationError(
                        errors={"class_obj_id": ["Turma não encontrada."]}
                    ) from exc
            else:
                updates["class_obj"] = None

        updates["updated_by"] = self.user
        event = repo.update(event, **updates)
        self._record_audit("UPDATE", event, old_values=old)
        return event

    def cancel_event(self, event_id, reason: str = ""):
        """Marca um evento como cancelado, preservando histórico."""
        repo = _EventRepo()
        event = repo.get_by_id(event_id)
        if event.is_cancelled:
            raise BusinessRuleViolationError("Evento já está cancelado.")

        old = {"is_cancelled": event.is_cancelled}
        event.is_cancelled = True
        event.cancel_reason = (reason or "").strip()
        event.updated_by = self.user
        event.save(update_fields=["is_cancelled", "cancel_reason", "updated_by", "updated_at"])
        self._record_audit("UPDATE", event, old_values=old)
        self._log("Evento cancelado", event_id=str(event.pk))
        return event

    # ── Feriados ──────────────────────────────────────────────────────────────
    def create_holiday(self, data: dict):
        """Cria um feriado/dia não letivo."""
        from academic_calendar.models import Holiday

        required = ["name", "date", "type"]
        errors: dict[str, list[str]] = {}
        for field in required:
            if not data.get(field):
                errors[field] = ["Campo obrigatório."]
        if errors:
            raise ValidationError(errors=errors)

        name = data["name"].strip()
        date = data["date"]
        if Holiday.objects.filter(name=name, date=date).exists():
            raise ValidationError(errors={"name": ["Feriado já cadastrado nesta data."]})

        holiday = Holiday.objects.create(
            name=name,
            date=date,
            type=data["type"],
            is_recurring=bool(data.get("is_recurring", False)),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", holiday)
        self._log("Feriado criado", holiday_id=str(holiday.pk))
        return holiday

    # ── Dias letivos ─────────────────────────────────────────────────────────
    def is_working_day(self, date: dt.date) -> bool:
        """Indica se a data é dia letivo (exclui finais de semana e feriados)."""
        from academic_calendar.models import CalendarEvent, Holiday

        if date.weekday() >= 5:  # sábado(5) ou domingo(6)
            return False

        if Holiday.objects.filter(date=date).exists():
            return False
        if Holiday.objects.filter(
            is_recurring=True, date__month=date.month, date__day=date.day
        ).exists():
            return False

        if CalendarEvent.objects.filter(
            start_date__lte=date,
            end_date__gte=date,
            type__in=[CalendarEvent.Type.HOLIDAY, CalendarEvent.Type.NON_SCHOOL_DAY],
        ).exists():
            return False

        return True

    def get_working_days(self, start_date: dt.date, end_date: dt.date) -> list[dt.date]:
        """Retorna os dias letivos de um intervalo, descontando feriados/finais de semana."""
        if end_date < start_date:
            raise ValidationError(errors={"end_date": ["Término deve ser após o início."]})

        days: list[dt.date] = []
        current = start_date
        while current <= end_date:
            if self.is_working_day(current):
                days.append(current)
            current += dt.timedelta(days=1)
        return days
