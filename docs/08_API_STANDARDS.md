# API Standards

> **Status atual:** O projeto usa Django Templates + HTMX como interface principal.
> APIs REST serão expostas futuramente para integrações externas (mobile, webhooks, IA).

---

## Princípios

- **REST** com versionamento explícito no path: `/api/v1/`
- **JSON** como formato único de request/response
- **OpenAPI** (drf-spectacular): documentação automática em `/api/v1/schema/`
- **Autenticação:** Session (web) + JWT (API externa) — nunca Basic Auth em produção
- **Rate limiting:** obrigatório em todos os endpoints via Redis

---

## Estrutura de Resposta Padrão

### Sucesso
```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

### Erro de validação (400)
```json
{
  "error": "validation_error",
  "message": "Os dados informados são inválidos.",
  "errors": {
    "name": ["Campo obrigatório."],
    "email": ["Formato inválido."]
  }
}
```

### Erro de negócio (409)
```json
{
  "error": "business_rule_violation",
  "message": "Professor já está desativado."
}
```

### Não encontrado (404)
```json
{
  "error": "not_found",
  "message": "Teacher com id '...' não encontrado."
}
```

---

## Convenções de Endpoint

| Operação | Método | Path |
|---|---|---|
| Listar | GET | `/api/v1/teachers/` |
| Criar | POST | `/api/v1/teachers/` |
| Detalhe | GET | `/api/v1/teachers/{id}/` |
| Atualizar | PUT/PATCH | `/api/v1/teachers/{id}/` |
| Desativar | DELETE | `/api/v1/teachers/{id}/` |
| Ação customizada | POST | `/api/v1/teachers/{id}/assign-subject/` |

---

## Paginação

- Parâmetros: `?page=1&page_size=20`
- `page_size` máximo: 100 (configurado no `BaseSelector`)
- Resposta inclui `total`, `total_pages`, `has_next`, `has_previous`

---

## Filtros

- Parâmetros de query string: `?status=active&class_id=<uuid>`
- Filtros complexos via selectors — nunca na view diretamente

---

## Segurança

- CSRF: não necessário para APIs JWT (stateless)
- Throttling: 100 req/min para usuários autenticados, 20/min para anônimos
- Permissões: verificar role do usuário no tenant ativo antes de toda operação
- Correlation ID: propagado no header `X-Correlation-ID` de resposta
