# ADR-0006 — Identidade por schema e acesso temporário de suporte

## Status

Aceito.

## Contexto

Usuários no schema público eram visíveis em todos os tenants pelo `search_path`, permitindo
autenticação e seleção de destinatários fora da escola correta. Ao mesmo tempo, operadores da
plataforma precisam diagnosticar tenants sem compartilhar credenciais escolares.

## Decisão

`tenancy.School`, `Domain` e `SupportAccessGrant` são compartilhados. `core.CustomUser`, papéis,
auth e sessions existem separadamente em cada schema, inclusive no `public`. O login sempre usa
o domínio atual. Operadores públicos entram num tenant somente por concessão de uso único com
motivo, expiração, conta técnica sem senha e rastreabilidade do ator público.

Cache escolar inclui o schema na chave. Auditoria é síncrona e participa da mesma transação da
mutação; eventos não críticos continuam isolando falhas.

## Consequências

- O mesmo e-mail pode existir em escolas diferentes.
- Usuários escolares não atravessam tenants.
- Suporte cross-schema é explícito, temporário e auditável.
- Migrations anteriores foram rebaselineadas antes da entrada em produção.
