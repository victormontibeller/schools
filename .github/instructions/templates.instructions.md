---
applyTo: "**/templates/**/*.html"
---

# Templates — regras locais obrigatórias

`docs/09_UI_GUIDELINES.md` é a especificação completa e normativa de frontend. Leia-o antes de criar ou editar templates.

## Aplicação

- Usar `{% extends "base.html" %}` ou uma base de formulário compatível.
- Nunca carregar Bootstrap, tema ou HTMX por CDN; usar os assets locais definidos em `base.html`.
- Formularios POST sempre incluem `{% csrf_token %}`; uploads incluem `multipart/form-data`.
- Usar `partials/form_field.html` para campos comuns e `partials/list_header.html`/`list_footer.html` nas listagens aplicáveis.
- Respostas HTMX renderizam somente o fragmento alvo. Use `hx-target` no menor componente necessário.
- Tabelas exigem `table-responsive`, estado `{% empty %}`, primeira coluna como link principal e paginação que preserva filtros.
- Botões só com ícone precisam de `aria-label`; imagens precisam de `alt`.

## Consulta obrigatória

- Padrão visual, formulários, listagens, avatar/logotipo: `docs/09_UI_GUIDELINES.md`.
- Arquitetura HTTP e camadas: `docs/02_ARCHITECTURE.md` e `docs/03_ENGINEERING_RULES.md`.
