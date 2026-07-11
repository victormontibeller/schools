"""Testes da garantia transacional entre escrita e auditoria."""

from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_audit_failure_rolls_back_domain_write(user):
    """Nenhuma escrita persiste quando o AuditLog falha."""
    from rooms.models import Room
    from rooms.services import RoomService

    with patch("audit.services.AuditService.record", side_effect=RuntimeError("audit down")):
        with pytest.raises(RuntimeError, match="audit down"):
            RoomService(user=user).create_room({"name": "Sala", "code": "ATOMIC-1"})
    assert not Room.all_objects.filter(code="ATOMIC-1").exists()
