# ADR-0010 — Mídia NFS e subdomínios gerenciados

## Status

Aceito em 2026-07-13. Infraestrutura implementada; rollout depende de staging.

## Contexto

Réplicas Swarm não podem depender de disco local para uploads. A resolução de tenants precisa de
uma base de hosts previsível e de TLS wildcard sem distribuir mídia privada pelo proxy.

## Decisão

- Usar `media/` local no desenvolvimento e o mesmo NFSv4 em `/app/media` no web e nos workers.
- Expor somente `media/public/` por Nginx somente-leitura; ali ficam logos institucionais com
  cache longo e nomes imutáveis.
- Manter `media/private/` sem URL pública. Fotos são entregues inline por endpoints autenticados;
  documentos e justificativas são anexos com `private, no-store` e `nosniff`.
- Usar `PLATFORM_DOMAIN` e `TENANT_BASE_DOMAIN`, limitando tenants a um subdomínio gerenciado.
- Emitir wildcard via ACME DNS-01 e guardar a credencial como Docker secret.
- Fixar imagens por digest e exigir a imagem da aplicação também por digest.

## Consequências

Deploy multi-node depende da disponibilidade, backup e permissões do NFS. Domínios customizados
ficam fora desta etapa. A migração e o rollback seguem `docs/36_PRODUCTION_RUNBOOK.md`.
