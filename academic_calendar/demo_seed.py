"""Seed DEMO do calendário acadêmico."""

import datetime as dt


class CalendarDemoSeedMixin:
    """Cria o calendário demonstrativo atual."""

    def populate_calendar(self) -> int:
        """Cria ano letivo, 13 feriados e seis eventos da agenda de 2026."""
        from academic_calendar.contracts import AcademicYear, CalendarEvent, Holiday
        from classes.contracts import Class

        academic_year = self._ensure(
            AcademicYear,
            {"name": "2026", "start_date": dt.date(2026, 2, 2)},
            {"end_date": dt.date(2026, 12, 18), "status": AcademicYear.Status.IN_PROGRESS},
        )
        holidays = [
            ("Confraternização Universal", dt.date(2026, 1, 1), Holiday.Type.NATIONAL),
            ("Aniversário da Cidade de São Paulo", dt.date(2026, 1, 25), Holiday.Type.MUNICIPAL),
            ("Paixão de Cristo", dt.date(2026, 4, 3), Holiday.Type.NATIONAL),
            ("Tiradentes", dt.date(2026, 4, 21), Holiday.Type.NATIONAL),
            ("Dia Mundial do Trabalho", dt.date(2026, 5, 1), Holiday.Type.NATIONAL),
            ("Corpus Christi", dt.date(2026, 6, 4), Holiday.Type.MUNICIPAL),
            ("Data Magna do Estado de São Paulo", dt.date(2026, 7, 9), Holiday.Type.STATE),
            ("Independência do Brasil", dt.date(2026, 9, 7), Holiday.Type.NATIONAL),
            ("Nossa Senhora Aparecida", dt.date(2026, 10, 12), Holiday.Type.NATIONAL),
            ("Finados", dt.date(2026, 11, 2), Holiday.Type.NATIONAL),
            ("Proclamação da República", dt.date(2026, 11, 15), Holiday.Type.NATIONAL),
            (
                "Dia Nacional de Zumbi e da Consciência Negra",
                dt.date(2026, 11, 20),
                Holiday.Type.NATIONAL,
            ),
            ("Natal", dt.date(2026, 12, 25), Holiday.Type.NATIONAL),
        ]
        for name, date, holiday_type in holidays:
            self._ensure(
                Holiday, {"name": name, "date": date}, {"type": holiday_type, "is_recurring": False}
            )
        event_specs = [
            (
                "Reunião de responsáveis — 1º bimestre",
                dt.date(2026, 4, 9),
                CalendarEvent.Type.MEETING,
                CalendarEvent.Audience.GUARDIANS,
                None,
            ),
            (
                "Conselho de classe — 1º bimestre",
                dt.date(2026, 4, 16),
                CalendarEvent.Type.MEETING,
                CalendarEvent.Audience.TEACHERS,
                None,
            ),
            (
                "Avaliação diagnóstica — 6º A",
                dt.date(2026, 3, 17),
                CalendarEvent.Type.ASSESSMENT,
                CalendarEvent.Audience.CLASS,
                "6º A",
            ),
            (
                "Feira de Ciências",
                dt.date(2026, 8, 22),
                CalendarEvent.Type.SCHOOL_EVENT,
                CalendarEvent.Audience.ALL,
                None,
            ),
            (
                "Mostra cultural — 6º B",
                dt.date(2026, 9, 18),
                CalendarEvent.Type.SCHOOL_EVENT,
                CalendarEvent.Audience.CLASS,
                "6º B",
            ),
            (
                "Reunião pedagógica de encerramento",
                dt.date(2026, 12, 16),
                CalendarEvent.Type.MEETING,
                CalendarEvent.Audience.TEACHERS,
                None,
            ),
        ]
        for title, date, event_type, audience, class_name in event_specs:
            class_obj = (
                Class.objects.filter(name=class_name, academic_year=2026).first()
                if class_name
                else None
            )
            self._ensure(
                CalendarEvent,
                {"title": title, "start_date": date},
                {
                    "description": "Evento institucional do calendário DEMO.",
                    "end_date": date,
                    "start_time": (
                        dt.time(18, 30) if event_type == CalendarEvent.Type.MEETING else None
                    ),
                    "end_time": (
                        dt.time(20, 0) if event_type == CalendarEvent.Type.MEETING else None
                    ),
                    "type": event_type,
                    "recurrence": {},
                    "audience": audience,
                    "class_obj": class_obj,
                    "academic_year": academic_year,
                    "is_public": True,
                    "is_cancelled": False,
                    "cancel_reason": "",
                },
            )
        return len(holidays)
