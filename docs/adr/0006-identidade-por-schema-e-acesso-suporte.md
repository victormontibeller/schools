# ADR-0006 — Identidade por schema e suporte cross-schema adiado

## Status

Aceito.

## Contexto

Identidades compartilhadas pelo `search_path` permitiam autenticação e seleção de destinatários
fora da escola correta. O produto ainda está em desenvolvimento e não necessita de impersonação
operacional.

## Decisão

`tenancy.School` e `Domain` são compartilhados. `core.CustomUser`, papéis, autenticação e sessões
existem separadamente em cada schema, inclusive no `public`. O login sempre usa o domínio atual.
Operadores públicos administram o catálogo, mas não acessam tenants. Suporte cross-schema foi
adiado e exigirá novo ADR e revisão de segurança antes de existir.

## Consequências

- O mesmo e-mail pode existir em escolas diferentes.
- Usuários escolares não atravessam tenants.
- Não existem grants, conta técnica, modo `SUPPORT` ou permissão `access_tenant`.
- As migrations foram reinicializadas antes da entrada em produção.
