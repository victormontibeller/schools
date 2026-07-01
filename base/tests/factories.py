"""Factories reutilizáveis (factory_boy) para os modelos de domínio.

Uso:
    from base.tests.factories import CustomUserFactory

    user = CustomUserFactory()           # email aleatório único
    user = CustomUserFactory(first_name='Maria')

Ver `docs/15_SPRINT_01.md` §88 (factories com factory_boy, antes pendentes).
"""

from __future__ import annotations

import factory

from core.models import CustomUser


class CustomUserFactory(factory.django.DjangoModelFactory):
    """Factory de usuários do sistema — email único por chamada (sequence)."""

    class Meta:
        model = CustomUser
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@test.com")
    first_name = "Foo"
    last_name = "Bar"
    password = factory.PostGenerationMethodCall("set_password", "Senha123")
    is_active = True


class SubjectFactory(factory.django.DjangoModelFactory):
    """Factory de disciplina."""

    class Meta:
        model = "teachers.Subject"

    name = factory.Sequence(lambda n: f"Disciplina {n}")
    code = factory.Sequence(lambda n: f"D{n:03d}")
    workload = 80


class RoomFactory(factory.django.DjangoModelFactory):
    """Factory de sala física."""

    class Meta:
        model = "rooms.Room"

    name = factory.Sequence(lambda n: f"Sala {n}")
    code = factory.Sequence(lambda n: f"R-{n:03d}")
    capacity = 30
    type = "CLASSROOM"


class StudentFactory(factory.django.DjangoModelFactory):
    """Factory de aluno — sem user vinculado (perfil 'acesso ao sistema')."""

    class Meta:
        model = "students.Student"

    enrollment_number = factory.Sequence(lambda n: f"STU-{n:04d}")
    first_name = "Aluno"
    last_name = factory.Sequence(lambda n: f"Sobrenome{n}")
    birth_date = "2010-01-15"
    gender = "NI"
