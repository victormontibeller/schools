"""Views HTMX para salas físicas."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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

    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/rooms_table.html", {"result": result, "q": search})
    return render(request, "rooms/rooms_list.html", {"result": result, "q": search})


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
    from rooms.models import Room

    room = get_object_or_404(Room, pk=pk)
    return render(request, "rooms/room_detail.html", {"room": room})
