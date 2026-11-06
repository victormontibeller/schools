"""Prazo administrativo em São Paulo, independente do calendário letivo."""

import datetime as dt
from zoneinfo import ZoneInfo

from base.exceptions import BusinessRuleViolationError, ValidationError
from service_requests.models import AdministrativeCalendar

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class ResponseDeadline:
    @staticmethod
    def calculate(opened_at):
        calendar = AdministrativeCalendar.objects.first() or AdministrativeCalendar()
        day = opened_at.astimezone(SAO_PAULO).date() + dt.timedelta(days=1)
        closed = set(calendar.closed_dates)
        for _ in range(370):
            if day.weekday() in calendar.weekdays and day.isoformat() not in closed:
                return dt.datetime.combine(day, calendar.closes_at, tzinfo=SAO_PAULO)
            day += dt.timedelta(days=1)
        raise BusinessRuleViolationError("Configure ao menos um dia de atendimento no próximo ano.")

    @staticmethod
    def validate(weekdays, opens_at, closes_at, closed_dates):
        if not weekdays or set(weekdays) - set(range(7)):
            raise ValidationError(errors={"weekdays": ["Selecione dias de atendimento válidos."]})
        if not opens_at or not closes_at or opens_at >= closes_at:
            raise ValidationError(
                errors={"closes_at": ["O encerramento deve ocorrer após a abertura."]}
            )
        try:
            normalized = sorted(
                {dt.date.fromisoformat(value).isoformat() for value in closed_dates}
            )
        except (TypeError, ValueError):
            raise ValidationError(errors={"closed_dates": ["Use datas AAAA-MM-DD."]}) from None
        if len(normalized) > 366:
            raise ValidationError(errors={"closed_dates": ["Informe até 366 fechamentos."]})
        return normalized
