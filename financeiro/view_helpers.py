"""Composição HTTP compartilhada pelas telas financeiras."""

from core.permissions import VIEW, can_access


def finance_breadcrumbs(user, *items: tuple[str, str | None]) -> list[dict[str, str | None]]:
    """Monta breadcrumbs sem criar link para uma visão financeira não autorizada."""
    breadcrumbs: list[dict[str, str | None]] = [{"label": "Home", "url": "dashboard"}]
    if can_access(user, "finance_overview", VIEW):
        breadcrumbs.append({"label": "Financeiro", "url": "finance_dashboard"})
    breadcrumbs.extend({"label": label, "url": url} for label, url in items)
    return breadcrumbs
