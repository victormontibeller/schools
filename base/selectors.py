"""BaseSelector: consultas somente-leitura com paginação."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from django.db.models import QuerySet

from base.exceptions import ObjectNotFoundError
from base.models import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass
class PageResult(Generic[ModelT]):
    """Contêiner de paginação com itens, total e metadados da página."""

    items: list[ModelT] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def total_pages(self) -> int:
        """Total de páginas considerando o tamanho configurado."""
        return max(1, -(-self.total // self.page_size)) if self.page_size else 0

    @property
    def has_next(self) -> bool:
        """Indica existência de próxima página."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Indica existência de página anterior."""
        return self.page > 1


class BaseSelector(Generic[ModelT]):
    """Base para consultas somente-leitura com paginação."""

    model_class: type[ModelT]

    def get_by_id(self, object_id) -> ModelT:
        """Retorna o registro pelo id ou lança `ObjectNotFoundError`."""
        try:
            return self.model_class.objects.get(pk=object_id)
        except self.model_class.DoesNotExist:
            raise ObjectNotFoundError(self.model_class.__name__, str(object_id)) from None

    def list(
        self,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        order_by: str | None = None,
    ) -> PageResult[ModelT]:
        """Lista registros ativos com filtros, ordenação e paginação."""
        qs = self.model_class.objects.all()
        if filters:
            qs = qs.filter(**filters)
        if order_by:
            qs = qs.order_by(order_by)
        return self._paginate(qs, page=page, page_size=page_size)

    def _paginate(
        self,
        queryset: QuerySet[ModelT],
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PageResult[ModelT]:
        """Pagina um queryset customizado aplicando os limites globais."""
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        page = max(1, page)
        total = queryset.count()
        offset = (page - 1) * page_size
        return PageResult(
            items=list(queryset[offset : offset + page_size]),
            total=total,
            page=page,
            page_size=page_size,
        )
