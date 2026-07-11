"""Testes dos helpers de interface."""

from types import SimpleNamespace

from core.templatetags.ui_helpers import user_role_label


def test_user_role_label_prefers_explicit_role():
    user = SimpleNamespace(role_id=1, role="Coordenador", is_staff=False, is_authenticated=True)

    assert user_role_label(user) == "Coordenador"


def test_user_role_label_infers_teacher_profile():
    user = SimpleNamespace(
        role_id=None,
        role=None,
        teacher_profile=object(),
        is_staff=False,
        is_authenticated=True,
    )

    assert user_role_label(user) == "Professor"


def test_user_role_label_falls_back_to_admin():
    user = SimpleNamespace(role_id=None, role=None, is_staff=True, is_authenticated=True)

    assert user_role_label(user) == "Administrador"


def test_user_role_label_does_not_query_school_profiles_for_platform_admin():
    class PlatformAdmin:
        role_id = None
        role = None
        is_staff = True
        is_superuser = True
        is_authenticated = True

        @property
        def teacher_profile(self):
            raise AssertionError("Perfil escolar não deve ser consultado no schema público")

    assert user_role_label(PlatformAdmin()) == "Administrador da Plataforma"
