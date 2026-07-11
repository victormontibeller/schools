"""Testes das consultas de escopo usadas pelo RBAC."""

from unittest.mock import MagicMock, patch

import pytest

from core.access_selectors import ObjectAccessSelector


@pytest.mark.parametrize(
    ("target", "method", "args"),
    [
        ("guardians.models.StudentGuardian", "guardian_can_access_student", ("u", "s")),
        ("activities.models.Activity", "guardian_can_access_activity", ("u", "a")),
        ("activities.models.Activity", "teacher_can_access_activity", ("u", "a")),
        ("attendance.models.AttendanceRecord", "teacher_can_access_attendance", ("u", "r")),
        ("classes.models.Enrollment", "teacher_can_access_student", ("u", "s")),
    ],
)
def test_direct_scope_selectors_return_exists_result(target, method, args):
    manager = MagicMock()
    manager.filter.return_value.exists.return_value = True
    with patch(f"{target}.objects", manager):
        assert getattr(ObjectAccessSelector, method)(*args) is True
    manager.filter.return_value.exists.assert_called_once_with()


def test_teacher_class_scope_checks_teacher_and_schedule_relationships():
    manager = MagicMock()
    manager.filter.return_value.filter.return_value.exists.return_value = True
    with patch("classes.models.Class.objects", manager):
        assert ObjectAccessSelector.teacher_can_access_class("u", "c") is True
    manager.filter.return_value.filter.return_value.exists.assert_called_once_with()
