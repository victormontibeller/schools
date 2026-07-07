"""Views HTMX para salas físicas."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from base.exceptions import ValidationError
from rooms.forms import RoomForm
from rooms.selectors import RoomSelector
from rooms.services import RoomService


@login_required
def rooms_list(request):
    """Lista salas paginadas; suporta busca por nome e partial HTMX."""
    page = int(request.GET.get("page", 1))
    search = request.GET.get("q", "").strip()
    filters = {}
    if search:
        filters["name__icontains"] = search

    result = RoomSelector().list_rooms(filters=filters, page=page)

    ctx = {
        "result": result,
        "q": search,
        "breadcrumb_items": [
            {"label": "Home", "url": "dashboard"},
            {"label": "Salas", "url": None},
        ],
    }
    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/rooms_table.html", ctx)
    return render(request, "rooms/rooms_list.html", ctx)


@login_required
def room_create(request):
    """Exibe/Processa o formulário de criação de sala."""
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            RoomService(user=request.user).create_room(form.cleaned_data)
            return redirect("rooms_list")
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    return render(request, "rooms/room_form.html", {"form": form, "title": "Nova Sala"})


@login_required
def room_detail(request, pk):
    """Exibe detalhes de uma sala."""
    room = RoomSelector().get_by_id(pk)
    if request.headers.get("HX-Request") and request.GET.get("component") == "information":
        return render(
            request,
            "rooms/partials/room_information_card.html",
            {"room": room},
        )
    return render(request, "rooms/room_detail.html", {"room": room})


@login_required
def room_edit(request, pk):
    """Edita a sala substituindo apenas o card de informações."""
    room = RoomSelector().get_by_id(pk)
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        try:
            room = RoomService(user=request.user).update_room(pk, form.cleaned_data)
            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "rooms/partials/room_information_card.html",
                    {"room": room, "saved": True},
                )
            return redirect("room_detail", pk=pk)
        except ValidationError as exc:
            for field, errors in exc.errors.items():
                for error in errors:
                    form.add_error(field if field != "__all__" else None, error)
    if not request.headers.get("HX-Request"):
        return redirect("room_detail", pk=pk)
    return render(
        request,
        "partials/information_form_card.html",
        {
            "form": form,
            "component_id": "room-information-card",
            "component_title": "Informações da Sala",
            "edit_url": request.path,
            "cancel_url": f"{request.path_info.removesuffix('editar/')}?component=information",
        },
    )
