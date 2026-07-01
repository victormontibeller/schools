# Sprint 20 — Produção

## Objetivo

Preparar a plataforma para o ambiente de produção com Docker Swarm, hardening de segurança, otimização de performance, configuração de alertas e validação de todos os requisitos não-funcionais antes do go-live.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [ ] O ambiente de produção deverá estar funcional com Docker Swarm.
- [ ] Traefik deverá provisionar HTTPS automaticamente via Let's Encrypt.
- [ ] Backup automático do PostgreSQL deverá estar configurado.
- [ ] Alertas do Grafana deverão notificar a equipe técnica em caso de falhas.
- [ ] Todas as verificações de segurança do OWASP Top 10 deverão ser realizadas e aprovadas.
- [ ] A plataforma deverá suportar a carga esperada com tempo de resposta < 2 segundos (p99).
- [ ] Documentação de operações (runbook) deverá estar criada.

---

## Tarefas

### Docker Swarm

- [ ] Criar `docker-stack.yml` para produção (equivalente ao compose, otimizado para Swarm)
- [ ] Configurar replicas por serviço:
  - `app`: mínimo 2 réplicas
  - `worker`: mínimo 2 réplicas
  - `beat`: exatamente 1 réplica (singleton)
- [ ] Configurar `deploy.resources` com limites de CPU e memória por serviço
- [ ] Configurar `deploy.restart_policy` com política de restart automático
- [ ] Configurar `deploy.update_config` para rolling updates sem downtime
- [ ] Configurar `secrets` do Docker Swarm para gerenciamento de credenciais
- [ ] Configurar `healthcheck` para todos os serviços críticos

### Traefik — Produção

- [ ] Configurar provisionamento automático de certificados Let's Encrypt
- [ ] Configurar roteamento por subdomínio para Tenants
- [ ] Configurar rate limiting por IP no Traefik
- [ ] Configurar headers de segurança: HSTS, CSP, X-Frame-Options
- [ ] Configurar redirect HTTP → HTTPS

### PostgreSQL — Produção

- [ ] Configurar `postgresql.conf` para produção (max_connections, shared_buffers, work_mem)
- [ ] Configurar backup automático diário com retenção de 30 dias
- [ ] Configurar backup incremental via WAL (Point-in-Time Recovery)
- [ ] Testar e documentar procedimento de restore
- [ ] Configurar monitoramento de conexões e slow queries no Grafana

### Segurança — Hardening

- [ ] Executar auditoria de segurança com `django-security-check` ou equivalente
- [ ] Verificar todos os headers HTTP de segurança
- [ ] Garantir que `DEBUG = False` em produção
- [ ] Garantir que `SECRET_KEY` tem 50+ caracteres e não está no código
- [ ] Configurar `SECURE_BROWSER_XSS_FILTER = True`
- [ ] Configurar `SESSION_COOKIE_SECURE = True` e `CSRF_COOKIE_SECURE = True`
- [ ] Revisar permissões de arquivos nos containers (non-root user)
- [ ] Escanear imagens Docker com `trivy` ou equivalente
- [ ] Garantir que nenhuma credencial está em variáveis de ambiente expostas nos logs

### Observabilidade — Produção

- [ ] Configurar alertas no Grafana:
  - Taxa de erro > 1% em 5 min → alerta imediato
  - Latência p99 > 2s → alerta imediato
  - CPU > 80% por 5 min → alerta de atenção
  - Memória > 85% → alerta de atenção
  - Fila Celery > 1000 mensagens → alerta de atenção
  - Worker Celery inativo → alerta imediato
  - Banco inacessível → alerta crítico
- [ ] Configurar canal de destino dos alertas (e-mail ou Slack)
- [ ] Configurar retenção de logs no Loki (mínimo 90 dias)
- [ ] Configurar retenção de métricas no Prometheus (mínimo 30 dias)

### Performance

- [ ] Executar testes de carga com `locust` ou `k6` simulando uso concorrente
- [ ] Identificar e otimizar queries N+1 com `django-debug-toolbar` (em staging)
- [ ] Adicionar índices faltantes identificados em queries lentas
- [ ] Validar que todas as páginas principais carregam em < 2s com 50 usuários simultâneos
- [ ] Configurar compressão gzip no Traefik para respostas HTML/JSON

### CI/CD — Produção

- [ ] Configurar pipeline de deploy automático para produção após aprovação manual
- [ ] Pipeline deverá: rodar testes → build da imagem → push para registry → deploy no Swarm
- [ ] Configurar rollback automático se o healthcheck falhar após deploy
- [ ] Configurar notificação de deploy no canal da equipe

### Documentação Operacional (Runbook)

- [ ] Documentar: como fazer deploy de nova versão
- [ ] Documentar: como escalar workers Celery
- [ ] Documentar: como executar restore do banco de dados
- [ ] Documentar: como adicionar novo Tenant manualmente
- [ ] Documentar: como investigar um erro usando Grafana + Loki + Correlation ID
- [ ] Documentar: procedimento de rollback de deploy

---

## Dependências

- Sprints 00-08 concluídas e validadas
- Ambiente de servidor de produção provisionado

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] Testes de carga aprovados (< 2s p99 com 50 usuários)
- [ ] Todos os alertas do Grafana testados e funcionando
- [ ] Backup e restore testados com sucesso
- [ ] Auditoria de segurança sem itens críticos em aberto
- [ ] Runbook revisado e aprovado pela equipe
- [ ] Go-live autorizado
