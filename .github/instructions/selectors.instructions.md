---
applyTo: "**/selectors.py"
---

# Selectors — Padrões Obrigatórios

Selectors são **somente-leitura**. Nunca escrevem no banco. Nunca chamam services.

```python
from base.selectors import BaseSelector, PageResult
from base.exceptions import ObjectNotFoundError

class MySelector(BaseSelector):
    model_class = MyModel

    # Listagem paginada simples (herda de BaseSelector.list())
    def list_active(self, page: int = 1) -> PageResult[MyModel]:
        return self.list(order_by="-created_at", page=page)

    # Listagem com filtro
    def list_by_class(self, class_id, page: int = 1) -> PageResult[MyModel]:
        return self.list(filters={"class_id": class_id}, order_by="name", page=page)

    # Busca por ID com erro descritivo (herda de BaseSelector.get_by_id())
    def get_by_id(self, object_id) -> MyModel:
        return super().get_by_id(object_id)

    # Consulta customizada com select_related / prefetch_related
    def get_detail(self, object_id) -> MyModel:
        try:
            return (
                MyModel.objects.select_related("user", "class")
                .prefetch_related("subjects")
                .get(pk=object_id)
            )
        except MyModel.DoesNotExist:
            raise ObjectNotFoundError("MyModel", str(object_id)) from None

    # Agregação (sempre via ORM, nunca SQL direto)
    def count_active_by_class(self, class_id: int) -> int:
        return MyModel.objects.filter(class_id=class_id).count()
```

## Usando `PageResult` nas views

```python
# view
result = MySelector().list_active(page=int(request.GET.get("page", 1)))
# result.items     — lista de objetos
# result.total     — total de registros
# result.has_next  — bool
# result.has_previous — bool
# result.total_pages  — int
```

## Regras

- **Nunca** escrever no banco em um selector
- **Nunca** chamar um service de dentro de um selector
- **Sempre** usar `select_related` / `prefetch_related` em queries N+1 potenciais
- **Nunca** `Model.objects.filter()` diretamente em views — mover para selector
- Queries complexas aqui; a view passa só parâmetros simples (page, filters)
