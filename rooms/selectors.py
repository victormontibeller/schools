"""RoomSelector: consultas somente-leitura para salas."""

from base.selectors import BaseSelector, PageResult


class RoomSelector(BaseSelector):
    """Selector para a entidade Room — consultas paginadas e por código."""

    @property
    def model_class(self):
        from rooms.models import Room

        return Room

    def list_rooms(self, filters=None, order_by="name", page=1, page_size=20) -> PageResult:
        """Lista salas ativas paginadas, com filtros opcionais."""
        return self.list(filters=filters, order_by=order_by, page=page, page_size=page_size)

    def get_room_by_id(self, room_id):
        """Retorna a sala com o ID informado."""
        return self.get_by_id(room_id)

    def get_room_by_code(self, code: str):
        """Retorna a sala com o código informado, ou None."""
        from rooms.models import Room

        return Room.objects.filter(code=code).first()
