"""Testes dos formularios do modulo teachers."""

import datetime as dt

import pytest

from teachers.forms import SubjectForm, TeacherForm


@pytest.mark.django_db
class TestSubjectForm:
    def test_valid(self):
        form = SubjectForm(data={"name": "Matematica", "code": "MAT", "workload": 200})
        assert form.is_valid()

    def test_blank_name(self):
        form = SubjectForm(data={"name": "", "code": "MAT"})
        assert not form.is_valid()
        assert "name" in form.errors


@pytest.mark.django_db
class TestTeacherForm:
    def test_valid(self):
        form = TeacherForm(
            data={
                "user_id": "00000000-0000-0000-0000-000000000001",
                "registration_number": "MAT-001",
            }
        )
        assert form.is_valid()

    def test_valid_with_hire_date(self):
        form = TeacherForm(
            data={
                "user_id": "00000000-0000-0000-0000-000000000001",
                "registration_number": "MAT-002",
                "hire_date": dt.date(2025, 1, 15),
            }
        )
        assert form.is_valid()

    def test_blank_registration(self):
        form = TeacherForm(
            data={
                "user_id": "00000000-0000-0000-0000-000000000001",
                "registration_number": "",
            }
        )
        assert not form.is_valid()
        assert "registration_number" in form.errors

    def test_invalid_user_id(self):
        form = TeacherForm(
            data={
                "user_id": "not-a-uuid",
                "registration_number": "MAT-003",
            }
        )
        assert not form.is_valid()
        assert "user_id" in form.errors
