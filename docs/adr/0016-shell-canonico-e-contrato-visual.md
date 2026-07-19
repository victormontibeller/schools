# ADR-0016 — Shell canônico e contrato visual

## Status

Aceito em 2026-07-18.

## Contexto

Listagens e grades operacionais reproduziam manualmente cabeçalho, margens, card e regiões de
rolagem. Pequenas diferenças entre implementações faziam novas telas perderem alinhamento,
permitiam rolagem do documento e recortavam controles flutuantes. Revisão manual e documentação
isolada não impediam a regressão, e a cópia do CSS customizado exigia versionamento de cache feito
à mão.

## Decisão

- Adotar `page_shell_base.html` para páginas operacionais com grade primária e
  `list_page_base.html` para todas as listagens autenticadas.
- Centralizar dimensões e comportamento nos tokens e utilitários de
  `design_system/refs/duralux/css/school-manager.css`: cabeçalhos de 80px/65px, margens de
  30px/20px, recuo de registros de 30px/15px, viewport travado, card vertical, região rolável
  acessível, cabeçalho e primeira coluna fixos.
- Manter `ListPageDefinition` como catálogo tipado, indexado pelo nome da rota. O shell obtém do
  catálogo título, criação, busca, contador e alvo HTMX; configuração ausente ou rota inválida
  falha no contrato.
- Registrar grades operacionais e exceções legítimas em `core.ui_contracts`. O verificador
  estático do CI rejeita shells manuais, tabelas primárias fora do contrato, duplicação do CSS e
  versionamento manual de assets.
- Publicar diretamente a fonte do design system via `STATICFILES_DIRS`. Usar armazenamento de
  manifesto não estrito para manter URLs simples em desenvolvimento e nomes com hash de conteúdo
  após `collectstatic`.
- Executar regressão geométrica no Chromium, em job Playwright próprio, para desktop, janela
  baixa e mobile. Asserções de posição e rolagem são bloqueantes; traces e screenshots são
  preservados somente quando há falha.

## Consequências

Novas listagens e grades reutilizam infraestrutura em vez de reconstruir espaçamento e rolagem.
O contrato estático oferece feedback rápido antes do navegador e o teste visual cobre o que a
análise de templates não consegue provar. Alterações deliberadamente fora do padrão exigem uma
entrada explícita na allowlist e revisão arquitetural. O CI ganha um job de navegador e seu custo,
mas deixa de depender de comparação pixel a pixel e reduz o retrabalho visual recorrente.
