"""Regressão geométrica determinística dos shells canônicos."""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode, urlparse

import pytest
from django.conf import settings
from django.urls import reverse
from playwright.sync_api import Page, expect

from activities.models import Activity, ActivitySubmission
from agenda.models import Schedule, TimeSlot
from attendance.services import AttendanceService
from base.tests.factories import RoomFactory, StudentFactory
from classes.models import Class, Enrollment
from enrollments.models import EnrollmentApplication
from enrollments.services import EnrollmentApplicationService
from financeiro.models import PaymentRecord
from financeiro.services import FinanceService
from student_diary.tests.test_services import _class, _enroll, _student
from students.models import Student
from teachers.models import Subject, Teacher

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@dataclass(frozen=True, slots=True)
class Screen:
    name: str
    path: str
    scroller: str
    context: str
    footer: str | None = None
    diary_dropdown: bool = False
    workspace_5_7: bool = False


VIEWPORTS = (
    (1280, 720, 30),
    (1280, 480, 30),
    (390, 844, 20),
)


@pytest.fixture()
def canonical_screens(user) -> tuple[Screen, ...]:
    RoomFactory.create_batch(60, created_by=user, updated_by=user)
    for index in range(55):
        Class.objects.create(
            name=f"Turma de Grade Visual {index:03d}",
            grade=Class.Grade.ELEMENTARY_1,
            education_stage=Class.EducationStage.ELEMENTARY_I,
            shift=Class.Shift.MORNING,
            academic_year=2026,
            created_by=user,
            updated_by=user,
        )

    diary_class = _class(user)
    diary_class.name = "Educação Infantil — Turma Integral com nome deliberadamente longo"
    diary_class.save(update_fields=["name"])
    for index in range(55):
        student = _student(user, f"UI-DIARY-{index:03d}")
        _enroll(user, diary_class, student)

    attendance_class = Class.objects.create(
        name="5º Ano — Turma de validação visual",
        grade=Class.Grade.ELEMENTARY_5,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    for enrollment_student in StudentFactory.create_batch(
        20,
        created_by=user,
        updated_by=user,
    ):
        EnrollmentApplicationService(user=user).create_application(
            {
                "student_id": enrollment_student.pk,
                "target_class_id": attendance_class.pk,
                "application_type": EnrollmentApplication.ApplicationType.NEW,
            }
        )
    for index in range(55):
        student = Student.objects.create(
            first_name="Aluno",
            last_name=f"Frequência {index:03d}",
            birth_date=dt.date(2015, 1, 1),
            enrollment_number=f"UI-ATT-{index:03d}",
            created_by=user,
            updated_by=user,
        )
        Enrollment.objects.create(
            student=student,
            class_obj=attendance_class,
            academic_year=attendance_class.academic_year,
            enrollment_date=dt.date(2026, 1, 20),
            status=Enrollment.Status.ACTIVE,
            created_by=user,
            updated_by=user,
        )

    activity_subject = Subject.objects.create(
        name=("Avaliação visual de leitura compartilhada e interpretação com título " * 3).strip(),
        code="UI-ACT",
        created_by=user,
        updated_by=user,
    )
    activity_teacher = Teacher.objects.create(
        user=user,
        registration_number="UI-ACT-001",
        created_by=user,
        updated_by=user,
    )
    activity_teacher.subjects.add(activity_subject)
    attendance_slot = TimeSlot.objects.create(
        start_time=dt.time(8),
        end_time=dt.time(9),
        slot_number=1,
        shift=TimeSlot.Shift.MORNING,
        created_by=user,
        updated_by=user,
    )
    slot_start = dt.datetime.combine(dt.date(2026, 1, 1), dt.time(12))
    for number in range(2, 22):
        start = slot_start + dt.timedelta(minutes=20 * (number - 2))
        TimeSlot.objects.create(
            start_time=start.time(),
            end_time=(start + dt.timedelta(minutes=20)).time(),
            slot_number=number,
            shift=TimeSlot.Shift.MORNING,
            created_by=user,
            updated_by=user,
        )
    Schedule.objects.create(
        class_obj=attendance_class,
        subject=activity_subject,
        teacher=activity_teacher,
        time_slot=attendance_slot,
        day_of_week=Schedule.Day.MON,
        valid_from=dt.date(2026, 1, 1),
        created_by=user,
        updated_by=user,
    )
    attendance_record = AttendanceService(user=user).open_attendance(
        {
            "class_id": attendance_class.pk,
            "subject_id": activity_subject.pk,
            "teacher_id": activity_teacher.pk,
            "date": dt.date(2026, 7, 20),
            "lesson_number": 2,
            "lesson_content": (
                (
                    "Leitura compartilhada de uma crônica, identificação dos elementos "
                    "narrativos, interpretação das ideias principais e produção coletiva de "
                    "um novo desfecho com revisão ortográfica orientada."
                )
                + " "
            )
            * 6,
            "notes": (
                (
                    "Acompanhar a participação da turma, reservar apoio individual aos alunos "
                    "que apresentarem dificuldade de leitura e retomar os combinados no "
                    "encerramento."
                )
                + " "
            )
            * 5,
        }
    )
    activity = Activity.objects.create(
        class_obj=attendance_class,
        subject=activity_subject,
        teacher=activity_teacher,
        title="Atividade de lançamento com título deliberadamente longo",
        due_date=dt.date(2026, 7, 18),
        created_by=user,
        updated_by=user,
    )
    ActivitySubmission.objects.bulk_create(
        [
            ActivitySubmission(
                activity=activity,
                student=student,
                created_by=user,
                updated_by=user,
            )
            for student in Student.objects.filter(enrollments__class_obj=attendance_class)
        ]
    )

    finance_student = _student(user, "UI-FINANCE")
    finance_contract = FinanceService(user=user).create_contract(
        {
            "student_id": finance_student.pk,
            "academic_year": 2026,
            "name": "Contrato para regressão visual financeira",
            "installment_count": 60,
            "installment_value": Decimal("100.00"),
            "due_day": 10,
            "start_competency": dt.date(2026, 1, 1),
        }
    )
    FinanceService(user=user).activate_contract(finance_contract.pk)

    diary_query = urlencode({"class_id": diary_class.pk, "date": dt.date(2026, 7, 18).isoformat()})
    return (
        Screen(
            "listagem",
            reverse("rooms_list"),
            "#rooms-table .sm-scroll-region",
            "[data-sm-layout='list'] > .card-header",
        ),
        Screen(
            "matriculas",
            reverse("enrollment_application_list"),
            "#applications-table .sm-scroll-region",
            "[data-sm-layout='list'] > .card-header",
        ),
        Screen(
            "grade_horaria_list",
            reverse("schedule_classes_list"),
            "#schedule-classes-table .sm-scroll-region",
            "[data-sm-layout='list'] > .card-header",
        ),
        Screen(
            "grade_horaria_matriz",
            reverse("schedule_weekly", args=[attendance_class.pk]),
            "#schedule-matrix-workspace .sm-scroll-region",
            "#schedule-matrix-workspace > .card-header",
        ),
        Screen(
            "acessos",
            reverse("access_settings"),
            "#access-matrix-card .sm-scroll-region",
            "#access-matrix-card > .card-header",
            "#access-matrix-card > form > .card-footer",
        ),
        Screen(
            "agenda",
            f"{reverse('diary_daily')}?{diary_query}",
            "#diary-workspace-card .sm-scroll-region",
            ".sm-diary-context-bar",
            "#diary-roster-form > .card-footer",
            diary_dropdown=True,
        ),
        Screen(
            "frequencia",
            reverse("class_attendance_summary", args=[attendance_class.pk]),
            ".sm-detail-table-card .sm-scroll-region",
            ".sm-detail-table-card > .card-header",
        ),
        Screen(
            "attendance_record_fill",
            reverse("attendance_record_fill", args=[attendance_record.pk]),
            "#attendance-fill-card .sm-scroll-region",
            "#attendance-fill-card > form > .card-header",
            "#attendance-fill-card > .card-footer",
            workspace_5_7=True,
        ),
        Screen(
            "notas",
            reverse("activity_detail", args=[activity.pk]),
            "#activity-score-card .sm-scroll-region",
            "#activity-score-card > form > .card-header",
            "#activity-score-card > .card-footer",
            workspace_5_7=True,
        ),
        Screen(
            "financeiro",
            reverse("billing_list"),
            "#billings-table .sm-scroll-region",
            "[data-sm-layout='list'] > .card-header",
        ),
    )


def _authenticate(page: Page, client, user, live_server) -> None:
    if str(client.session.get("_auth_user_id", "")) != str(user.pk):
        client.force_login(user)
    if not getattr(page, "_sm_notifications_routed", False):
        page.route(
            "**/notifications/**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body="<div></div>",
            ),
        )
        page._sm_notifications_routed = True
    cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    hostname = urlparse(live_server.url).hostname
    assert hostname is not None
    page.context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": cookie.value,
                "domain": hostname,
                "path": "/",
                "sameSite": "Lax",
            }
        ]
    )


def _geometry(page: Page, screen: Screen) -> dict:
    return page.evaluate(
        """
        ({scrollerSelector, contextSelector, footerSelector}) => {
            const content = document.querySelector('.nxl-content');
            const card = document.querySelector('[data-sm-layout]') ||
                document.querySelector('.sm-detail-table-card');
            const header = document.querySelector('.sm-page-header');
            const context = document.querySelector(contextSelector);
            const scroller = document.querySelector(scrollerSelector);
            const firstHeader = scroller.querySelector('thead tr > :first-child');
            const firstBody = scroller.querySelector(
                'tbody tr:not([hidden]):not(.sm-access-department-row) > :first-child'
            );
            const firstStatus = scroller.querySelector(
                'tbody tr:not([hidden]) > .sm-attendance-status-column'
            );
            const footer = footerSelector ? document.querySelector(footerSelector) : null;
            const rect = (element) => element ? element.getBoundingClientRect() : null;
            return {
                card: rect(card),
                content: rect(content),
                header: rect(header),
                context: rect(context),
                scroller: rect(scroller),
                firstHeader: rect(firstHeader),
                firstBody: rect(firstBody),
                firstStatus: rect(firstStatus),
                firstBodyPosition: getComputedStyle(firstBody).position,
                firstBodyLeft: getComputedStyle(firstBody).left,
                firstBodyPaddingLeft: parseFloat(getComputedStyle(firstBody).paddingLeft),
                contextPaddingLeft: parseFloat(getComputedStyle(context).paddingLeft),
                scrollerOverflow: getComputedStyle(scroller).overflow,
                footer: rect(footer),
                scrollTop: scroller.scrollTop,
                scrollLeft: scroller.scrollLeft,
                scrollHeight: scroller.scrollHeight,
                scrollWidth: scroller.scrollWidth,
                clientHeight: scroller.clientHeight,
                clientWidth: scroller.clientWidth,
                windowScrollY: window.scrollY,
                documentWidth: document.documentElement.scrollWidth,
                documentHeight: document.documentElement.scrollHeight,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
            };
        }
        """,
        {
            "scrollerSelector": screen.scroller,
            "contextSelector": screen.context,
            "footerSelector": screen.footer,
        },
    )


def _assert_geometry(page: Page, screen: Screen, gutter: int) -> None:
    before = _geometry(page, screen)
    uses_stacked_mobile_flow = (
        screen.name in {"attendance_record_fill", "notas"} and before["viewportWidth"] < 1200
    )
    if screen.workspace_5_7:
        assert before["card"]["left"] >= before["content"]["left"] + gutter - 1
        assert before["card"]["right"] <= before["content"]["right"] - gutter + 1
    else:
        assert abs(before["card"]["left"] - before["content"]["left"] - gutter) <= 1
    assert before["documentWidth"] <= before["viewportWidth"] + 1
    assert before["documentHeight"] <= before["viewportHeight"] + 1
    if not uses_stacked_mobile_flow:
        assert before["scrollHeight"] > before["clientHeight"], (
            screen.name,
            before["viewportWidth"],
            before["viewportHeight"],
        )
    assert before["firstBodyPaddingLeft"] == 30
    if screen.name in {"agenda", "attendance_record_fill"}:
        assert before["contextPaddingLeft"] == 30
    if screen.name == "attendance_record_fill" and before["viewportWidth"] <= 390:
        assert before["firstBody"]["width"] <= 140.5
        assert before["firstStatus"]["right"] <= before["scroller"]["right"] + 1

    page.locator(screen.scroller).evaluate(
        """element => {
            element.scrollTop = element.scrollHeight;
            element.scrollLeft = element.scrollWidth;
        }"""
    )
    after = _geometry(page, screen)

    if not uses_stacked_mobile_flow:
        assert after["scrollTop"] > 0
    assert after["windowScrollY"] == before["windowScrollY"] == 0
    assert abs(after["header"]["top"] - before["header"]["top"]) <= 1
    assert abs(after["context"]["top"] - before["context"]["top"]) <= 1
    assert abs(after["firstHeader"]["top"] - after["scroller"]["top"]) <= 2
    if after["scrollWidth"] > after["clientWidth"]:
        assert abs(after["firstBody"]["left"] - after["scroller"]["left"]) <= 2, (
            screen.name,
            after["firstBodyPosition"],
            after["firstBodyLeft"],
            after["scrollerOverflow"],
            after["firstBody"],
            after["scroller"],
        )
    if after["footer"] and not uses_stacked_mobile_flow:
        assert after["footer"]["bottom"] <= after["viewportHeight"] + 1

    if not uses_stacked_mobile_flow:
        scroller = page.locator(screen.scroller)
        scroller.evaluate("element => { element.scrollTop = 0; }")
        scroller.focus()
        expect(scroller).to_be_focused()
        scroller.press("PageDown")
        page.wait_for_function(
            "selector => document.querySelector(selector).scrollTop > 0",
            arg=screen.scroller,
        )


def _assert_access_matrix_layout(page: Page) -> None:
    has_full_selector = page.evaluate(
        """() => {
            const cell = Array.from(document.querySelectorAll('[data-access-cell]')).find(
                candidate => candidate.querySelector(
                    ".sm-access-action-input[value='deactivate']"
                )
            );
            if (!cell) {
                return false;
            }
            cell.querySelectorAll('.sm-access-action-input').forEach(input => {
                if (!input.checked) {
                    input.checked = true;
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                }
            });
            return true;
        }"""
    )
    assert has_full_selector is True

    metrics = page.locator("#access-matrix-card .sm-scroll-region").evaluate(
        """scroller => {
            const table = scroller.querySelector('.sm-access-table');
            const moduleHeader = table.querySelector('.sm-access-module-column');
            const roleHeaders = Array.from(table.querySelectorAll('.sm-access-role-column'));
            const selectors = Array.from(table.querySelectorAll('.sm-access-selector'));
            const fullSelector = selectors.find(
                selector => selector.querySelectorAll('.sm-access-action-badge').length === 4
            );
            const width = element => element.getBoundingClientRect().width;
            return {
                viewportWidth: innerWidth,
                scrollerClientWidth: scroller.clientWidth,
                tableWidth: width(table),
                moduleWidth: width(moduleHeader),
                roleWidths: roleHeaders.map(width),
                selectorWidths: selectors.map(width),
                fullSelectorFits: fullSelector
                    ? fullSelector.scrollWidth <= fullSelector.clientWidth + 1
                    : false,
                scrollsHorizontally: scroller.scrollWidth > scroller.clientWidth,
                scrollsVertically: scroller.scrollHeight > scroller.clientHeight,
                documentWidth: document.documentElement.scrollWidth,
            };
        }"""
    )

    assert metrics["scrollsVertically"] is True
    assert metrics["documentWidth"] <= metrics["viewportWidth"] + 1
    assert metrics["fullSelectorFits"] is True
    assert min(metrics["roleWidths"]) >= 219
    assert min(metrics["selectorWidths"]) >= 195
    if metrics["viewportWidth"] <= 767:
        assert 174 <= metrics["moduleWidth"] <= 176
        minimum_table_width = 1275
    else:
        assert 279 <= metrics["moduleWidth"] <= 281
        minimum_table_width = 1380
    expected_table_width = max(minimum_table_width, metrics["scrollerClientWidth"])
    assert abs(metrics["tableWidth"] - expected_table_width) <= 1
    assert metrics["scrollsHorizontally"] is (metrics["scrollerClientWidth"] < minimum_table_width)

    scroller = page.locator("#access-matrix-card .sm-scroll-region")
    scroller.evaluate(
        """element => {
            element.scrollTop = element.scrollHeight;
            element.scrollLeft = element.scrollWidth;
        }"""
    )
    sticky = scroller.evaluate(
        """element => {
            const rect = target => target.getBoundingClientRect();
            return {
                scroller: rect(element),
                firstHeader: rect(element.querySelector('thead tr > :first-child')),
                firstBody: rect(element.querySelector(
                    'tbody tr:not([hidden]):not(.sm-access-department-row) > :first-child'
                )),
            };
        }"""
    )
    assert abs(sticky["firstHeader"]["top"] - sticky["scroller"]["top"]) <= 2
    assert abs(sticky["firstBody"]["left"] - sticky["scroller"]["left"]) <= 2

    scroller.evaluate("element => { element.scrollTop = 0; element.scrollLeft = 0; }")
    scroller.focus()
    expect(scroller).to_be_focused()
    scroller.press("PageDown")
    page.wait_for_function(
        "selector => document.querySelector(selector).scrollTop > 0",
        arg="#access-matrix-card .sm-scroll-region",
    )


def _assert_last_diary_dropdown(page: Page) -> None:
    scroller = page.locator("#diary-workspace-card .sm-scroll-region")
    scroller.evaluate("element => { element.scrollTop = element.scrollHeight; }")
    button = page.locator(".sm-diary-notes-column .sm-diary-selector").last
    button.click()
    state = page.evaluate(
        """() => ({
            expanded: document.querySelectorAll(
                '.sm-diary-notes-column .sm-diary-selector'
            )[document.querySelectorAll(
                '.sm-diary-notes-column .sm-diary-selector'
            ).length - 1].getAttribute('aria-expanded'),
            bootstrap: typeof window.bootstrap,
            shownMenus: document.querySelectorAll('.sm-diary-notes-menu.show').length,
            bodyMenus: document.querySelectorAll('body > .sm-diary-notes-menu').length,
        })"""
    )
    assert state["expanded"] == "true", state
    menu = page.locator(".sm-diary-notes-menu.show").last
    expect(menu).to_be_visible()
    assert menu.evaluate("element => element.parentElement === document.body")
    box = menu.bounding_box()
    assert box is not None
    viewport = page.viewport_size
    assert viewport is not None
    assert box["x"] >= -1
    assert box["y"] >= -1
    assert box["x"] + box["width"] <= viewport["width"] + 1
    assert box["y"] + box["height"] <= viewport["height"] + 1
    page.keyboard.press("Escape")


def _assert_attendance_workspace(page: Page) -> None:
    workspace = page.locator("#attendance-workspace")
    information_column = workspace.locator(".col-xl-5")
    operational_column = workspace.locator(".col-xl-7")
    information = page.locator("#attendance-information-card")
    information_scroller = information.locator(".sm-attendance-information-scroll")
    expect(information).to_contain_text("revisão ortográfica orientada")

    workspace_box = workspace.bounding_box()
    information_box = information_column.bounding_box()
    operational_box = operational_column.bounding_box()
    assert workspace_box is not None
    assert information_box is not None
    assert operational_box is not None

    if page.evaluate("innerWidth") >= 1200:
        assert abs(information_box["y"] - operational_box["y"]) <= 1
        assert information_box["width"] < operational_box["width"]
        assert abs(information_box["width"] * 7 - operational_box["width"] * 5) <= 12
    else:
        assert information_box["y"] < operational_box["y"]
        assert abs(information_box["x"] - operational_box["x"]) <= 1
        assert workspace.evaluate("element => element.scrollHeight > element.clientHeight")

    if information_scroller.evaluate("element => element.scrollHeight > element.clientHeight"):
        information_scroller.evaluate("element => { element.scrollTop = 0; }")
        information_scroller.focus()
        expect(information_scroller).to_be_focused()
        information_scroller.press("PageDown")
        page.wait_for_function(
            "selector => document.querySelector(selector).scrollTop > 0",
            arg=".sm-attendance-information-scroll",
        )


def _assert_attendance_dropdown(page: Page) -> None:
    old_card = page.locator("#attendance-fill-card").element_handle()
    assert old_card is not None
    page.locator("button[form='attendance-fill-form']").click()
    page.wait_for_function("element => !element.isConnected", arg=old_card)

    card = page.locator("#attendance-fill-card")
    expect(card.locator("[role='status']")).to_contain_text("Chamada salva com sucesso")
    fallback = card.locator("[data-attendance-fallback]").last
    enhanced = card.locator("[data-attendance-enhanced]").last
    expect(fallback).to_be_hidden()
    expect(fallback.locator("input, select, textarea")).to_be_disabled()
    expect(enhanced).to_be_visible()
    expect(enhanced.locator("input, select, textarea")).to_be_enabled()

    page.locator("#attendance-fill-card .sm-scroll-region").evaluate(
        "element => { element.scrollLeft = 0; }"
    )
    button = page.locator("[data-attendance-status] .sm-attendance-selector").last
    expect(button).to_have_attribute("data-sm-floating-initialized", "true")
    button.scroll_into_view_if_needed()
    button.focus()
    expect(button).to_be_focused()
    button.press("ArrowDown")
    expect(button).to_have_attribute("aria-expanded", "true")

    menu = page.locator("body > .sm-attendance-dropdown-menu").last
    expect(menu).to_be_visible()
    assert menu.evaluate("element => element.parentElement === document.body")
    present = menu.locator('input[value="PRESENT"]')
    expect(present).to_be_focused()
    present.press("Shift+Tab")
    expect(button).to_have_attribute("aria-expanded", "false")
    expect(button).to_be_focused()

    button.press("ArrowDown")
    expect(present).to_be_focused()
    present.press("ArrowDown")
    expect(button.locator("[data-attendance-status-summary]")).to_have_text("Ausente")
    expect(button).to_have_attribute("aria-expanded", "false")
    expect(button).to_be_focused()

    note_button = page.locator("[data-attendance-note] .sm-attendance-selector").last
    button.press("ArrowDown")
    expect(present).to_be_focused()
    present.press("Tab")
    expect(button).to_have_attribute("aria-expanded", "false")
    expect(note_button).to_be_focused()

    note_button.scroll_into_view_if_needed()
    note_button.press("ArrowDown")
    expect(note_button).to_have_attribute("aria-expanded", "true")
    note_input = page.locator("body > .sm-attendance-note-menu .sm-attendance-note-input").last
    expect(note_input).to_be_focused()
    expect(note_input).to_have_attribute("rows", "6")
    expect(note_input).to_have_attribute("maxlength", "250")
    improve_button = page.locator(
        "body > .sm-attendance-note-menu button[aria-disabled='true']"
    ).last
    expect(improve_button).to_be_disabled()
    expect(improve_button).to_contain_text("Melhorar com IA")
    expect(improve_button).to_contain_text("Em breve")
    note_input.press("Tab")
    expect(note_button).to_have_attribute("aria-expanded", "false")
    footer_cancel = page.locator("#attendance-fill-card > .card-footer a").first
    expect(footer_cancel).to_be_focused()

    note_button.focus()
    note_button.press("ArrowDown")
    expect(note_input).to_be_focused()
    note_input.press("Escape")
    expect(note_button).to_have_attribute("aria-expanded", "false")
    expect(note_button).to_be_focused()


def _assert_activity_score_observation(page: Page) -> None:
    card = page.locator("#activity-score-card")
    fallback = card.locator("[data-activity-score-feedback-fallback]").first
    enhanced = card.locator("[data-activity-score-feedback-enhanced]").first
    selector = enhanced.locator(".sm-activity-score-feedback-selector")

    expect(fallback).to_be_hidden()
    expect(fallback.locator("textarea")).to_be_disabled()
    expect(enhanced).to_be_visible()
    expect(enhanced.locator("textarea").first).to_be_enabled()
    expect(selector).to_have_attribute("data-sm-floating-initialized", "true")

    widths = card.locator(".sm-activity-score-table").evaluate(
        """table => {
            const width = selector => table.querySelector(selector).getBoundingClientRect().width;
            return {
                viewport: innerWidth,
                student: width('thead .sm-activity-score-student-column'),
                enrollment: width('thead .sm-activity-score-enrollment-column'),
                score: width('thead .sm-activity-score-value-column'),
                observation: width('thead .sm-activity-score-feedback-column'),
            };
        }"""
    )
    assert abs(widths["enrollment"] - 112) <= 1
    assert abs(widths["score"] - 96) <= 1
    assert abs(widths["observation"] - 180) <= 1
    assert widths["student"] >= 220

    selector.focus()
    selector.press("ArrowDown")
    expect(selector).to_have_attribute("aria-expanded", "true")
    menu = page.locator("body > .sm-activity-score-feedback-menu").first
    observation = menu.locator("textarea")
    expect(observation).to_be_focused()
    expect(observation).to_have_attribute("rows", "6")
    improve_button = menu.get_by_role("button", name=re.compile("Melhorar com IA"))
    expect(improve_button).to_be_disabled()
    expect(improve_button).to_contain_text("Em breve")
    observation.press("Escape")
    expect(selector).to_have_attribute("aria-expanded", "false")
    expect(selector).to_be_focused()


def _assert_schedule_cell_modal(page: Page) -> None:
    workspace = page.locator("#schedule-matrix-workspace")
    opener = page.locator("[data-sm-schedule-cell-modal]").first
    modal = page.locator("#app-modal-root > #schedule-cell-modal")
    body = modal.locator("#schedule-cell-modal-body")
    workspace_metrics = workspace.evaluate(
        "element => ({height: element.getBoundingClientRect().height, "
        "scrollHeight: element.scrollHeight})"
    )

    expect(modal).to_have_count(1)
    expect(workspace.locator("#schedule-cell-modal")).to_have_count(0)
    expect(opener).not_to_have_attribute("data-bs-toggle", "modal")
    opener.click()
    expect(modal).to_be_visible()
    expect(body.locator("select[name='teacher_id']")).to_be_focused()
    assert (
        workspace.evaluate(
            "element => ({height: element.getBoundingClientRect().height, "
            "scrollHeight: element.scrollHeight})"
        )
        == workspace_metrics
    )

    valid_from = body.locator("input[name='valid_from']")
    valid_from.fill("")
    valid_from.evaluate("element => element.removeAttribute('required')")
    modal.get_by_role("button", name="Salvar").click()
    invalid_field = body.locator(".is-invalid, [aria-invalid='true']").first
    expect(modal).to_be_visible()
    expect(invalid_field).to_be_focused()

    modal.get_by_role("button", name="Cancelar").click()
    expect(modal).to_be_hidden()
    expect(opener).to_be_focused()

    opener.click()
    expect(body.locator("select[name='teacher_id']")).to_be_focused()
    modal.get_by_role("button", name="Cancelar").click()
    expect(modal).to_be_hidden()
    expect(opener).to_be_focused()
    expect(body).to_contain_text("Carregando formulário.")

    opener.click()
    expect(body.locator("select[name='teacher_id']")).to_be_focused()
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    expect(opener).to_be_focused()

    opener.click()
    expect(body.locator("select[name='teacher_id']")).to_be_focused()
    body.locator("input[name='valid_from']").evaluate(
        "element => { element.value = '2026-08-10'; "
        "element.dispatchEvent(new Event('change', {bubbles: true})); }"
    )
    modal.get_by_role("button", name="Salvar").click()
    expect(modal).to_be_hidden()
    expect(page.locator("[data-sm-schedule-cell-modal]").first).to_be_focused()
    expect(body).to_contain_text("Carregando formulário.")
    assert (
        workspace.evaluate(
            "element => ({height: element.getBoundingClientRect().height, "
            "scrollHeight: element.scrollHeight})"
        )
        == workspace_metrics
    )


def _assert_schedule_copy_modal(page: Page) -> None:
    workspace = page.locator("#schedule-matrix-workspace")
    opener = page.locator("[data-sm-schedule-copy-modal]")
    modal = page.locator("#app-modal-root > #schedule-copy-modal")
    body = modal.locator("#schedule-copy-modal-body")
    workspace_metrics = workspace.evaluate(
        "element => ({height: element.getBoundingClientRect().height, "
        "scrollHeight: element.scrollHeight})"
    )

    expect(modal).to_have_count(1)
    expect(workspace.locator("#schedule-copy-modal")).to_have_count(0)
    opener.focus()
    opener.press("Enter")
    expect(modal).to_be_visible()
    expect(body.locator("select[name='source_day']")).to_be_focused()
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    expect(opener).to_be_focused()
    expect(body).to_contain_text("Carregando formulário.")
    assert (
        workspace.evaluate(
            "element => ({height: element.getBoundingClientRect().height, "
            "scrollHeight: element.scrollHeight})"
        )
        == workspace_metrics
    )


def _assert_schedule_matrix_layout(page: Page) -> None:
    workspace = page.locator("#schedule-matrix-workspace")
    header = workspace.locator("> .sm-schedule-matrix-header")
    title = header.locator(".sm-schedule-matrix-title")
    actions = header.locator(".sm-schedule-matrix-actions")
    scroller = workspace.locator(".sm-scroll-region")
    table = scroller.locator(".sm-schedule-matrix")
    day_headers = table.locator("thead th:not(:first-child)")
    subject = table.locator(".sm-schedule-cell-subject").first
    action_group = table.locator(".sm-schedule-cell-actions").first

    expect(title).to_contain_text("Matriz semanal")
    expect(actions.get_by_role("navigation", name="Navegação semanal da grade")).to_be_visible()
    expect(actions.get_by_role("link", name="Copiar dia")).to_be_visible()
    expect(subject).to_have_text(
        "Avaliação visual de leitura compartilhada e interpretação com título " * 3
    )

    header_box = header.bounding_box()
    title_box = title.bounding_box()
    actions_box = actions.bounding_box()
    assert header_box is not None
    assert title_box is not None
    assert actions_box is not None

    if page.evaluate("innerWidth") >= 992:
        assert title_box["x"] < actions_box["x"]
        assert actions_box["x"] + actions_box["width"] <= header_box["x"] + header_box["width"]
        assert scroller.evaluate("element => element.scrollWidth <= element.clientWidth + 1")

        header_widths = day_headers.evaluate_all(
            "elements => elements.map(element => element.getBoundingClientRect().width)"
        )
        assert max(header_widths) - min(header_widths) <= 1

        subject_box = subject.bounding_box()
        action_box = action_group.bounding_box()
        cell_box = action_group.locator("xpath=ancestor::td").bounding_box()
        assert subject_box is not None
        assert action_box is not None
        assert cell_box is not None
        assert subject_box["x"] + subject_box["width"] <= action_box["x"]
        assert action_box["x"] + action_box["width"] <= cell_box["x"] + cell_box["width"]
        assert subject.evaluate("element => element.scrollWidth > element.clientWidth")
    else:
        assert actions_box["y"] > title_box["y"]
        assert scroller.evaluate("element => element.scrollWidth > element.clientWidth")


def _assert_modal_navigation_is_clean(page: Page) -> None:
    expect(page.locator(".modal-backdrop")).to_have_count(0)
    assert (
        page.locator("body").evaluate(
            """body => ({
            modalOpen: body.classList.contains('modal-open'),
            overflow: body.style.overflow,
            paddingRight: body.style.paddingRight,
        })"""
        )
        == {"modalOpen": False, "overflow": "", "paddingRight": ""}
    )


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_list_primary_navigation_preserves_global_shell(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    list_screen = next(
        screen for screen in canonical_screens if screen.name == "grade_horaria_list"
    )
    page.goto(f"{live_server.url}{list_screen.path}")

    navigation = page.locator("#school-navigation")
    primary_link = page.locator(
        "[data-sm-layout='list'] "
        ".sm-sticky-table--first-column tbody tr > td:first-child a[href]"
    ).first
    expect(primary_link).to_have_attribute("hx-boost", "true")
    navigation.evaluate("element => { element.dataset.persistenceMarker = 'preserved'; }")

    primary_link.click()

    expect(page).to_have_url(re.compile(r"/turmas/[^/]+/grade/"))
    expect(
        page.locator("#app-main").get_by_role("heading", name=re.compile("Grade horária"))
    ).to_be_visible()
    expect(navigation).to_have_attribute("data-persistence-marker", "preserved")


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_history_clears_open_schedule_modal_portal(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    schedule_screen = next(
        screen for screen in canonical_screens if screen.name == "grade_horaria_matriz"
    )
    page.goto(f"{live_server.url}{schedule_screen.path}")

    modal = page.locator("#app-modal-root > #schedule-cell-modal")
    copy_modal = page.locator("#app-modal-root > #schedule-copy-modal")
    expect(modal).to_have_count(1)
    expect(copy_modal).to_have_count(1)
    page.locator("[data-sm-schedule-cell-modal]").first.click()
    expect(modal).to_be_visible()

    _authenticate(page, client, user, live_server)
    page.locator(f"#school-navigation a[href='{reverse('dashboard')}']").evaluate(
        "element => element.click()"
    )
    expect(page.locator("#app-main")).to_have_attribute("data-nav-url-name", "dashboard")
    expect(modal).to_have_count(0)
    expect(copy_modal).to_have_count(0)
    _assert_modal_navigation_is_clean(page)
    page.locator("#app-main a[href='/classes/']").first.click(trial=True)

    _authenticate(page, client, user, live_server)
    page.go_back()
    expect(page.locator("#app-main")).to_have_attribute(
        "data-nav-url-name", "schedule_classes_list"
    )
    expect(modal).to_have_count(1)
    expect(copy_modal).to_have_count(1)
    _assert_modal_navigation_is_clean(page)
    page.locator("[data-sm-schedule-cell-modal]").first.click()
    expect(modal).to_be_visible()

    _authenticate(page, client, user, live_server)
    page.go_forward()
    expect(page.locator("#app-main")).to_have_attribute("data-nav-url-name", "dashboard")
    expect(modal).to_have_count(0)
    _assert_modal_navigation_is_clean(page)

    _authenticate(page, client, user, live_server)
    page.go_back()
    expect(modal).to_have_count(1)
    _assert_modal_navigation_is_clean(page)
    page.locator("[data-sm-schedule-cell-modal]").first.click()
    expect(modal).to_be_visible()
    page.locator("#schedule-cell-modal [data-bs-dismiss='modal']").first.click()
    expect(modal).to_be_hidden()


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_schedule_week_navigation_preserves_reference_in_history_and_reload(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    schedule_screen = next(
        screen for screen in canonical_screens if screen.name == "grade_horaria_matriz"
    )
    initial_url = f"{live_server.url}{schedule_screen.path}?as_of=2026-02-02"
    next_url = f"{live_server.url}{schedule_screen.path}?as_of=2026-02-09"
    page.goto(initial_url)

    _authenticate(page, client, user, live_server)
    page.get_by_role("link", name="Próxima semana").click()
    expect(page).to_have_url(next_url)
    expect(page.locator("#schedule-matrix-workspace")).to_contain_text("Segunda (09/02)")

    _authenticate(page, client, user, live_server)
    page.reload()
    expect(page).to_have_url(next_url)
    expect(page.locator("#schedule-matrix-workspace")).to_contain_text("Segunda (09/02)")

    _authenticate(page, client, user, live_server)
    page.go_back()
    expect(page).to_have_url(initial_url)
    expect(page.locator("#schedule-matrix-workspace")).to_contain_text("Segunda (02/02)")


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_schedule_copy_modal_updates_workspace_url_and_focus(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    schedule_screen = next(
        screen for screen in canonical_screens if screen.name == "grade_horaria_matriz"
    )
    page.goto(f"{live_server.url}{schedule_screen.path}?as_of=2026-02-02")

    workspace = page.locator("#schedule-matrix-workspace")
    opener = page.locator("[data-sm-schedule-copy-modal]")
    modal = page.locator("#app-modal-root > #schedule-copy-modal")
    body = modal.locator("#schedule-copy-modal-body")
    workspace_metrics = workspace.evaluate(
        "element => ({height: element.getBoundingClientRect().height, "
        "scrollHeight: element.scrollHeight})"
    )
    original_opener = opener.element_handle()
    assert original_opener is not None
    window_scroll_before_submit = page.evaluate("window.scrollY")

    _authenticate(page, client, user, live_server)
    opener.click()
    expect(modal).to_be_visible()
    body.locator("select[name='source_day']").select_option(Schedule.Day.MON)
    body.locator("select[name='target_day']").select_option(Schedule.Day.TUE)
    body.locator("input[name='as_of']").fill("2026-02-02")
    _authenticate(page, client, user, live_server)
    modal.get_by_role("button", name="Copiar dia").click()

    expect(page).to_have_url(f"{live_server.url}{schedule_screen.path}?as_of=2026-02-02")
    expect(
        page.locator("#schedule-matrix-workspace tbody tr:first-child > td:nth-child(3)")
    ).to_contain_text("Avaliação visual")
    expect(modal).to_be_hidden()
    assert original_opener.evaluate("element => element.isConnected") is False
    expect(page.locator("#schedule-copy-day-trigger")).to_be_focused()
    assert page.evaluate("window.scrollY") == window_scroll_before_submit
    assert (
        workspace.evaluate(
            "element => ({height: element.getBoundingClientRect().height, "
            "scrollHeight: element.scrollHeight})"
        )
        == workspace_metrics
    )


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_primary_screens_follow_geometry_contract(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    for width, height, gutter in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        for screen in canonical_screens:
            _authenticate(page, client, user, live_server)
            page.goto(f"{live_server.url}{screen.path}")
            expect(page.locator(".sm-page-header")).to_be_visible()
            _assert_geometry(page, screen, gutter)
            if screen.diary_dropdown:
                _assert_last_diary_dropdown(page)
            if screen.name == "attendance_record_fill":
                _assert_attendance_workspace(page)
                _assert_attendance_dropdown(page)
            if screen.name == "notas":
                _assert_activity_score_observation(page)
            if screen.name == "grade_horaria_matriz":
                _assert_schedule_matrix_layout(page)
                if (width, height) == VIEWPORTS[0][:2]:
                    _assert_schedule_cell_modal(page)
                    _assert_schedule_copy_modal(page)


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_activity_observation_enhances_after_list_navigation_and_score_swap(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    page.set_viewport_size({"width": 1280, "height": 720})
    activity_screen = next(screen for screen in canonical_screens if screen.name == "notas")
    page.goto(f"{live_server.url}{reverse('activities_list')}")

    navigation = page.locator("#school-navigation")
    navigation.evaluate("element => { element.dataset.persistenceMarker = 'preserved'; }")
    activity_link = page.locator(
        f"[data-sm-layout='list'] tbody a[href='{activity_screen.path}']"
    ).first
    expect(activity_link).to_have_attribute("hx-boost", "true")
    activity_link.click()

    expect(page).to_have_url(re.compile(r"/activities/[^/]+/"))
    expect(navigation).to_have_attribute("data-persistence-marker", "preserved")
    _assert_activity_score_observation(page)

    card = page.locator("#activity-score-card")
    old_card = card.element_handle()
    assert old_card is not None
    score = card.locator(".sm-activity-score-value-column input[type='number']").first
    selector = card.locator(".sm-activity-score-feedback-selector").first
    score.fill("8.5")
    selector.click()
    observation = page.locator("body > .sm-activity-score-feedback-menu textarea").first
    observation.fill("Participou bem da atividade.")
    expect(selector.locator("[data-activity-score-feedback-summary]")).to_have_text(
        "Com observação"
    )
    page.keyboard.press("Escape")
    card.get_by_role("button", name="Salvar rascunho").click()

    page.wait_for_function("element => !element.isConnected", arg=old_card)
    refreshed = page.locator("#activity-score-card")
    expect(refreshed.locator("[role='status']")).to_contain_text("salva com sucesso")
    expect(refreshed.locator("[data-activity-score-feedback-fallback]").first).to_be_hidden()
    expect(refreshed.locator(".sm-activity-score-feedback-selector").first).to_contain_text(
        "Com observação"
    )


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_access_matrix_preserves_readable_columns_and_internal_scroll(
    page: Page,
    client,
    user,
    live_server,
) -> None:
    screen = Screen(
        "acessos",
        reverse("access_settings"),
        "#access-matrix-card .sm-scroll-region",
        "#access-matrix-card > .card-header",
        "#access-matrix-card > form > .card-footer",
    )

    access_viewports = (*VIEWPORTS, (1792, 969, 30))
    for width, height, _gutter in access_viewports:
        page.set_viewport_size({"width": width, "height": height})
        _authenticate(page, client, user, live_server)
        page.goto(f"{live_server.url}{screen.path}")
        expect(page.locator(".sm-page-header")).to_be_visible()
        _assert_access_matrix_layout(page)

    page.set_viewport_size({"width": 1280, "height": 720})
    _authenticate(page, client, user, live_server)
    page.goto(f"{live_server.url}{screen.path}")
    page.locator("#theme-toggle").click()
    expect(page.locator("html")).to_have_class("app-skin-dark")
    _assert_access_matrix_layout(page)


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_reenrollment_workspace_preserves_geometry_keyboard_and_dark_theme(
    page: Page,
    client,
    user,
    live_server,
) -> None:
    source_class = Class.objects.create(
        name="5º Ano — Origem da rematrícula visual",
        grade=Class.Grade.ELEMENTARY_5,
        education_stage=Class.EducationStage.ELEMENTARY_I,
        shift=Class.Shift.MORNING,
        academic_year=2026,
        created_by=user,
        updated_by=user,
    )
    Class.objects.create(
        name="6º Ano — Destino da rematrícula visual",
        grade=Class.Grade.ELEMENTARY_6,
        education_stage=Class.EducationStage.ELEMENTARY_II,
        shift=source_class.shift,
        academic_year=2027,
        created_by=user,
        updated_by=user,
    )
    Enrollment.objects.bulk_create(
        [
            Enrollment(
                student=student,
                class_obj=source_class,
                academic_year=source_class.academic_year,
                enrollment_date=dt.date(2026, 1, 20),
                status=Enrollment.Status.ACTIVE,
                created_by=user,
                updated_by=user,
            )
            for student in StudentFactory.create_batch(
                55,
                created_by=user,
                updated_by=user,
            )
        ]
    )
    _authenticate(page, client, user, live_server)
    screen = Screen(
        "rematricula",
        f"{reverse('reenrollment_batch')}?source_class_id={source_class.pk}",
        "#reenrollment-workspace .sm-scroll-region",
        "#reenrollment-workspace > .card-header",
        "#reenrollment-workspace .card-footer",
    )

    for width, height, gutter in VIEWPORTS:
        _authenticate(page, client, user, live_server)
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{live_server.url}{screen.path}")
        expect(page.locator(".sm-page-header")).to_be_visible()
        _assert_geometry(page, screen, gutter)

    page.set_viewport_size({"width": 1280, "height": 720})
    page.goto(f"{live_server.url}{screen.path}")
    page.locator("#theme-toggle").click()
    expect(page.locator("html")).to_have_class("app-skin-dark")
    _assert_geometry(page, screen, 30)


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_enrollment_detail_preserves_5_7_layout_and_keyboard_focus(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    assert canonical_screens
    application = EnrollmentApplication.objects.order_by("created_at").first()
    assert application is not None

    for width, height, _gutter in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(
            f"{live_server.url}{reverse('enrollment_application_detail', args=[application.pk])}"
        )
        left = page.locator(".main-content > .row > .col-xl-5")
        right = page.locator(".main-content > .row > .col-xl-7")
        left_box = left.bounding_box()
        right_box = right.bounding_box()
        assert left_box is not None
        assert right_box is not None
        assert page.locator("#application-process-card").count() == 1
        assert page.locator("#application-documents-card").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        if width >= 1200:
            assert abs(left_box["y"] - right_box["y"]) <= 1
            assert abs(left_box["width"] * 7 - right_box["width"] * 5) <= 12
        else:
            assert left_box["y"] < right_box["y"]
            assert abs(left_box["x"] - right_box["x"]) <= 1

        submit = page.locator("#application-process-card button[value='submit']")
        submit.focus()
        expect(submit).to_be_focused()


def _assert_document_requirement_form_layout(page: Page, viewport_width: int) -> None:
    workspace = page.locator(".main-content > .row.g-3.align-items-start")
    column = workspace.locator(":scope > .col-12.col-xl-5")
    card = column.locator(":scope > .card")
    grid = card.locator("#primary-form > .row.g-2")
    switches = grid.locator(":scope > .col-12.col-md-6")

    expect(workspace).to_be_visible()
    expect(column).to_be_visible()
    expect(card).to_be_visible()
    expect(grid).to_be_visible()
    expect(switches).to_have_count(2)
    expect(card).to_contain_text(
        "A alteração valerá somente para solicitações abertas depois da configuração."
    )

    workspace_box = workspace.bounding_box()
    column_box = column.bounding_box()
    switch_boxes = switches.evaluate_all(
        "elements => elements.map(element => element.getBoundingClientRect().toJSON())"
    )
    assert workspace_box is not None
    assert column_box is not None
    assert column_box["x"] >= workspace_box["x"] - 1
    assert column_box["x"] + column_box["width"] <= page.evaluate("innerWidth") + 1
    if viewport_width >= 1200:
        assert abs(column_box["width"] * 12 - workspace_box["width"] * 5) <= 12
    else:
        assert abs(column_box["width"] - workspace_box["width"]) <= 2

    if viewport_width >= 768:
        assert abs(switch_boxes[0]["y"] - switch_boxes[1]["y"]) <= 1
        assert abs(switch_boxes[0]["width"] - switch_boxes[1]["width"]) <= 1
    else:
        assert switch_boxes[0]["y"] < switch_boxes[1]["y"]
        assert abs(switch_boxes[0]["width"] - switch_boxes[1]["width"]) <= 1

    fields = [
        page.locator("select[name='application_type']"),
        page.locator("input[name='code']"),
        page.locator("input[name='label']"),
        page.locator("input[name='display_order']"),
        page.locator("input[name='is_required']"),
        page.locator("input[name='allows_physical']"),
    ]
    fields[0].focus()
    expect(fields[0]).to_be_focused()
    for current, following in zip(fields[:-1], fields[1:], strict=True):
        current.press("Tab")
        expect(following).to_be_focused()

    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_document_requirement_form_preserves_layout_theme_keyboard_and_no_overflow(
    page: Page,
    client,
    user,
    live_server,
) -> None:
    _authenticate(page, client, user, live_server)
    form_url = f"{live_server.url}{reverse('document_requirement_create')}"

    for width, height, _gutter in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(form_url)
        assert "app-skin-dark" not in (page.locator("html").get_attribute("class") or "")
        _assert_document_requirement_form_layout(page, width)

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_class("app-skin-dark")
        _assert_document_requirement_form_layout(page, width)

        page.locator("#theme-toggle").click()
        assert "app-skin-dark" not in (page.locator("html").get_attribute("class") or "")


def _tab_style(locator) -> dict[str, str]:
    return locator.evaluate(
        """element => {
            const style = getComputedStyle(element);
            return {
                backgroundColor: style.backgroundColor,
                borderTopColor: style.borderTopColor,
                borderRightColor: style.borderRightColor,
                borderBottomColor: style.borderBottomColor,
                borderLeftColor: style.borderLeftColor,
                color: style.color,
                outlineColor: style.outlineColor,
                outlineStyle: style.outlineStyle,
                outlineWidth: style.outlineWidth,
            };
        }"""
    )


def _contrast_ratio(first: str, second: str) -> float:
    def relative_luminance(color: str) -> float:
        match = re.fullmatch(r"rgb\((\d+), (\d+), (\d+)\)", color)
        assert match is not None, f"Cor de foco deve ser opaca: {color}"
        channels = (int(value) / 255 for value in match.groups())
        linear = tuple(
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        )
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    first_luminance = relative_luminance(first)
    second_luminance = relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _assert_tabs_visual_contract(page: Page, *, dark: bool) -> None:
    tabs = page.locator(".sm-tabs")
    active = tabs.locator(".nav-link.active")
    inactive = tabs.locator(".nav-link:not(.active)").first
    text_color = "rgb(226, 232, 240)" if dark else "rgb(40, 60, 80)"
    active_background = "rgb(30, 41, 59)" if dark else "rgb(241, 245, 249)"
    interaction_background = "rgb(30, 41, 59)" if dark else "rgb(248, 250, 252)"
    neutral_border = "rgb(100, 116, 139)"
    focus_outline = "rgb(203, 213, 225)" if dark else "rgb(71, 85, 105)"

    expect(tabs).to_be_visible()
    expect(active).to_have_count(1)
    expect(inactive).to_have_css("color", text_color)
    expect(active).to_have_css("color", text_color)
    expect(active).to_have_css("background-color", active_background)
    expect(active).to_have_css("border-top-color", neutral_border)
    assert _tab_style(inactive)["color"] == text_color
    active_style = _tab_style(active)
    assert active_style["color"] == text_color
    assert active_style["backgroundColor"] == active_background
    assert {
        active_style["borderTopColor"],
        active_style["borderRightColor"],
        active_style["borderBottomColor"],
        active_style["borderLeftColor"],
    } == {neutral_border}

    inactive.hover()
    expect(inactive).to_have_css("background-color", interaction_background)
    hovered_style = _tab_style(inactive)
    assert hovered_style["color"] == text_color
    assert hovered_style["backgroundColor"] == interaction_background

    inactive.focus()
    expect(inactive).to_be_focused()
    expect(inactive).to_have_css("background-color", interaction_background)
    expect(inactive).to_have_css("outline-color", focus_outline)
    focused_style = _tab_style(inactive)
    assert focused_style["color"] == text_color
    assert focused_style["backgroundColor"] == interaction_background
    assert focused_style["outlineStyle"] == "solid"
    assert focused_style["outlineWidth"] == "3px"
    assert focused_style["outlineColor"] == focus_outline
    assert _contrast_ratio(focused_style["outlineColor"], focused_style["backgroundColor"]) >= 3


def _assert_tabs_responsiveness(page: Page, *, expect_overflow: bool) -> None:
    metrics = page.locator(".sm-tabs").evaluate(
        """element => {
            const style = getComputedStyle(element);
            return {
                clientWidth: element.clientWidth,
                documentWidth: document.documentElement.scrollWidth,
                flexWrap: style.flexWrap,
                overflowX: style.overflowX,
                scrollWidth: element.scrollWidth,
                viewportWidth: innerWidth,
            };
        }"""
    )

    assert metrics["flexWrap"] == "nowrap"
    assert metrics["overflowX"] in {"auto", "scroll"}
    assert metrics["documentWidth"] <= metrics["viewportWidth"] + 1
    if expect_overflow:
        assert metrics["scrollWidth"] > metrics["clientWidth"]


def _assert_tab_keyboard_activation(
    page: Page,
    tab_id: str,
    *,
    expect_horizontal_scroll: bool,
) -> None:
    navigation = page.locator("[data-sm-list-tabs]")
    requested_tab = navigation.locator(f"[data-sm-tab-id='{tab_id}']")
    original_tab = requested_tab.element_handle()
    assert original_tab is not None

    requested_tab.focus()
    expect(requested_tab).to_be_focused()
    requested_tab.press("Enter")

    active_tab = navigation.locator(f"[data-sm-tab-id='{tab_id}'].active")
    expect(active_tab).to_have_attribute("aria-current", "page")
    expect(active_tab).to_be_focused()
    assert original_tab.evaluate("element => element.isConnected") is False

    metrics = navigation.evaluate(
        """element => {
            const active = element.querySelector("[data-sm-tab-id].active");
            const navigationBox = element.getBoundingClientRect();
            const activeBox = active.getBoundingClientRect();
            return {
                activeLeft: activeBox.left,
                activeRight: activeBox.right,
                navigationLeft: navigationBox.left,
                navigationRight: navigationBox.right,
                scrollLeft: element.scrollLeft,
            };
        }"""
    )
    assert metrics["activeLeft"] >= metrics["navigationLeft"] - 1
    assert metrics["activeRight"] <= metrics["navigationRight"] + 1
    if expect_horizontal_scroll:
        assert metrics["scrollLeft"] > 0


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_enrollment_and_billing_tabs_preserve_geometry_keyboard_and_dark_theme(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    enrollment_screen = next(screen for screen in canonical_screens if screen.name == "matriculas")

    for width, height, gutter in VIEWPORTS:
        _authenticate(page, client, user, live_server)
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{live_server.url}{enrollment_screen.path}")
        expect(page.locator(".sm-page-header")).to_be_visible()
        _assert_geometry(page, enrollment_screen, gutter)
        _assert_tabs_responsiveness(page, expect_overflow=width == 390)
        if width == 390:
            _assert_tab_keyboard_activation(
                page,
                "encerradas",
                expect_horizontal_scroll=True,
            )

    page.set_viewport_size({"width": 1280, "height": 720})
    for screen_name in ("matriculas", "financeiro"):
        screen = next(screen for screen in canonical_screens if screen.name == screen_name)
        _authenticate(page, client, user, live_server)
        page.goto(f"{live_server.url}{screen.path}")
        _assert_tabs_visual_contract(page, dark=False)
        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_class("app-skin-dark")
        _assert_tabs_visual_contract(page, dark=True)
        if screen_name == "matriculas":
            _assert_geometry(page, screen, 30)
        page.locator("#theme-toggle").click()
        expect(page.locator("html")).not_to_have_class("app-skin-dark")
        if screen_name == "financeiro":
            page.set_viewport_size({"width": 390, "height": 844})
            _authenticate(page, client, user, live_server)
            page.goto(f"{live_server.url}{screen.path}")
            _assert_tab_keyboard_activation(
                page,
                "cancelado",
                expect_horizontal_scroll=True,
            )
            page.set_viewport_size({"width": 1280, "height": 720})


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_payment_list_preserves_tabs_history_geometry_and_dark_theme(
    page: Page,
    client,
    user,
    live_server,
) -> None:
    PaymentRecord.objects.bulk_create(
        [
            PaymentRecord(
                amount=Decimal("25.00"),
                paid_date=dt.date(2026, 7, 1) + dt.timedelta(days=index),
                receipt_number=f"UI-PAY-{index:02d}",
                received_by=user,
                created_by=user,
                updated_by=user,
            )
            for index in range(25)
        ]
    )
    _authenticate(page, client, user, live_server)
    screen = Screen(
        "conciliacoes",
        reverse("payment_queue"),
        "#payments-table .sm-scroll-region",
        "[data-sm-layout='list'] > .card-header",
    )

    for width, height, gutter in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{live_server.url}{screen.path}?status=PENDING&q=UI-PAY&sort=-paid_date")
        expect(page.locator(".sm-page-header")).to_be_visible()
        expect(page.locator("nav[aria-label='Situações das conciliações']")).to_be_visible()
        expect(page.locator(".nav-link[aria-current='page']")).to_have_text("Pendente")
        _assert_geometry(page, screen, gutter)
        if width == 390:
            _assert_tab_keyboard_activation(
                page,
                "REVERSED",
                expect_horizontal_scroll=False,
            )

    page.set_viewport_size({"width": 1280, "height": 720})
    _authenticate(page, client, user, live_server)
    page.goto(f"{live_server.url}{screen.path}?status=PENDING&q=UI-PAY&sort=-paid_date")
    _assert_tabs_visual_contract(page, dark=False)
    page.get_by_role("link", name="Conciliado", exact=True).click()
    expect(page).to_have_url(re.compile(r"status=CONFIRMED"))
    expect(page.locator(".nav-link[aria-current='page']")).to_have_text("Conciliado")
    expect(page.locator("input[name='q']")).to_have_value("UI-PAY")
    page.go_back()
    expect(page.locator(".nav-link[aria-current='page']")).to_have_text("Pendente")

    page.locator("#theme-toggle").click()
    expect(page.locator("html")).to_have_class("app-skin-dark")
    _assert_tabs_visual_contract(page, dark=True)


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_primary_screens_preserve_dark_theme(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)
    page.set_viewport_size({"width": 1280, "height": 720})

    for screen in canonical_screens:
        page.goto(f"{live_server.url}{screen.path}")
        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_class("app-skin-dark")
        _assert_geometry(page, screen, 30)
        page.locator("#theme-toggle").click()
