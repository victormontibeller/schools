"""Testes do RoomService."""

import datetime as dt

import pytest

from base.exceptions import BusinessRuleViolationError, ObjectNotFoundError, ValidationError
from rooms.models import Room
from rooms.services import RoomService

_BASE_ROOM_DATA = {
    "name": "Sala 101",
    "code": "S101",
    "capacity": 30,
    "type": Room.Type.CLASSROOM,
}


@pytest.mark.django_db
class TestCreateRoom:
    def test_success(self, user):
        room = RoomService(user=user).create_room(_BASE_ROOM_DATA)
        assert room.pk is not None
        assert room.code == "S101"
        assert room.capacity == 30

    def test_duplicate_code(self, user):
        RoomService(user=user).create_room(_BASE_ROOM_DATA)
        with pytest.raises(ValidationError):
            RoomService(user=user).create_room({**_BASE_ROOM_DATA, "name": "Sala 102"})

    def test_missing_required_fields(self, user):
        with pytest.raises(ValidationError):
            RoomService(user=user).create_room({"name": "Sala X"})

    def test_with_building_and_floor(self, user):
        room = RoomService(user=user).create_room(
            {**_BASE_ROOM_DATA, "code": "S102", "building": "Bloco A", "floor": "1"}
        )
        assert room.building == "Bloco A"
        assert room.floor == "1"

    def test_different_types(self, user):
        for room_type, _ in Room.Type.choices:
            room = RoomService(user=user).create_room(
                {"name": f"Sala {room_type}", "code": f"T-{room_type}", "type": room_type}
            )
            assert room.type == room_type


@pytest.mark.django_db
class TestUpdateRoom:
    def test_success(self, user):
        room = RoomService(user=user).create_room(
            {**_BASE_ROOM_DATA, "code": "UPD-ROOM", "capacity": 20}
        )
        updated = RoomService(user=user).update_room(room.pk, {"capacity": 35, "floor": "2"})
        assert updated.capacity == 35
        assert updated.floor == "2"

    def test_duplicate_code_on_update(self, user):
        RoomService(user=user).create_room({**_BASE_ROOM_DATA, "code": "C-001"})
        room2 = RoomService(user=user).create_room({**_BASE_ROOM_DATA, "code": "C-002"})
        with pytest.raises(ValidationError):
            RoomService(user=user).update_room(room2.pk, {"code": "C-001"})


@pytest.mark.django_db
class TestDeactivateRoom:
    def test_success(self, user):
        room = RoomService(user=user).create_room({**_BASE_ROOM_DATA, "code": "DEL-R"})
        RoomService(user=user).deactivate_room(room.pk)
        room.refresh_from_db()
        assert room.deleted_at is not None

    def test_already_deactivated(self, user):
        room = RoomService(user=user).create_room({**_BASE_ROOM_DATA, "code": "DEL-R2"})
        RoomService(user=user).deactivate_room(room.pk)
        with pytest.raises(BusinessRuleViolationError):
            RoomService(user=user).deactivate_room(room.pk)


@pytest.mark.django_db
class TestCheckAvailability:
    def test_available_when_no_schedules(self, user):
        room = RoomService(user=user).create_room({**_BASE_ROOM_DATA, "code": "AVAIL-001"})
        assert RoomService(user=user).check_availability(
            room.pk,
            dt.date(2025, 3, 10),
            dt.time(8, 0),
            dt.time(9, 0),
        )

    def test_deactivate_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            RoomService(user=user).deactivate_room(uuid.uuid4())

    def test_check_availability_room_not_found(self, user):
        import uuid

        with pytest.raises(ObjectNotFoundError):
            RoomService(user=user).check_availability(
                uuid.uuid4(),
                dt.date(2025, 3, 10),
                dt.time(8, 0),
                dt.time(9, 0),
            )

    def test_invalid_time_range(self, user):
        room = RoomService(user=user).create_room({**_BASE_ROOM_DATA, "code": "AVAIL-002"})
        with pytest.raises(ValidationError):
            RoomService(user=user).check_availability(
                room.pk,
                dt.date(2025, 3, 10),
                dt.time(9, 0),
                dt.time(8, 0),
            )
