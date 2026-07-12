"""RoomService: regras de negócio para salas físicas."""

import logging

from base.exceptions import ObjectNotFoundError, ValidationError
from base.repositories import BaseRepository
from base.services import BaseService

logger = logging.getLogger(__name__)


class _RoomRepo(BaseRepository):
    @property
    def model_class(self):
        from rooms.models import Room

        return Room


class RoomService(BaseService):
    """Serviço de aplicação para o domínio de salas físicas."""

    def create_room(self, data: dict):
        """Cria uma sala a partir dos dados validados."""
        from rooms.models import Room

        self.validate_required(data, ["name", "code"])

        code = data["code"].strip()
        if Room.objects.filter(code=code).exists():
            raise ValidationError(errors={"code": ["Código já cadastrado."]})

        room = Room.objects.create(
            name=data["name"].strip(),
            code=code,
            capacity=int(data.get("capacity", 0) or 0),
            type=data.get("type", Room.Type.CLASSROOM),
            observations=(data.get("observations") or "").strip(),
            floor=(data.get("floor") or "").strip(),
            building=(data.get("building") or "").strip(),
            created_by=self.user,
            updated_by=self.user,
        )
        self._record_audit("INSERT", room)
        self._log("Sala criada", room_id=str(room.pk))
        return room

    def update_room(self, room_id, data: dict):
        """Atualiza os dados de uma sala existente."""
        repo = _RoomRepo()
        room = repo.get_by_id(room_id)
        old = {"name": room.name, "code": room.code, "capacity": room.capacity}

        allowed = {"name", "capacity", "type", "observations", "floor", "building"}
        updates = {k: v for k, v in data.items() if k in allowed}

        if "code" in data:
            code = data["code"].strip()
            from rooms.models import Room

            if Room.objects.filter(code=code).exclude(pk=room_id).exists():
                raise ValidationError(errors={"code": ["Código já cadastrado."]})
            updates["code"] = code

        updates["updated_by"] = self.user
        room = repo.update(room, **updates)
        self._record_audit("UPDATE", room, old_values=old)
        self._log("Sala atualizada", room_id=str(room.pk))
        return room

    def deactivate_room(self, room_id):
        """Desativa uma sala (soft delete)."""
        from rooms.models import Room

        return self._deactivate(Room, room_id, "Room")

    def check_availability(self, room_id, date, start_time, end_time):
        """Verifica disponibilidade de uma sala em uma data e janela de horário.

        Procura `Schedule` ativos com a sala dada cuja validade cobre `date`, e
        cujo `TimeSlot` sobrepõe o intervalo [start_time, end_time). Cronograma
        preterido (valid_until < date) é ignorado.
        """
        repo = _RoomRepo()
        try:
            room = repo.model_class.all_objects.get(pk=room_id)
        except repo.model_class.DoesNotExist:
            raise ObjectNotFoundError("Room", str(room_id)) from None

        if end_time <= start_time:
            raise ValidationError(
                errors={"end_time": ["Horário final deve ser maior que o inicial."]}
            )

        try:
            from django.db.models import Q

            from agenda.models import Schedule
        except ImportError:
            # agenda ainda não instalado — sem conflitos possíveis.
            return True

        qs = Schedule.all_objects.filter(
            room=room,
            is_active=True,
            valid_from__lte=date,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=date))
        # Overlap baseado no TimeSlot vinculado.
        qs = qs.filter(time_slot__start_time__lt=end_time).filter(
            time_slot__end_time__gt=start_time
        )
        return not qs.exists()
