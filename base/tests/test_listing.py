"""Testes dos helpers compartilhados de listagem."""

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from base.listing import LISTING_SESSION_KEY, resolve_listing_state


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
