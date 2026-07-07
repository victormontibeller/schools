"""Helpers compartilhados para listagens com busca, ordenacao e estado persistido."""

from __future__ import annotations

from urllib.parse import urlencode

LISTING_SESSION_KEY = "listing_state"


def build_querystring(params: dict[str, object], *, include_blank: bool = False) -> str:
    """Serializa um dict em query string, com opcao de manter valores vazios."""
    items: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        text = str(value)
        if not include_blank and text == "":
            continue
        items.append((key, text))
    return urlencode(items)


def resolve_listing_state(
    request,
    *,
    scope: str,
    allowed_sorts: set[str],
    default_sort: str,
) -> dict[str, str]:
    """Resolve busca e ordenacao da listagem, persistindo por usuario na sessao."""
    session_state = request.session.get(LISTING_SESSION_KEY, {}).get(scope, {})
    has_q_param = "q" in request.GET
    has_sort_param = "sort" in request.GET

    search = request.GET.get("q") if has_q_param else session_state.get("q", "")
    sort = request.GET.get("sort") if has_sort_param else session_state.get("sort", default_sort)

    search = (search or "").strip()
    if sort not in allowed_sorts:
        sort = default_sort

    listing_state = request.session.get(LISTING_SESSION_KEY, {})
    listing_state[scope] = {"q": search, "sort": sort}
    request.session[LISTING_SESSION_KEY] = listing_state
    request.session.modified = True

    return {"q": search, "sort": sort}


def build_sorting(
    *,
    current_sort: str,
    search: str,
    sortable_fields: list[str],
) -> dict[str, dict[str, str | bool]]:
    """Monta metadados de links e estado visual para colunas ordenaveis."""
    active_field = current_sort.removeprefix("-")
    is_desc = current_sort.startswith("-")
    sorting: dict[str, dict[str, str | bool]] = {}

    for field in sortable_fields:
        is_active = active_field == field
        next_sort = field
        direction = ""
        aria_sort = "none"

        if is_active:
            direction = "desc" if is_desc else "asc"
            aria_sort = "descending" if is_desc else "ascending"
            next_sort = field if is_desc else f"-{field}"

        sorting[field] = {
            "active": is_active,
            "direction": direction,
            "aria_sort": aria_sort,
            "query": build_querystring({"q": search, "sort": next_sort}),
        }

    return sorting
