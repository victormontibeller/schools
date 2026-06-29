"""Seed de calendário: ano letivo, feriados nacionais e 2 eventos de demo."""
import datetime as dt

from core.models import School
from django_tenants.utils import tenant_context

school = School.objects.get(schema_name="demo")

with tenant_context(school):
    from academic_calendar.models import AcademicYear, CalendarEvent, Holiday
    from classes.models import Class

    ay, _ = AcademicYear.objects.get_or_create(
        name="2026",
        start_date=dt.date(2026, 2, 1),
        defaults={
            "end_date": dt.date(2026, 12, 15),
            "status": AcademicYear.Status.IN_PROGRESS,
        },
    )
    print("Ano letivo:", ay)

    national = [
        (dt.date(2026, 1, 1), "Confraternização Universal"),
        (dt.date(2026, 4, 21), "Tiradentes"),
        (dt.date(2026, 5, 1), "Dia do Trabalho"),
        (dt.date(2026, 9, 7), "Independência do Brasil"),
        (dt.date(2026, 10, 12), "Nossa Senhora Aparecida"),
        (dt.date(2026, 11, 2), "Finados"),
        (dt.date(2026, 11, 15), "Proclamação da República"),
        (dt.date(2026, 12, 25), "Natal"),
    ]
    for date, name in national:
        Holiday.objects.get_or_create(
            name=name,
            date=date,
            defaults={
                "type": Holiday.Type.NATIONAL,
                "is_recurring": False,
            },
        )
    print(f" {Holiday.objects.count()} feriados nacionais.")

    events = [
        (
            "Reunião de Pais — 1º Bimestre",
            dt.date(2026, 7, 4),
            CalendarEvent.Type.MEETING,
            CalendarEvent.Audience.GUARDIANS,
        ),
        (
            "Festa Junina",
            dt.date(2026, 6, 26),
            CalendarEvent.Type.SCHOOL_EVENT,
            CalendarEvent.Audience.ALL,
        ),
    ]
    for title, date, etype, audience in events:
        CalendarEvent.objects.get_or_create(
            title=title,
            start_date=date,
            defaults={
                "end_date": date,
                "type": etype,
                "audience": audience,
                "academic_year": ay,
                "is_public": True,
            },
        )
    print(f" {CalendarEvent.objects.count()} eventos.")
    print("Seed de calendário concluído.")