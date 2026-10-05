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

## Otimização e reconciliação de imagens

Executar com o mesmo acesso ao PostgreSQL e NFS da aplicação. Primeiro inventariar, depois
simular e aplicar explicitamente; substituir `demo` pelo schema desejado ou usar `--all`:

```bash
python manage.py manage_images --schema demo
python manage.py manage_images --schema demo --operation optimize
python manage.py manage_images --schema demo --operation optimize --apply
python manage.py manage_images --schema demo --operation reconcile
python manage.py manage_images --schema demo --operation reconcile --apply
```

Sem `--apply` nenhuma escrita, exclusão ou auditoria é produzida. O inventário valida a possibilidade
de conversão; JSON final mostra os contadores, e erros registram schema/UUID/tipo sem PII. Arquivos
inválidos ou ausentes são preservados. `--all` inclui usuários públicos e cada tenant inativo ou
excluído; Professor compartilha o avatar de Usuário e não gera conversão duplicada. Imagens já
em `optimized/v1` não são recomprimidas. Conversões verificam nome e versão esperados por registro.

A reconciliação só alcança UUIDs gerenciados nas categorias de logos, avatares e fotos, sem
referência em qualquer schema e com mais de 24 horas; documentos, nomes desconhecidos e symlinks
são ignorados. Falha de consulta global impede exclusão. Revisar o inventário e manter backup do
volume antes de aplicação operacional. Consulte ADR-0010 para formatos, namespaces e limites.

## Sondas, estáticos e proteção dos logs

- Web: GET exato `http://127.0.0.1:8000/health/`, independente de Host, HTTPS, sessão e banco.
  Readiness permanece separada, autenticada e capaz de testar dependências.
- Worker: `celery -A core.celery inspect ping --destination celery@$HOSTNAME --timeout 5`;
  a sonda precisa receber resposta do próprio worker. Beat usa reinício em falha e agenda em
  `/tmp/celerybeat-schedule`; nenhum processo Celery herda uma sonda HTTP da imagem.
- WhiteNoise serve somente `STATIC_ROOT`, após SecurityMiddleware, usando o storage canônico
  comprimido e com hash. Nginx permanece restrito a mídia pública e fixado por digest.
- No smoke externo, buscar CSS/JS com hash e conferir 200/cache; tentar mídia privada sem
  autenticação e exigir bloqueio. Testar web/worker/Beat saudáveis e reinício após falha real.
- Enviar marcador sintético em token de convite, reset, URL desconhecida e erro controlado;
  confirmar ausência nos logs de Django/Gunicorn/Traefik e spans exportados. Verificar
  `strict-origin` e `no-store` nas páginas de token, inclusive após passagem pelo proxy, erros
  antecipados e escola inativa. Páginas comuns usam `same-origin`; Traefik preserva esses headers.
  Submeter convites, recuperação e estorno com/sem JavaScript e verificar CSRF ativo e Referer
  sem caminho/query/token nas páginas sensíveis.

A estabilização de 17/09/2026 exige reset dev/demo pelo novo grafo inicial antes da integração.
Build Docker/Swarm, duas réplicas, scans e validação externa devem ser comprovados no ambiente
operacional; verificações locais não substituem essa evidência e não autorizam deploy automático.

O reset local aceita `PYTHON_BIN=/caminho/do/venv/bin/python3.13` para selecionar explicitamente
Python 3.13; sem override, mantém `./.venv/bin/python`. O mesmo executável é usado no fallback
PostgreSQL, nas migrations e no seed. As confirmações e restrições de host continuam obrigatórias.

O CSV de inadimplência mantém uma única consulta/cursor, consumida em blocos de 500 sob o schema
capturado. Pagamentos entre blocos não deslocam posições nem omitem grupos. O cursor é fechado
no contexto do tenant também quando o consumidor interrompe a leitura.

Os testes Chromium com `live_server` usam arquivos fonte via `StaticFilesStorage`, pois o handler
de estáticos do Django intercepta as URLs antes do middleware. O manifesto local de `collectstatic`
não altera essa suíte; testes de produção continuam exigindo WhiteNoise e assets com hash.
