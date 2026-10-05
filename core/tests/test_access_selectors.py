"""Testes das consultas de escopo usadas pelo RBAC."""

from unittest.mock import MagicMock, patch

import pytest

from core.access_selectors import ObjectAccessSelector


@pytest.mark.parametrize(
    ("target", "method", "args"),
    [
        ("activities.models.Activity", "teacher_can_access_activity", ("u", "a")),
        ("attendance.models.AttendanceRecord", "teacher_can_access_attendance", ("u", "r")),
    ],
)
def test_direct_scope_selectors_return_exists_result(target, method, args):
    manager = MagicMock()
    manager.filter.return_value.exists.return_value = True
    with patch(f"{target}.objects", manager):
        assert getattr(ObjectAccessSelector, method)(*args) is True
    manager.filter.return_value.exists.assert_called_once_with()


def test_guardian_scope_delegates_to_canonical_selectors():
    with patch(
        "guardians.selectors.GuardianSelector.user_can_access_student", return_value=True
    ) as student_access:
        assert ObjectAccessSelector.guardian_can_access_student("u", "s") is True
    student_access.assert_called_once_with("u", "s")

    with patch(
        "activities.selectors.ActivitySelector.guardian_can_access_activity", return_value=True
    ) as activity_access:
        assert ObjectAccessSelector.guardian_can_access_activity("u", "a") is True
    activity_access.assert_called_once_with("u", "a")
