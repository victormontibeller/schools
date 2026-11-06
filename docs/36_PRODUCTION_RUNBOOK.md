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

## Piloto fictício reproduzível e acesso local

Consulte ADR-0026. Nunca ative `FICTITIOUS_MODE` em produção ou com dados reais. Configure um
**banco novo**, diretório 0700 em `/tmp`, `DEBUG=true`, `FICTITIOUS_MODE=true`,
`FICTITIOUS_DIRECTORY`, `FICTITIOUS_HTTP_PORT`, `MEDIA_ROOT` dentro desse diretório,
`PLATFORM_DOMAIN=platform.localhost`, `TENANT_BASE_DOMAIN=localhost`, DB de prefixo
`schools_pilot_` em loopback e Redis exclusivo do exercício. Proteja o arquivo de ambiente com
0600. Não copie senhas, tokens nem mensagens capturadas para tickets, logs ou repositório.

```sh
make migrate-all VENV_BIN=/caminho/venv/bin
python manage.py setup_fictitious_pilot
python manage.py runserver 127.0.0.1:18080 --noreload
python scripts/verify_fictitious_pilot.py
```

O comando cria Escola Piloto Ipê (duas turmas, três crianças, docentes, equipe, irmãos, guarda e
pessoa de retirada) e uma escola de comparação, usando bootstrap/convites/carga/matrícula
canônicos. Crianças não têm contas, e-mails ou documentos inventados. Não usa `seed_dev` nem
contas DEMO. `access.json` contém somente credenciais fictícias e referências; `messages/` contém
capturas privadas. Configuração concluída é reconhecida; configuração parcial exige investigação
ou outro banco novo, não limpeza silenciosa. A porta faz parte das URLs geradas canonicamente.

Sem RabbitMQ, o comando drena intenções explicitamente pelo mesmo service. Isso comprova a
persistência e revalidação, mas **não** homologa worker/Beat/broker reais.

## Portabilidade e saída de uma escola

1. Registrar solicitação, escopo, destinatário autorizado e referência de atendimento.
2. Obter aprovação do administrador escolar; o operador público não acessa conteúdo por sessão
   de outro usuário. O comando operacional recebe a identidade autorizada do tenant.
3. Suspender novas escritas em janela coordenada, sem parar outras escolas se desnecessário.
4. Executar com pasta de saída privada 0700 e caminho inexistente:

```sh
python manage.py export_school --schema ESCOLA --actor-id UUID_ADMIN --output /privado/escola.zip
```

5. Conferir manifesto, contagens, hashes e mídia. O pacote inclui dados pessoais necessários à
   portabilidade: transferir por canal autenticado/criptografado, sem anexá-lo ao chamado.
6. Registrar recebimento e prazo de retenção/eliminação conforme política aprovada. Suspender
   escola pela plataforma revoga consulta e novas entregas; não remove outros tenants nem
   apaga automaticamente histórico. Encerramento definitivo depende da política real documentada.

## Backup, frescor, restauração e rollback

O procedimento abaixo exige **todos os escritores parados**: web, workers, Beat, jobs e uploads;
aguardar transações/tarefas em andamento. Confirmar a quiescência antes de passar a opção.
Executar em host com PostgreSQL cliente compatível e credenciais via ambiente/secret, nunca CLI.
Saída deve estar fora da árvore de mídia, em pasta 0700. Não usar `reset_dev.sh` como recuperação.

```sh
python scripts/pilot_backup.py backup --database DB_ORIGEM --media /midia \
  --output /backups/ponto-UTC.zip --writers-stopped
python scripts/pilot_backup.py check --source /backups/ponto-UTC.zip
python scripts/pilot_backup.py restore --source /backups/ponto-UTC.zip \
  --database DB_NOVO --directory /restauracoes/NOVA_PASTA
```

Automação produtiva deve criar um ponto consistente a cada **30 minutos**, com máximo observado
menor ou igual a uma hora, checar resultado/frescor e alertar falhas independentemente da fila.
O procedimento de quiescência deve ser homologado para esse agendamento; se interrupções forem
inaceitáveis, implementar e ensaiar snapshot coordenado ou PITR+versionamento da mídia antes da
entrada real. Um cron que só copia mídia enquanto há escrita não atende ao requisito.

Definir retenção diária/semanal, armazenamento externo criptografado, chave fora do backup,
acesso mínimo, capacidade e testes periódicos de restore. Estes controles dependem do operador
real: não foram provisionados pelo ensaio local. Usar nomes novos por execução, verificar SHA-256
e testar de fato a cópia externa. Monitor externo deve verificar frescor pelo menos a cada cinco
minutos; o próprio backup vencido não pode depender de Celery para alertar.

Após restauração: apontar configuração a banco e mídia novos; usar Redis separado ou prefixo
novo e reconstruir/inativar apenas chaves desse ambiente. Conferir todas as escolas, contagens,
histórico financeiro, ciência, documentos e abertura de mídia privada; testar login/permissões.
Reconciliar o intervalo entre ponto recuperado e incidente: guarda revogada, desativações,
permissões, convites, pagamentos/estornos e documentos. Reaplicar correções por serviços auditados
com evidência externa. Não reabrir por simples sucesso de `pg_restore` ou checksum. Registrar
quem autorizou a reabertura. Rollback mantém origem preservada; bloquear escrita antes de trocar
configuração e reconciliar qualquer escrita ocorrida no destino.

## Monitor independente e contatos de operação

```sh
python manage.py check_pilot_operations --backup /backups/ponto-UTC.zip \
  --service-url https://escola.exemplo/health/ --alert-url https://receptor.exemplo/alertas \
  --state-file /privado/monitor-state.json
```

Configure `MONITOR_ALERT_TOKEN` em secret. O receptor recebe somente códigos, referência opaca e
estado; redirecionamentos são recusados. Banco indisponível, backup inválido/vencido, serviço fora
e fila/outbox atrasada produzem sinais operacionais. A sonda TCP do broker não substitui `inspect
ping` nem processamento real. O estado deduplica repetição; definir escalonamento humano e
recorrência externa. HTTPS/rotas auth Traefik usam rate limit próprio, além do Axes e limite
compartilhado do reset. `/metrics` usa o token canônico da aplicação, sem placeholder Basic Auth.

| Responsabilidade | Titular | Substituto | Contato imediato e janela |
|---|---|---|---|
| Suporte técnico/restore/alertas | A definir antes de dados reais | A definir | A definir |
| Administração escolar | A definir pela escola | A definir | A definir |
| Secretaria, Coordenação e Financeiro | Configurar por setor | Configurar vínculo autorizado | Calendário administrativo |

Recuperação extraordinária de administrador exige chamado, prova de identidade e vínculo com a
escola, validação do titular/substituto técnico e registro de executor/aprovação. Preferir outro
ADMIN ativo e recuperação nativa. Se ambos inacessíveis, intervenção técnica controlada por
comando auditado, sem impersonação, senha compartilhada ou bootstrap repetido; testar o fluxo
antes da entrada real e invalidar acesso comprometido.

## Treinamento, transição e decisão de liberação

| Perfil | Exercício obrigatório |
|---|---|
| Operador | Provisionar escola, bootstrap e Agenda; suspender sem afetar outra escola |
| Administrador | Ativar, cadastrar substituto/equipe, corrigir convite, configurar setores/acessos |
| Secretaria | Prévia/carga, conferir guarda/retirada, matrícula/documentos e atendimento |
| Coordenação | Turmas/calendário, devolver/revisar/publicar Agenda, comunicado/ciência/correção |
| Professor | Somente suas turmas; frequência/rotina, reenvio após devolução |
| Financeiro | Contrato/cobrança, pagamento, recibo, estorno e solicitação financeira |
| Responsável | Ativar/recuperar, vários filhos, Agenda/ciência, solicitação privada e cobranças permitidas |
| Retirada/criança | Cadastro sem conta; conferência no portão permanece operacional |
| Suporte | Referência opaca, alerta, recuperação em destino novo e reconciliação |

| Processo | Fonte oficial durante a transição |
|---|---|
| Cadastro, guarda e matrícula aprovados/importados | School Manager após reconciliação e aceite escolar |
| Agenda, comunicados e atendimento habilitados | School Manager; e-mail é aviso, não registro oficial |
| Contratos/cobranças/baixas migrados e conferidos | School Manager; instituição financeira comprova recebimento externo |
| Retirada, ficha de cuidados, assinatura, documentos ainda não substituídos | Procedimento externo vigente da escola, a identificar no aceite |

Antes de dados reais: registrar fonte específica de cada processo, responsáveis, treinamento e
contato imediato; reconciliar **todas** as turmas/alunos/guardas; validar jornadas e negativos;
aprovar testes, cobertura, scans e infraestrutura real; ensaiar recuperação e alerta recebido por
pessoa responsável; assinar ADR encerrando política descartável. Qualquer falha conhecida de
acesso, perda de dados ou integridade financeira bloqueia liberação. A escola fictícia não é esse
aceite. Após entrada real, acompanhar quatro semanas de ativação, leitura/ciência, falhas,
atendimentos atrasados e dificuldades antes de expandir para até três escolas.
