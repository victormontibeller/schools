---
applyTo: "**/services.py"
---

# Services — Padrões Obrigatórios

> Regras normativas de engenharia, segurança e auditoria estão em `docs/03_ENGINEERING_RULES.md` e `docs/04_SECURITY.md`. Este arquivo cobre apenas a aplicação dessas regras em services.

Todo service deve herdar de `BaseService` e seguir este padrão:

```python
from base.services import BaseService
from base.exceptions import ValidationError, ObjectNotFoundError, BusinessRuleViolationError

class MyService(BaseService):
    def create_entity(self, data: dict) -> MyModel:
        # 1. Validar campos obrigatórios (DRY)
        self.validate_required(data, ["field1", "field2"])

        # 2. Validações de unicidade / regras de negócio
        if MyModel.objects.filter(field1=data["field1"]).exists():
            raise ValidationError(errors={"field1": ["Já cadastrado."]})

        # 3. Criar
        instance = MyModel.objects.create(
            field1=data["field1"],
            created_by=self.user,
            updated_by=self.user,
        )

        # 4. SEMPRE: auditoria + log
        self._record_audit("INSERT", instance)
        self._log("entity_created", entity_id=str(instance.id))
        return instance

    def update_entity(self, entity_id, data: dict) -> MyModel:
        try:
            instance = MyModel.objects.get(pk=entity_id)
        except MyModel.DoesNotExist:
            raise ObjectNotFoundError("MyModel", str(entity_id)) from None

        instance.field1 = data.get("field1", instance.field1)
        instance.updated_by = self.user
        instance.save()

        self._record_audit("UPDATE", instance)
        self._log("entity_updated", entity_id=str(instance.id))
        return instance

    def deactivate_entity(self, entity_id) -> MyModel:
        # DRY: soft-delete + auditoria em uma linha
        return self._deactivate(MyModel, entity_id, "MyModel")
```

## Regras

- **Nunca** raise `ValueError`, `Exception`, `Http404` — use as exceções de `base/exceptions.py`
- **Nunca** PII em `self._log()` (email, CPF, nome, telefone)
- **Sempre** `self._record_audit()` em toda operação de escrita
- **Sempre** setar `created_by=self.user` e `updated_by=self.user` no create
- **Nunca** chamar `instance.delete()` — usar `instance.soft_delete(user=self.user)` ou `self._deactivate()`
- **Nunca** lógica de negócio em views, forms ou tasks

## Exceções disponíveis

```python
from base.exceptions import (
    ValidationError,           # dados inválidos — raise ValidationError(errors={"campo": ["msg"]})
    ObjectNotFoundError,       # não encontrado — raise ObjectNotFoundError("ModelName", str(id))
    BusinessRuleViolationError,# regra violada — raise BusinessRuleViolationError("Mensagem.")
    PermissionDeniedError,     # sem permissão
)
```
