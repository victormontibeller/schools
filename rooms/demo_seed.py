"""Seed DEMO de salas."""


class RoomDemoSeedMixin:
    """Cria o catálogo demonstrativo de salas."""

    def populate_rooms(self) -> None:
        from rooms.contracts import Room

        for code, name, capacity, room_type, resources in [
            (
                "SALA-101",
                "Sala 101",
                32,
                Room.Type.CLASSROOM,
                {"projector": True, "air_conditioning": True},
            ),
            (
                "SALA-102",
                "Sala 102",
                32,
                Room.Type.CLASSROOM,
                {"projector": True, "whiteboard": True},
            ),
            (
                "LAB-CIE",
                "Laboratório de Ciências",
                28,
                Room.Type.LAB,
                {"microscopes": 12, "sink": True},
            ),
            (
                "BIB-001",
                "Biblioteca Monteiro Lobato",
                45,
                Room.Type.LIBRARY,
                {"computers": 10, "reading_tables": 8},
            ),
            (
                "QUADRA",
                "Quadra Poliesportiva",
                80,
                Room.Type.GYM,
                {"covered": True, "bleachers": True},
            ),
        ]:
            self._ensure(
                Room,
                {"code": code},
                {
                    "name": name,
                    "capacity": capacity,
                    "type": room_type,
                    "resources": resources,
                    "floor": "Térreo",
                    "building": "Bloco A",
                },
            )
