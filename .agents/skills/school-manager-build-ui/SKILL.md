---
name: school-manager-build-ui
description: Criar ou revisar interfaces canônicas do School Manager com Django Templates, HTMX, Bootstrap/Duralux, CSS local, responsividade e acessibilidade. Usar em tarefas sobre telas, listagens, fichas, formulários, templates, fragmentos HTMX, CSS, JavaScript de interface, navegação, menus, layouts, tema claro/escuro, revisão ou regressão visual.
---

# Construir interface no School Manager

Implementar a interface a partir dos componentes e contratos existentes, mantendo HTTP progressivo e comportamento acessível.

## 1. Localizar o padrão canônico

1. Ler `AGENTS.md` por inteiro, `docs/09_UI_GUIDELINES.md` e a instrução local de cada arquivo afetado.
2. Inspecionar uma tela equivalente, seus templates, partials, view, form, catálogo, contrato e testes antes de criar estrutura nova.
3. Identificar o papel do usuário, as capacidades exigidas pela rota e o menor fragmento que precisa ser atualizado.

## 2. Classificar a interface

- Para listagem, herdar de `list_page_base.html`, registrar a rota em `core.ui_catalog.LIST_PAGE_CATALOG` e manter a tabela em partial próprio.
- Para grade operacional primária, herdar de `page_shell_base.html` e registrar o novo `GridContract` em `core.ui_contracts`.
- Para ficha, reutilizar a grade e os cards canônicos; editar somente o card alvo com HTMX.
- Para formulário, escolher a base canônica adequada e renderizar campos comuns com `partials/form_field.html`.
- Para página pública, usar layout standalone somente quando a navegação e o objetivo forem realmente distintos da aplicação autenticada.

## 3. Implementar o fluxo

1. Renderizar a primeira resposta com Django Templates e usar HTMX apenas para substituir o menor fragmento necessário.
2. Preservar `href`, action do form, URL, histórico, título e fallback sem JavaScript; respostas HTMX devem renderizar somente o fragmento alvo.
3. Incluir CSRF em POST e configurar `multipart/form-data` e `hx-encoding` em uploads.
4. Manter views como orquestração HTTP, forms como validação de campo, selectors como leitura complexa e services como regra de negócio.
5. Usar `$school-manager-secure-command` quando a interface introduzir ou alterar uma mutação de domínio.
6. Resolver visibilidade de controles pelas mesmas políticas de acesso das rotas; ocultar um controle não substitui autorização no backend.
7. Alterar CSS customizado somente em `design_system/refs/duralux/css/school-manager.css`; não copiar o arquivo para `static/css` nem adicionar CDN.
8. Preferir Bootstrap, Duralux e Feather existentes. Manter JavaScript customizado pequeno; usar Alpine.js somente para estado local e reinicializar comportamento após HTMX quando necessário.
9. Garantir HTML semântico, foco visível, operação por teclado, nomes acessíveis, `alt`, `aria-label` e respeito a `prefers-reduced-motion`.

## 4. Verificar conforme o risco

Executar sempre:

```bash
./.venv/bin/python scripts/check_ui_contracts.py
./.venv/bin/pytest <app>/tests/ -q
```

Executar também:

- `make test-ui` ao alterar shell, listagem, grade, CSS, tema ou responsividade;
- testes Chromium nos viewports `1280x720`, `1280x480` e `390x844` para novos contratos geométricos;
- testes de fluxo HTTP e HTMX, incluindo resposta completa e resposta parcial;
- `./.venv/bin/ruff check .` e `./.venv/bin/black --check .` quando houver Python alterado.

Revisar que somente `.sm-scroll-region` rola, que não existe overflow no documento, que cabeçalho e primeira coluna permanecem fixos quando exigidos e que tema escuro e navegação por teclado continuam funcionais.
