"""Regressão geométrica determinística dos shells canônicos."""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode, urlparse

import pytest
from django.conf import settings
from django.urls import reverse
from playwright.sync_api import Page, expect

from base.tests.factories import RoomFactory
from classes.models import Class, Enrollment
from financeiro.services import FinanceService
from student_diary.tests.test_services import _class, _enroll, _student
from students.models import Student

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@dataclass(frozen=True, slots=True)
class Screen:
    name: str
    path: str
    scroller: str
    context: str
    footer: str | None = None
    diary_dropdown: bool = False


VIEWPORTS = (
    (1280, 720, 30),
    (1280, 480, 30),
    (390, 844, 20),
)


@pytest.fixture()
def canonical_screens(user) -> tuple[Screen, ...]:
    RoomFactory.create_batch(60, created_by=user, updated_by=user)

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
            enrollment_date=dt.date(2026, 1, 20),
            status=Enrollment.Status.ACTIVE,
            created_by=user,
            updated_by=user,
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
            "financeiro",
            reverse("billing_list"),
            "#billings-table .sm-scroll-region",
            "[data-sm-layout='list'] > .card-header",
        ),
    )


def _authenticate(page: Page, client, user, live_server) -> None:
    client.force_login(user)
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
    assert abs(before["card"]["left"] - before["content"]["left"] - gutter) <= 1
    assert before["documentWidth"] <= before["viewportWidth"] + 1
    assert before["documentHeight"] <= before["viewportHeight"] + 1
    assert before["scrollHeight"] > before["clientHeight"]
    assert before["firstBodyPaddingLeft"] == 30
    if screen.name == "agenda":
        assert before["contextPaddingLeft"] == 30

    page.locator(screen.scroller).evaluate(
        """element => {
            element.scrollTop = element.scrollHeight;
            element.scrollLeft = element.scrollWidth;
        }"""
    )
    after = _geometry(page, screen)

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
    if after["footer"]:
        assert after["footer"]["bottom"] <= after["viewportHeight"] + 1

    scroller = page.locator(screen.scroller)
    scroller.evaluate("element => { element.scrollTop = 0; }")
    scroller.focus()
    expect(scroller).to_be_focused()
    scroller.press("PageDown")
    page.wait_for_function(
        "selector => document.querySelector(selector).scrollTop > 0",
        arg=screen.scroller,
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


@pytest.mark.ui
@pytest.mark.django_db(transaction=True)
def test_primary_screens_follow_geometry_contract(
    page: Page,
    client,
    user,
    live_server,
    canonical_screens,
) -> None:
    _authenticate(page, client, user, live_server)

    for width, height, gutter in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        for screen in canonical_screens:
            page.goto(f"{live_server.url}{screen.path}")
            expect(page.locator(".sm-page-header")).to_be_visible()
            _assert_geometry(page, screen, gutter)
            if screen.diary_dropdown:
                _assert_last_diary_dropdown(page)


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
