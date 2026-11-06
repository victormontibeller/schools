"""Referência Axes sem credenciais, cabeçalhos ou caminho bruto informado pelo cliente."""

from base.context import correlation_id


def axes_client_reference(username, ip_address, user_agent, path_info, request):
    route = getattr(getattr(request, "resolver_match", None), "view_name", "unresolved")
    return f"route={route}; reference={correlation_id.get()}"
