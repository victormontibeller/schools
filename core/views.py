"""Health check e placeholder de dashboard."""

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def health(request: HttpRequest) -> HttpResponse:
    """Endpoint de health check retornando JSON com status ok."""
    return HttpResponse(
        content=json.dumps({"status": "ok"}),
        content_type="application/json",
        status=200,
    )


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Exibe o dashboard; placeholder atual redireciona para o admin."""
    return redirect("/admin/")
