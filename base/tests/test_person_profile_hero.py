"""Testes do cabeçalho canônico de perfis de pessoa."""

from django import forms
from django.template.loader import render_to_string


class ProfileAvatarForm(forms.Form):
    """Formulário mínimo para validar o campo de avatar do componente."""

    avatar = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "sm-profile-avatar-input"}),
    )


def test_person_profile_hero_renders_image_and_upload_control_when_editable():
    form = ProfileAvatarForm()

    rendered = render_to_string(
        "partials/person_profile_hero.html",
        {
            "profile_avatar_field": form["avatar"],
            "profile_has_image": True,
            "profile_image_url": "/avatars/profile.png",
            "profile_avatar_theme": "bg-soft-primary text-primary",
            "profile_initial": "Q",
            "profile_name": "Maria Silva",
            "profile_email": "maria@example.com",
        },
    )

    assert 'src="/avatars/profile.png"' in rendered
    assert 'alt="Foto de Maria Silva"' in rendered
    assert 'name="avatar"' in rendered
    assert "Alterar foto de Maria Silva" in rendered
    assert "avatar-text" not in rendered


def test_person_profile_hero_renders_monogram_without_upload_control_when_displayed():
    rendered = render_to_string(
        "partials/person_profile_hero.html",
        {
            "profile_has_image": False,
            "profile_avatar_theme": "bg-soft-primary text-primary",
            "profile_initial": "Q",
            "profile_name": "Maria Silva",
            "profile_email": "maria@example.com",
        },
    )

    assert "avatar-text" in rendered
    assert "Q" in rendered
    assert 'name="avatar"' not in rendered
