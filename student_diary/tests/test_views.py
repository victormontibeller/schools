"""Testes HTTP da Agenda escolar."""

import datetime as dt

import pytest
from django.urls import reverse

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


def _daily_post(class_obj, students, *, missing_answer=False):
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
        data[f"{prefix}-notes"] = "Registro pela tela"
    return data


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
    assert b"diary-roster-card" in response.content
    assert reverse("diary_student_history", args=[student.pk]).encode() in response.content
    assert b"Caf\xc3\xa9 da manh\xc3\xa3" in response.content
    assert b"N\xc3\xa3o estava presente" in response.content
    assert response.content.count(b"Salvar Agenda") == 1


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
    assert f"student-editor-{second.pk}".encode() in response.content
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
def test_diary_configuration_lists_only_four_fixed_aspects(client, user):
    client.force_login(user)

    response = client.get(reverse("diary_configuration"))

    assert response.status_code == 200
    assert b"Aspectos da rotina" in response.content
    assert b"diary-categories-table" in response.content
    assert b"Humor" in response.content
    assert b"Descanso" in response.content
    assert b"Evacua\xc3\xa7\xc3\xa3o" in response.content
    assert b"Participa\xc3\xa7\xc3\xa3o" in response.content
    assert b"Nova categoria" not in response.content


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
        {},
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
