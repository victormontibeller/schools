"""Testes dos formularios do modulo teachers."""

import datetime as dt

import pytest

from teachers.forms import SubjectForm, TeacherEditForm, TeacherForm


@pytest.mark.django_db
class TestSubjectForm:
    def test_valid(self):
        form = SubjectForm(data={"name": "Matematica", "code": "MAT", "workload": 200})
        assert form.is_valid()

    def test_blank_name(self):
        form = SubjectForm(data={"name": "", "code": "MAT"})
        assert not form.is_valid()
        assert "name" in form.errors
        assert "workload" in form.errors


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


@pytest.mark.django_db
class TestTeacherEditForm:
    def test_requires_all_profile_fields(self):
        form = TeacherEditForm(data={})

        assert not form.is_valid()
        for field_name in [
            "first_name",
            "last_name",
            "registration_number",
            "hire_date",
            "birth_date",
            "gender",
            "nationality",
            "cpf",
            "rg_number",
            "rg_issuer",
            "rg_state",
            "phone_mobile",
        ]:
            assert field_name in form.errors

    def test_valid_with_complete_payload(self):
        form = TeacherEditForm(
            data={
                "first_name": "Maria",
                "last_name": "Souza",
                "registration_number": "MAT-010",
                "hire_date": dt.date(2025, 1, 15),
                "birth_date": dt.date(1990, 5, 20),
                "gender": "F",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "(11) 99999-0000",
            }
        )

        assert form.is_valid()
