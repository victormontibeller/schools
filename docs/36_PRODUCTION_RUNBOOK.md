# Runbook de produção — mídia, domínios e rollout

> Estado: procedimento operacional implementado na configuração e pendente de execução em
> staging. Exige janela de mudança, snapshot verificável e operador com acesso ao Swarm, DNS e
> armazenamento. Nunca copie secrets para logs ou para o repositório.

## Pré-requisitos

- Definir `PLATFORM_DOMAIN`, `TENANT_BASE_DOMAIN`, `NFS_MEDIA_SERVER` e `NFS_MEDIA_PATH`.
- Criar os Docker secrets listados em `docker-stack.yml`, inclusive `acme_dns_api_token`.
- Publicar `PLATFORM_DOMAIN` e `*.TENANT_BASE_DOMAIN` no balanceador do Swarm.
- Definir `SCHOOLS_IMAGE` como referência imutável `registry/imagem@sha256:<digest>`.
- Garantir UID/GID 10001 no export NFS ou alterar `APP_UID`/`APP_GID` de modo consistente no build.

## Migração da mídia

1. Criar snapshot consistente da origem e snapshot/backup vazio do destino NFS.
2. Montar origem e destino somente no host de migração. Registrar capacidade e contagem de
   arquivos, sem listar nomes potencialmente pessoais em tickets ou logs.
3. Executar cópia inicial preservando diretórios, modos e timestamps. Gerar manifestos SHA-256
   relativos para origem e destino e comparar com `sha256sum --check`.
4. Subir staging com uma réplica web e um worker apontando para o NFS. Validar upload e download
   autenticado, `Content-Disposition: attachment` e `Cache-Control: private, no-store`.
5. Na janela final, bloquear temporariamente novos uploads, sincronizar apenas diferenças e
   repetir contagem e checksums. Não remover a origem.
6. Atualizar a stack, liberar uploads e validar que um upload feito por uma réplica é baixado
   após a requisição ser atendida por outra. Reiniciar uma réplica e repetir o download.

Rollback: bloquear uploads, reimplantar a imagem/configuração anterior, apontar `MEDIA_ROOT` para
a origem preservada e restaurar o snapshot se houver escrita no destino. Reabrir uploads apenas
depois de comparar os manifestos. Manter snapshots conforme retenção corporativa e testar
periodicamente a restauração do backup do NFS.

## DNS e wildcard TLS

1. Delegar as zonas necessárias e confirmar que o provedor ACME possui somente permissão para
   alterar registros DNS de desafio.
2. Implantar Traefik com DNS-01; a credencial vem do secret e não de label ou variável versionada.
3. Validar certificado para o domínio-base e `*.TENANT_BASE_DOMAIN`, cadeia, renovação e HSTS.
4. Cadastrar dois subdomínios de staging e confirmar que cada host resolve exatamente seu schema.
   Hosts desconhecidos, com porta/caminho ou fora da base devem ser recusados.
5. Confirmar que somente `PLATFORM_DOMAIN` e subdomínios de `TENANT_BASE_DOMAIN` são aceitos.

## Rollout de segurança

1. Aplicar migrations compartilhadas e tenant-scoped antes de liberar tráfego incompatível.
2. Confirmar ausência de rotas, permissões, contas técnicas e sessões de suporte cross-schema.
3. Testar que logos são públicos e que fotos, avatares, matrículas e justificativas não são
   alcançáveis pelo Nginx público.
4. Executar `check --deploy`, migrations check, Ruff, Black, testes SQLite/PostgreSQL,
   `pip-audit`, Gitleaks e Trivy. Instalações devem usar os locks com hashes.
5. Rodar duas réplicas web e dois workers em nós diferentes; validar NFS, health/readiness,
   tarefas Celery com correlation ID e isolamento de tenant.
6. Liberar por atualização `start-first`, uma réplica por vez, acompanhando erros, latência,
   revogações e fila. A configuração Swarm deve reverter automaticamente em falha.

## Evidências mínimas

Guardar fora do repositório: IDs dos snapshots, checksums agregados, resultado dos scans, serial
e validade do certificado, imagens/digests implantados, horário de início/fim e decisão de go/no-go.
