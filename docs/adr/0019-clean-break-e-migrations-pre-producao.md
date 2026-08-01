# ADR-0019 — Clean break e migrations descartáveis antes da produção

## Status

Aceito em 2026-07-22.

## Contexto

O School Manager ainda não possui instalações produtivas nem dados que precisem atravessar
versões. Manter aliases, rotas antigas, backfills e migrations de reconciliação aumentava o custo
de manutenção e escondia qual era o contrato atual do produto.

## Decisão

- Adotar clean break: toda substituição remove no mesmo lote o código, interface e testes
  superados. Compatibilidade retroativa depende de decisão explícita e ADR.
- Regenerar o grafo inicial após mudanças de schema e recriar integralmente bancos, tenants demo,
  mídia, cache e filas locais.
- Aceitar as divisões `initial=True` geradas pelo Django para resolver dependências e somente os
  seeds de localidades e catálogo inicial da Agenda. Proibir `replaces`, backfills,
  reconciliações e migrations evolutivas no CI.
- Preservar progressive enhancement, acessibilidade e tolerância a dependências do fluxo
  canônico, pois são resiliência atual e não compatibilidade histórica.
- Reportar churn por categoria e artefatos legados removidos em cada entrega.

## Consequências

O repositório mantém uma única forma atual de executar cada fluxo e uma instalação inicial
reproduzível, ao custo de descartar todos os dados locais após mudanças de schema. O primeiro
go-live exigirá novo ADR encerrando esta política; migrations publicadas passarão a ser imutáveis
e mudanças futuras usarão evolução compatível com dados persistentes.
