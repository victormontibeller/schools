"""Seed DEMO da matriz semanal de horários."""

import datetime as dt


class AgendaDemoSeedMixin:
    """Cria uma grade demonstrativa idempotente para as turmas regulares."""

    def populate_schedule(self) -> int:
        """Popula cinco dias letivos e 25 células por turma DEMO."""
        from agenda.contracts import Schedule, TimeSlot
        from classes.contracts import Class
        from rooms.contracts import Room
        from teachers.contracts import Subject, Teacher

        period_specs = (
            (1, TimeSlot.Shift.MORNING, dt.time(7, 30), dt.time(8, 20)),
            (2, TimeSlot.Shift.MORNING, dt.time(8, 20), dt.time(9, 10)),
            (3, TimeSlot.Shift.MORNING, dt.time(9, 30), dt.time(10, 20)),
            (4, TimeSlot.Shift.MORNING, dt.time(10, 20), dt.time(11, 10)),
            (5, TimeSlot.Shift.MORNING, dt.time(11, 10), dt.time(12, 0)),
            (6, TimeSlot.Shift.AFTERNOON, dt.time(13, 0), dt.time(13, 50)),
            (7, TimeSlot.Shift.AFTERNOON, dt.time(13, 50), dt.time(14, 40)),
            (8, TimeSlot.Shift.AFTERNOON, dt.time(15, 0), dt.time(15, 50)),
            (9, TimeSlot.Shift.AFTERNOON, dt.time(15, 50), dt.time(16, 40)),
            (10, TimeSlot.Shift.AFTERNOON, dt.time(16, 40), dt.time(17, 30)),
        )
        time_slots = {
            number: self._ensure(
                TimeSlot,
                {"start_time": start_time, "end_time": end_time, "shift": shift},
                {"slot_number": number},
            )
            for number, shift, start_time, end_time in period_specs
        }
        class_names = ("6º A", "6º B", "7º A")
        subject_codes = ("MAT", "POR", "CIE", "HIS", "GEO", "ING", "ART", "EDF", "TEC", "FIL")
        classes_by_name = {
            class_obj.name: class_obj
            for class_obj in Class.objects.filter(name__in=class_names, academic_year=2026)
        }
        subjects = {
            subject.code: subject for subject in Subject.objects.filter(code__in=subject_codes)
        }
        teachers = {
            subject_code: Teacher.objects.get(registration_number=f"PROF-2026-{index:03d}")
            for index, subject_code in enumerate(subject_codes, start=1)
        }
        rooms = {
            room.code: room
            for room in Room.objects.filter(
                code__in=("SALA-101", "SALA-102", "LAB-CIE", "BIB-001", "QUADRA")
            )
        }
        room_by_subject = {
            "CIE": rooms["LAB-CIE"],
            "EDF": rooms["QUADRA"],
            "POR": rooms["BIB-001"],
        }
        schedules_by_class = {
            "6º A": (
                range(1, 6),
                rooms["SALA-101"],
                (
                    (Schedule.Day.MON, ("MAT", "POR", "CIE", "HIS", "GEO")),
                    (Schedule.Day.TUE, ("POR", "MAT", "ING", "ART", "EDF")),
                    (Schedule.Day.WED, ("CIE", "HIS", "GEO", "MAT", "TEC")),
                    (Schedule.Day.THU, ("MAT", "POR", "CIE", "HIS", "FIL")),
                    (Schedule.Day.FRI, ("GEO", "ING", "ART", "EDF", "TEC")),
                ),
            ),
            "7º A": (
                range(1, 6),
                rooms["SALA-102"],
                (
                    (Schedule.Day.MON, ("POR", "CIE", "HIS", "GEO", "ING")),
                    (Schedule.Day.TUE, ("MAT", "ING", "ART", "EDF", "TEC")),
                    (Schedule.Day.WED, ("HIS", "GEO", "MAT", "TEC", "FIL")),
                    (Schedule.Day.THU, ("POR", "CIE", "HIS", "FIL", "GEO")),
                    (Schedule.Day.FRI, ("ING", "ART", "EDF", "TEC", "MAT")),
                ),
            ),
            "6º B": (
                range(6, 11),
                rooms["SALA-101"],
                (
                    (Schedule.Day.MON, ("MAT", "POR", "CIE", "HIS", "GEO")),
                    (Schedule.Day.TUE, ("POR", "MAT", "ING", "ART", "EDF")),
                    (Schedule.Day.WED, ("CIE", "HIS", "GEO", "MAT", "TEC")),
                    (Schedule.Day.THU, ("MAT", "POR", "CIE", "HIS", "FIL")),
                    (Schedule.Day.FRI, ("GEO", "ING", "ART", "EDF", "TEC")),
                ),
            ),
        }
        valid_from = dt.date(2026, 2, 2)
        count = 0
        for class_name, (slot_numbers, class_room, days) in schedules_by_class.items():
            class_obj = classes_by_name[class_name]
            for day_of_week, subject_codes in days:
                for slot_number, subject_code in zip(slot_numbers, subject_codes, strict=True):
                    subject = subjects[subject_code]
                    self._ensure(
                        Schedule,
                        {
                            "class_obj": class_obj,
                            "day_of_week": day_of_week,
                            "time_slot": time_slots[slot_number],
                            "valid_from": valid_from,
                        },
                        {
                            "teacher": teachers[subject_code],
                            "subject": subject,
                            "room": room_by_subject.get(subject_code, class_room),
                            "valid_until": None,
                        },
                    )
                    count += 1
        return count
