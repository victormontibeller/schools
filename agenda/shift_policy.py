"""Política compartilhada de compatibilidade entre turnos de turma e períodos."""

_TIME_SLOT_SHIFTS_BY_CLASS_SHIFT: dict[str, tuple[str, ...]] = {
    "MORNING": ("MORNING",),
    "AFTERNOON": ("AFTERNOON",),
    "NIGHT": ("NIGHT",),
    "FULL": ("MORNING", "AFTERNOON"),
}


def compatible_time_slot_shifts(class_shift: str) -> tuple[str, ...]:
    """Retorna os turnos de período aceitos pelo turno informado da turma."""
    return _TIME_SLOT_SHIFTS_BY_CLASS_SHIFT.get(str(class_shift), ())


def is_time_slot_compatible(class_shift: str, time_slot_shift: str) -> bool:
    """Indica se um período pode compor a matriz de uma turma."""
    return str(time_slot_shift) in compatible_time_slot_shifts(class_shift)
