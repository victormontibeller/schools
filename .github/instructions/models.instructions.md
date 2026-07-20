---
applyTo: "**/models.py"
---

# Models — Padrões Obrigatórios

Todo modelo de domínio deve herdar de `BaseModel`, nunca de `models.Model` diretamente. As
exceções de infraestrutura são exclusivamente `BaseModel`, `AuditLog`, `Domain` e os mixins de
tenancy documentados em `docs/05_DATABASE.md`.

```python
"""MyModel: <descrição breve do domínio>."""

from django.db import models

from base.models import BaseModel


class MyModel(BaseModel):
    """Descrição da entidade."""

    # Campos de domínio
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")

    # FK com on_delete explícito e justificado
    school_class = models.ForeignKey(
        "classes.Class",
        on_delete=models.CASCADE,  # CASCADE: sem turma, sem sentido manter
        related_name="my_models",
    )

    # Choices: usar classe interna
    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        ACTIVE = "active", "Ativo"
        CLOSED = "closed", "Encerrado"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        verbose_name = "My Model"
        verbose_name_plural = "My Models"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),          # índice em campo de filtro frequente
            models.Index(fields=["school_class"]),    # índice em FK
        ]

    def __str__(self) -> str:
        return f"MyModel({self.name})"
```

## Campos herdados do BaseModel (não redeclarar)

| Campo | Tipo |
|---|---|
| `id` | UUID (PK automático) |
| `created_at` | DateTimeField (auto) |
| `updated_at` | DateTimeField (auto) |
| `created_by` | FK User |
| `updated_by` | FK User |
| `is_active` | BooleanField (default True) |
| `deleted_at` | DateTimeField (soft delete) |
| `deleted_by` | FK User |
| `version` | IntegerField (concorrência otimista) |

## Regras

- **Nunca** herdar de `models.Model` em modelos de domínio — sempre `BaseModel`
- **Nunca** criar nova exceção de infraestrutura sem atualizar `docs/05_DATABASE.md`
- **Nunca** deletar fisicamente — soft delete é herdado de `BaseModel`
- **Sempre** `Meta.verbose_name` e `Meta.verbose_name_plural`
- **Sempre** índices em campos de filtro frequente e FKs
- **Sempre** `on_delete` explícito com justificativa em comentário
- **Nunca** lógica de negócio em models — apenas schema, campos e `__str__`
- Migrations devem ser criadas com `python manage.py makemigrations` e revisadas antes de aplicar
