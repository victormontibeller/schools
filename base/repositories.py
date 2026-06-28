"""BaseRepository: CRUD genérico para todas as classes de repositório."""

from __future__ import annotations

import logging
from typing import Generic, TypeVar

from django.db import models

from base.exceptions import ObjectNotFoundError
from base.models import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)


class BaseRepository(Generic[ModelT]):
    """CRUD genérico reaproveitado por todos os repositórios de domínio."""

    model_class: type[ModelT]

    def get_by_id(self, object_id) -> ModelT:
        """Retorna o registro pelo id ou lança `ObjectNotFoundError`."""
        try:
            return self.model_class.objects.get(pk=object_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError(self.model_class.__name__, str(object_id)) from None

    def get_by_id_or_none(self, object_id) -> ModelT | None:
        """Retorna o registro pelo id ou `None` quando não existir."""
        try:
            return self.model_class.objects.get(pk=object_id)
        except self.model_class.DoesNotExist:
            return None

    def list(self, filters: dict | None = None) -> models.QuerySet:
        """Lista os registros ativos, aplicando filtros opcionais."""
        qs = self.model_class.objects.all()
        if filters:
            qs = qs.filter(**filters)
        return qs

    def create(self, **kwargs) -> ModelT:
        """Cria um novo registro com os atributos informados."""
        return self.model_class.objects.create(**kwargs)

    def update(self, instance: ModelT, **kwargs) -> ModelT:
        """Atualiza campos do registro e incrementa a versão otimista."""
        for field, value in kwargs.items():
            setattr(instance, field, value)
        instance.version += 1
        instance.save(update_fields=list(kwargs.keys()) + ["version", "updated_at"])
        return instance

    def soft_delete(self, instance: ModelT, user=None) -> ModelT:
        """Aplica exclusão lógica no registro, registrando o executor."""
        instance.soft_delete(user=user)
        return instance

    def restore(self, instance: ModelT, user=None) -> ModelT:
        """Reverte a exclusão lógica do registro, registrando o executor."""
        instance.restore(user=user)
        return instance
