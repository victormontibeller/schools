# AI Instructions

## Antes de Qualquer Implementação

1. Ler `AGENTS.md` na raiz do projeto — contém todos os padrões com exemplos de código.
2. Ler o doc relevante em `docs/` (arquitetura, segurança, multi-tenant, etc.).
3. Verificar se já existe helper reutilizável em `base/services.py` ou `base/selectors.py`.
4. Nunca alterar a arquitetura de camadas (models → services → selectors → views).
5. Nunca ignorar segurança (OWASP Top 10, `docs/04_SECURITY.md`).

---

## Checklist de Implementação

Antes de entregar qualquer código:

- [ ] Entidade herda de `BaseModel`?
- [ ] Service herda de `BaseService`?
- [ ] Regra de negócio está em `services.py`, não em view/form/task?
- [ ] Toda escrita chama `self._record_audit()`?
- [ ] Toda operação tem `self._log()` sem PII?
- [ ] Nenhum PII (email, CPF, nome, telefone) em logs?
- [ ] Usa exceções de `base/exceptions.py`?
- [ ] Queries complexas em `selectors.py`?
- [ ] Soft delete usado (nunca `instance.delete()`)?
- [ ] Testes escritos (`test_<verbo>_<condição>()`)?
- [ ] Cobertura de testes ≥ 80%?
- [ ] Nenhum `print()` no código?
- [ ] Secrets em variáveis de ambiente?

---

## Padrões de Código Resumidos

### Service — padrão mínimo
```python
class MyService(BaseService):
    def create_entity(self, data: dict):
        self.validate_required(data, ["field"])
        instance = MyModel.objects.create(created_by=self.user, **data)
        self._record_audit("INSERT", instance)
        self._log("created", entity_id=str(instance.id))
        return instance
```

### Selector — padrão mínimo
```python
class MySelector(BaseSelector):
    model_class = MyModel

    def list_all(self, page: int = 1) -> PageResult:
        return self.list(order_by="-created_at", page=page)
```

### Exceções — usar sempre
```python
raise ValidationError(errors={"field": ["Mensagem."]})
raise ObjectNotFoundError("Model", str(id))
raise BusinessRuleViolationError("Regra violada.")
```

### Celery + Multi-Tenant
```python
@shared_task
def my_task(tenant_schema: str, entity_id: str):
    with schema_context(tenant_schema):
        # lógica aqui
```

---

## Proibições Absolutas

| Proibido | Alternativa |
|---|---|
| `print()` | `self._log()` ou `logger.info()` |
| `Model.objects.filter()` em view | `MySelector().list()` |
| Regra de negócio em view | `MyService().do_something()` |
| `instance.delete()` | `instance.soft_delete(user=self.user)` |
| `raise ValueError(...)` | `raise BusinessRuleViolationError(...)` |
| SQL direto | ORM do Django |
| Secret em código | Variável de ambiente |
| PII em log | Omitir ou anonimizar |
| API externa direta em task | `notifications/channels/` SDK |

---

## Referências Rápidas

| Preciso de... | Olhar em... |
|---|---|
| Padrões completos com exemplos | `AGENTS.md` |
| Regras de engenharia | `docs/03_ENGINEERING_RULES.md` |
| DRY helpers de BaseService | `docs/10_CODING_STANDARDS.md` |
| Segurança e PII | `docs/04_SECURITY.md` |
| Multi-tenant | `docs/06_MULTI_TENANT.md` |
| Decisões arquiteturais | `docs/adr/` |
| Skills para IDE | `.github/instructions/` |
