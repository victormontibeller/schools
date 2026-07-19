---
applyTo: "**/templates/**/*.html"
---

# Templates — regras locais obrigatórias

`docs/09_UI_GUIDELINES.md` é a especificação completa e normativa de frontend. Leia-o antes de criar ou editar templates.

## Aplicação

- Listagens herdam obrigatoriamente de `list_page_base.html`; páginas operacionais com grade
  primária herdam de `page_shell_base.html`. Fichas e formulários continuam nas bases próprias.
- Nunca carregar Bootstrap, tema ou HTMX por CDN; usar os assets locais definidos em `base.html`.
- Formularios POST sempre incluem `{% csrf_token %}`; uploads incluem `multipart/form-data`.
- Usar `partials/form_field.html` para campos comuns. Não remontar `page-header`, `main-content`,
  card, filtros ou paginação de uma listagem fora dos shells canônicos.
- Respostas HTMX renderizam somente o fragmento alvo. Use `hx-target` no menor componente necessário.
- Grades primárias exigem região `table-responsive sm-scroll-region` nomeada, focável com
  `tabindex="0"`, tabela `sm-sticky-table sm-sticky-table--first-column`, estado `{% empty %}` e
  primeira coluna como link principal. Paginação preserva filtros.
- Novas listagens devem registrar sua rota em `core.ui_catalog.LIST_PAGE_CATALOG`; exceções ao
  shell só podem existir na allowlist explícita de `core.ui_contracts`.
- Botões só com ícone precisam de `aria-label`; imagens precisam de `alt`.

## Consulta obrigatória

- Padrão visual, formulários, listagens, avatar/logotipo: `docs/09_UI_GUIDELINES.md`.
- Arquitetura HTTP e camadas: `docs/02_ARCHITECTURE.md` e `docs/03_ENGINEERING_RULES.md`.
