"""Testes HTTP da Agenda escolar."""

import datetime as dt

import pytest
from django.urls import reverse

from classes.models import Class
from core.models import CustomUser, Role
from guardians.models import Guardian, StudentGuardian
from student_diary.models import DailyDiary, DiaryCategory, DiaryMeal
from student_diary.tests.test_services import (
    _class,
    _enroll,
    _fixed_answers,
    _student,
    _teacher,
)


def _daily_post(class_obj, students, *, missing_answer=False, notes="Registro pela tela"):
    answers = _fixed_answers()
    data = {"class_id": str(class_obj.pk), "date": "2026-07-12"}
    for index, student in enumerate(students):
        prefix = f"student-{student.pk}"
        for answer_index, (category_id, option_id) in enumerate(answers.items()):
            omit_answer = missing_answer and index == len(students) - 1 and answer_index == 0
            if not omit_answer:
                data[f"{prefix}-answer_{category_id}"] = option_id
        data[f"{prefix}-meal_MORNING_SNACK"] = DiaryMeal.Status.ATE_WELL
        data[f"{prefix}-meal_LUNCH"] = DiaryMeal.Status.ATE_PARTIALLY
        data[f"{prefix}-notes"] = notes
    return data


def _user_for_role(role_name, email):
    role = Role.objects.get(name=role_name)
    return CustomUser.objects.create_user(email=email, password="Senha123", role=role)


@pytest.mark.django_db
def test_diary_daily_renders_canonical_roster_for_admin(client, user):
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    client.force_login(user)

    response = client.get(
        reverse("diary_daily"),
        {"class_id": class_obj.pk, "date": "2026-07-12"},
    )

    assert response.status_code == 200
    assert b"Agenda" in response.content
    assert b"Lista da Agenda" in response.content
    assert b"page-header sm-page-header" in response.content
    assert b"sm-page-content--viewport" in response.content
    assert b"sm-diary-filter-form" in response.content
    assert b"sm-diary-context-bar" in response.content
    assert b"sm-diary-table" in response.content
    assert b"diary-student-editor" not in response.content
    assert b'value="2026-07-12"' in response.content
    assert b"diary-roster-card" in response.content
    assert reverse("diary_student_history", args=[student.pk]).encode() in response.content
    assert b"Caf\xc3\xa9 da manh\xc3\xa3" in response.content
    assert b"N\xc3\xa3o estava presente" in response.content
    assert f'name="student-{student.pk}-meal_MORNING_SNACK"'.encode() in response.content
    assert f'name="student-{student.pk}-notes"'.encode() in response.content
    assert response.content.count(b"Salvar Agenda") == 1
    assert response.content.count(reverse("diary_configuration").encode()) == 1


@pytest.mark.django_db
def test_diary_daily_without_filters_renders_compact_empty_state(client, user):
    client.force_login(user)

    response = client.get(reverse("diary_daily"))

    assert response.status_code == 200
    assert b"Lista da Agenda" in response.content
    assert b"form-select form-select-sm" in response.content
    assert b"form-control form-control-sm" in response.content
    assert b"Selecione uma turma e uma data" in response.content
    assert b"sm-diary-table" not in response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("shift", "expected_meal", "unexpected_meal"),
    [
        (Class.Shift.MORNING, "Caf\u00e9 da manh\u00e3", "Caf\u00e9 da tarde"),
        (Class.Shift.AFTERNOON, "Caf\u00e9 da tarde", "Caf\u00e9 da manh\u00e3"),
        (Class.Shift.FULL, "Caf\u00e9 da manh\u00e3", None),
    ],
)
def test_diary_daily_renders_meal_columns_for_class_shift(
    client, user, shift, expected_meal, unexpected_meal
):
    class_obj = _class(user, shift=shift)
    student = _student(user)
    _enroll(user, class_obj, student)
    client.force_login(user)

    response = client.get(
        reverse("diary_daily"),
        {"class_id": class_obj.pk, "date": "2026-07-12"},
    )

    content = response.content.decode()
    assert expected_meal in content
    assert "Almo\u00e7o" in content
    if unexpected_meal:
        assert unexpected_meal not in content


@pytest.mark.django_db
def test_diary_daily_renders_only_enabled_aspect_columns(client, user):
    disabled = DiaryCategory.objects.get(code=DiaryCategory.Aspect.BOWEL_MOVEMENT)
    disabled.is_enabled = False
    disabled.save(update_fields=["is_enabled"])
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    client.force_login(user)

    response = client.get(
        reverse("diary_daily"),
        {"class_id": class_obj.pk, "date": "2026-07-12"},
    )

    assert b"Humor" in response.content
    assert b"Evacua\xc3\xa7\xc3\xa3o" not in response.content


@pytest.mark.django_db
def test_diary_daily_admin_without_teacher_profile_saves_whole_class(client, user):
    class_obj = _class(user)
    first = _student(user)
    second = _student(user, "DIARY-002")
    _enroll(user, class_obj, first)
    _enroll(user, class_obj, second)
    client.force_login(user)

    response = client.post(reverse("diary_daily"), _daily_post(class_obj, [first, second]))

    assert response.status_code == 302
    assert DailyDiary.objects.filter(class_obj=class_obj).count() == 2
    assert not DailyDiary.objects.exclude(teacher=None).exists()


@pytest.mark.django_db
def test_diary_daily_invalid_student_keeps_card_and_rolls_back(client, user):
    class_obj = _class(user)
    first = _student(user)
    second = _student(user, "DIARY-002")
    _enroll(user, class_obj, first)
    _enroll(user, class_obj, second)
    client.force_login(user)

    response = client.post(
        reverse("diary_daily"),
        _daily_post(class_obj, [first, second], missing_answer=True),
    )

    assert response.status_code == 200
    assert b"Este campo \xc3\xa9 obrigat\xc3\xb3rio" in response.content
    assert b"sm-diary-row-has-errors" in response.content
    assert f'name="student-{second.pk}-answer_'.encode() in response.content
    assert DailyDiary.objects.count() == 0


@pytest.mark.django_db
def test_diary_daily_invalid_notes_keeps_error_in_student_row(client, user):
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    client.force_login(user)

    response = client.post(
        reverse("diary_daily"),
        _daily_post(class_obj, [student], notes="x" * 1001),
    )

    assert response.status_code == 200
    assert b"1000 caracteres" in response.content
    assert b"sm-diary-row-has-errors" in response.content
    assert DailyDiary.objects.count() == 0


@pytest.mark.django_db
def test_diary_daily_htmx_replaces_only_roster_card(client, user):
    class_obj = _class(user)
    student = _student(user)
    _enroll(user, class_obj, student)
    client.force_login(user)

    response = client.post(
        reverse("diary_daily"),
        _daily_post(class_obj, [student]),
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Agenda salva com sucesso" in response.content
    assert b"diary-roster-card" in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_diary_daily_teacher_sees_only_linked_class(client, user):
    teacher = _teacher(user)
    linked = _class(user, teacher)
    unlinked = _class(user)
    client.force_login(teacher.user)

    response = client.get(reverse("diary_daily"))

    assert response.status_code == 200
    assert linked.name.encode() in response.content
    assert unlinked.name.encode() not in response.content


@pytest.mark.django_db
def test_diary_configuration_lists_catalog_and_create_action(client, user):
    client.force_login(user)

    response = client.get(reverse("diary_configuration"))

    assert response.status_code == 200
    assert b"Aspectos da rotina" in response.content
    assert b"diary-categories-table" in response.content
    assert b"Humor" in response.content
    assert b"Descanso" in response.content
    assert b"Evacua\xc3\xa7\xc3\xa3o" in response.content
    assert b"Participa\xc3\xa7\xc3\xa3o" in response.content
    assert b"NOVO" in response.content


@pytest.mark.django_db
def test_diary_aspect_create_starts_inactive_and_redirects_to_detail(client, user):
    client.force_login(user)
    form_response = client.get(reverse("diary_aspect_create"))

    response = client.post(
        reverse("diary_aspect_create"),
        {"name": "Hidratação", "display_order": 5, "is_required": "on"},
    )

    aspect = DiaryCategory.objects.get(name="Hidratação")
    assert form_response.status_code == 200
    assert b'value="5"' in form_response.content
    assert response.status_code == 302
    assert response.url == reverse("diary_aspect_detail", args=[aspect.pk])
    assert aspect.code is None
    assert aspect.is_enabled is False
    assert aspect.is_required is True


@pytest.mark.django_db
def test_diary_aspect_and_option_edit_replace_only_their_cards(client, user):
    from student_diary.models import DiaryOption

    client.force_login(user)
    aspect = DiaryCategory.objects.get(code=DiaryCategory.Aspect.MOOD)
    option = DiaryOption.objects.get(code=DiaryOption.FixedCode.MOOD_HAPPY)

    aspect_response = client.post(
        reverse("diary_aspect_edit", args=[aspect.pk]),
        {
            "name": "Estado emocional",
            "display_order": 1,
            "is_required": "on",
            "version": aspect.version,
        },
        HTTP_HX_REQUEST="true",
    )
    option_response = client.post(
        reverse("diary_option_edit", args=[aspect.pk, option.pk]),
        {"label": "Muito alegre", "display_order": 1, "version": option.version},
        HTTP_HX_REQUEST="true",
    )

    aspect.refresh_from_db()
    option.refresh_from_db()
    assert aspect_response.status_code == 200
    assert b"diary-category-information-card" in aspect_response.content
    assert b"<html" not in aspect_response.content
    assert aspect.name == "Estado emocional"
    assert option_response.status_code == 200
    assert b"diary-options-card" in option_response.content
    assert b"<html" not in option_response.content
    assert option.label == "Muito alegre"


@pytest.mark.django_db
def test_diary_option_create_and_last_option_rule_stay_inside_card(client, user):
    from student_diary.services import StudentDiaryService

    service = StudentDiaryService(user=user)
    aspect = service.create_routine_aspect({"name": "Hidratação", "display_order": 5})
    client.force_login(user)

    created_response = client.post(
        reverse("diary_option_create", args=[aspect.pk]),
        {"label": "Bebeu bem", "display_order": 1},
        HTTP_HX_REQUEST="true",
    )
    option = aspect.options.get()
    aspect = service.set_routine_aspect_enabled(aspect.pk, True, aspect.version)
    blocked_response = client.post(
        reverse("diary_option_toggle", args=[aspect.pk, option.pk]),
        {"version": option.version},
        HTTP_HX_REQUEST="true",
    )

    option.refresh_from_db()
    assert created_response.status_code == 200
    assert b"diary-options-card" in created_response.content
    assert b"<html" not in created_response.content
    assert blocked_response.status_code == 200
    assert b"precisa manter ao menos uma op" in blocked_response.content
    assert b"<html" not in blocked_response.content
    assert option.is_enabled is True


@pytest.mark.django_db
def test_diary_aspect_without_option_cannot_be_enabled_from_card(client, user):
    from student_diary.services import StudentDiaryService

    aspect = StudentDiaryService(user=user).create_routine_aspect(
        {"name": "Hidratação", "display_order": 5}
    )
    client.force_login(user)

    response = client.post(
        reverse("diary_aspect_toggle", args=[aspect.pk]),
        {"is_enabled": "on", "version": aspect.version},
        HTTP_HX_REQUEST="true",
    )

    aspect.refresh_from_db()
    assert response.status_code == 200
    assert b"Cadastre ao menos uma op" in response.content
    assert b"<html" not in response.content
    assert aspect.is_enabled is False


@pytest.mark.django_db
def test_diary_configuration_htmx_returns_only_table(client, user):
    client.force_login(user)

    response = client.get(
        reverse("diary_configuration"),
        {"q": "Humor", "sort": "-name"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Humor" in response.content
    assert b"Descanso" not in response.content
    assert b"<html" not in response.content


@pytest.mark.django_db
def test_diary_aspect_detail_and_toggle_replace_information_card(client, user):
    client.force_login(user)
    aspect = DiaryCategory.objects.get(code=DiaryCategory.Aspect.MOOD)

    detail = client.get(reverse("diary_aspect_detail", args=[aspect.pk]))
    toggle = client.post(
        reverse("diary_aspect_toggle", args=[aspect.pk]),
        {"version": aspect.version},
        HTTP_HX_REQUEST="true",
    )
    aspect.refresh_from_db()

    assert detail.status_code == 200
    assert b"col-12 col-xl-5" in detail.content
    assert b"Alegre" in detail.content
    assert toggle.status_code == 200
    assert b"diary-category-information-card" in toggle.content
    assert b"<html" not in toggle.content
    assert not aspect.is_enabled


@pytest.mark.django_db
def test_diary_configuration_is_forbidden_to_teacher(client, user):
    teacher = _teacher(user)
    client.force_login(teacher.user)

    response = client.get(reverse("diary_configuration"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_secretary_can_configure_aspects_without_accessing_agenda(client):
    secretary = _user_for_role("SECRETARY", "secretary-diary-configuration@test.com")
    aspect = DiaryCategory.objects.get(code=DiaryCategory.Aspect.MOOD)
    client.force_login(secretary)

    configuration = client.get(reverse("diary_configuration"))
    toggle = client.post(
        reverse("diary_aspect_toggle", args=[aspect.pk]),
        {"version": aspect.version},
        HTTP_HX_REQUEST="true",
    )
    daily = client.get(reverse("diary_daily"))
    aspect.refresh_from_db()

    assert configuration.status_code == 200
    assert toggle.status_code == 200
    assert aspect.is_enabled is False
    assert daily.status_code == 403


@pytest.mark.django_db
def test_guardian_cannot_configure_aspects(client):
    guardian = _user_for_role("GUARDIAN", "guardian-diary-configuration@test.com")
    client.force_login(guardian)

    assert client.get(reverse("diary_configuration")).status_code == 403


@pytest.mark.django_db
def test_view_only_diary_configuration_hides_edit_control(client):
    from core.models import RoleModuleAccess

    secretary = _user_for_role("SECRETARY", "secretary-diary-view-only@test.com")
    RoleModuleAccess.objects.filter(
        role=secretary.role,
        module_key="diary_configuration",
    ).update(can_view=True, can_create=False, can_edit=False)
    aspect = DiaryCategory.objects.get(code=DiaryCategory.Aspect.MOOD)
    client.force_login(secretary)

    detail = client.get(reverse("diary_aspect_detail", args=[aspect.pk]))
    toggle = client.get(reverse("diary_aspect_toggle", args=[aspect.pk]))

    assert detail.status_code == 200
    assert b"Alterar disponibilidade" not in detail.content
    assert b"Adicionar op" not in detail.content
    assert toggle.status_code == 403

    configuration = client.get(reverse("diary_configuration"))
    assert b"NOVO" not in configuration.content


@pytest.mark.django_db
def test_diary_student_history_preserves_saved_and_empty_history(client, user):
    teacher = _teacher(user)
    class_obj = _class(user, teacher)
    saved_student = _student(user)
    empty_student = _student(user, "DIARY-EMPTY")
    _enroll(user, class_obj, saved_student)
    from student_diary.services import StudentDiaryService
    from student_diary.tests.test_services import _payload

    StudentDiaryService(user=teacher.user).save_daily_diaries(
        class_obj.pk,
        dt.date(2026, 7, 12),
        {str(saved_student.pk): _payload(notes="Histórico")},
    )
    client.force_login(user)

    saved_response = client.get(reverse("diary_student_history", args=[saved_student.pk]))
    empty_response = client.get(reverse("diary_student_history", args=[empty_student.pk]))

    assert saved_response.status_code == 200
    assert b"Hist\xc3\xb3rico" in saved_response.content
    assert empty_response.status_code == 200
    assert b"Nenhum registro" in empty_response.content


@pytest.mark.django_db
def test_diary_student_history_limits_guardian_to_linked_student(client, user):
    role, _ = Role.objects.get_or_create(name=Role.Name.GUARDIAN)
    guardian_user = CustomUser.objects.create_user(
        email="guardian-diary@test.com", password="Senha123", role=role
    )
    guardian = Guardian.objects.create(
        user=guardian_user,
        first_name="Responsável",
        created_by=user,
        updated_by=user,
    )
    linked = _student(user, "DIARY-LINKED")
    unrelated = _student(user, "DIARY-UNRELATED")
    StudentGuardian.objects.create(
        student=linked,
        guardian=guardian,
        created_by=user,
        updated_by=user,
    )
    client.force_login(guardian_user)

    linked_response = client.get(reverse("diary_student_history", args=[linked.pk]))
    unrelated_response = client.get(reverse("diary_student_history", args=[unrelated.pk]))

    assert linked_response.status_code == 200
    assert unrelated_response.status_code == 403
