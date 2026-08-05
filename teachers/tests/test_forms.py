"""Testes dos formularios do modulo teachers."""

import datetime as dt

import pytest

from teachers.forms import SubjectForm, TeacherEditForm, TeacherForm


@pytest.mark.django_db
class TestSubjectForm:
    def test_valid(self):
        form = SubjectForm(data={"name": "Matematica", "code": "MAT", "workload": 200})
        assert form.is_valid()
        assert "is_active" not in form.fields

    def test_edit_exposes_reversible_status(self):
        form = SubjectForm(
            data={"name": "Matematica", "code": "MAT", "workload": 200},
            include_status=True,
        )

        assert form.is_valid()
        assert form.cleaned_data["is_active"] is False
        assert form.fields["is_active"].label == "Ativa"

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
                "first_name": "Maria",
                "last_name": "Souza",
                "email": "maria@example.com",
                "hire_date": dt.date(2025, 1, 15),
                "birth_date": dt.date(1990, 5, 20),
                "gender": "F",
                "nationality": "Brasileira",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "rg_issuer": "SSP",
                "rg_state": "SP",
                "phone_mobile": "11999990000",
            }
        )
        assert form.is_valid()

    def test_registration_is_optional_and_readonly(self):
        form = TeacherForm(
            data={
                "first_name": "Maria",
                "last_name": "Souza",
                "email": "maria@example.com",
                "hire_date": dt.date(2025, 1, 15),
                "birth_date": dt.date(1990, 5, 20),
                "gender": "F",
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "phone_mobile": "11999990000",
            }
        )
        assert form.is_valid()
        assert form.fields["registration_number"].widget.attrs["readonly"] is True

    def test_invalid_email(self):
        form = TeacherForm(data={"email": "invalido"})
        assert not form.is_valid()
        assert "email" in form.errors


@pytest.mark.django_db
class TestTeacherEditForm:
    def test_requires_all_personal_fields_for_profile_update(self):
        form = TeacherEditForm(data={})

        assert not form.is_valid()
        for field_name in [
            "first_name",
            "last_name",
            "hire_date",
            "birth_date",
            "gender",
            "cpf",
            "rg_number",
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
                "cpf": "390.533.447-05",
                "rg_number": "1234567",
                "phone_mobile": "(11) 99999-0000",
                "version": 0,
            }
        )

        assert form.is_valid()
        assert "email" not in form.fields
        assert form.fields["email_display"].disabled is True
        assert form.fields["rg_number"].widget.attrs["data_grid"] == "col-12 col-md-6"
        assert form.fields["phone_mobile"].widget.attrs["data_grid"] == "col-12 col-md-6"
        assert (
            form.fields["accepts_email_notifications"].widget.attrs["data_grid"]
            == "col-12 col-md-6"
        )
        assert (
            form.fields["accepts_whatsapp_notifications"].widget.attrs["data_grid"]
            == "col-12 col-md-6"
        )
