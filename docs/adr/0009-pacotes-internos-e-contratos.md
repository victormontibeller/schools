# ADR-0009 — Pacotes internos, fachadas e contratos de importação

## Status

Aceito em 2026-07-13. Implementado.

## Contexto

Arquivos planos acima de 400 linhas dificultam revisão, cobertura e definição de fronteiras. Ao
mesmo tempo, transformar cada conceito em um novo Django app aumentaria migrations e acoplamento
operacional. Há imports públicos existentes que não podem quebrar.

## Decisão

Autorizar pacotes Python internos, sem novos Django apps, para:

- financeiro: planos, cobranças, pagamentos e políticas;
- core: páginas públicas, saúde, escolas e unidades;
- atividades: atividades, notas e grupos;
- matrículas: solicitações, documentos e rematrículas.

Domínios expõem `contracts.py`, selectors e services públicos. Outros domínios nunca importam
`models.py`. Novos arquivos ficam abaixo de 400 linhas e não há composition roots dispensados.

O CI exige zero imports diretos de modelos entre domínios, zero ORM em views, zero dependências de
`base` para apps e zero SQL direto. Não existe baseline de dívida.

## Consequências

Qualquer violação falha imediatamente. Alterações entre domínios devem evoluir o contrato público.
