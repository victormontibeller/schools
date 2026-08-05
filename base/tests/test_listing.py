"""Testes dos helpers compartilhados de listagem."""

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from base.listing import (
    LISTING_SESSION_KEY,
    build_listing_tabs,
    build_sorting,
    resolve_listing_state,
)


def _request_with_session(query: dict[str, str]):
    request = RequestFactory().get("/resource/", query)
    SessionMiddleware(lambda current_request: None).process_request(request)
    request.session.save()
    return request


@pytest.mark.django_db
@pytest.mark.parametrize(("raw_page", "expected"), [("2", 2), ("abc", 1), ("0", 1), ("-3", 1)])
def test_resolve_listing_state_normalizes_page_without_persisting(raw_page, expected):
    request = _request_with_session({"page": raw_page})

    state = resolve_listing_state(
        request,
        scope="resource_list",
        allowed_sorts={"name", "-name"},
        default_sort="name",
    )

    assert state == {"q": "", "sort": "name", "page": expected}
    assert request.session[LISTING_SESSION_KEY]["resource_list"] == {
        "q": "",
        "sort": "name",
    }


def test_build_listing_tabs_preserves_filters_and_resets_page():
    tabs = build_listing_tabs(
        choices=(("open", "Abertas"), ("paid", "Pagas")),
        active="paid",
        parameter="tab",
        preserved_params={
            "q": "mensalidade especial",
            "sort": "-due_date",
            "class_id": "class-1",
            "page": 7,
            "tab": "open",
        },
        counts={"open": 3, "paid": 2},
    )

    assert tabs == [
        {
            "id": "open",
            "label": "Abertas",
            "active": False,
            "query": "q=mensalidade+especial&sort=-due_date&class_id=class-1&tab=open",
            "count": 3,
        },
        {
            "id": "paid",
            "label": "Pagas",
            "active": True,
            "query": "q=mensalidade+especial&sort=-due_date&class_id=class-1&tab=paid",
            "count": 2,
        },
    ]


def test_build_sorting_preserves_public_filters_and_resets_page():
    sorting = build_sorting(
        current_sort="due_date",
        search="parcela",
        sortable_fields=["due_date"],
        preserved_params={"tab": "open", "page": 4},
    )

    assert sorting["due_date"]["query"] == "tab=open&q=parcela&sort=-due_date"
