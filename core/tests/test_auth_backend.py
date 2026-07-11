"""Testes do backend tenant-specific de autenticação e permissões."""

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone

from core.auth_backends import DEMO_PERMISSION_ALLOWLIST, RolePermissionBackend


@pytest.mark.django_db
def test_backend_rejects_inactive_expired_and_unverified_demo_users(user):
    backend = RolePermissionBackend()
    user.is_active = False
    assert backend.user_can_authenticate(user) is False

    user.is_active = True
    user.expires_at = timezone.now()
    assert backend.user_can_authenticate(user) is False

    user.expires_at = None
    user.access_mode = "DEMO"
    user.email_verified_at = None
    assert backend.user_can_authenticate(user) is False
    user.email_verified_at = timezone.now()
    assert backend.user_can_authenticate(user) is True


@pytest.mark.django_db
def test_backend_merges_role_permissions_and_restricts_demo_allowlist(user):
    backend = RolePermissionBackend()
    allowed = Permission.objects.get(content_type__app_label="classes", codename="view_class")
    blocked = Permission.objects.get(content_type__app_label="core", codename="view_customuser")
    user.role.permissions.set([allowed, blocked])

    assert {"classes.view_class", "core.view_customuser"} <= backend.get_user_permissions(user)

    user.access_mode = "DEMO"
    demo_permissions = backend.get_user_permissions(user)
    assert "classes.view_class" in demo_permissions
    assert "core.view_customuser" not in demo_permissions
    assert demo_permissions <= DEMO_PERMISSION_ALLOWLIST
