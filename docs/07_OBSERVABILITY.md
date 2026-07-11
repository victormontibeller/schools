# Observabilidade

## Princípio

O sistema deverá possuir observabilidade desde a **primeira Sprint**.

Nenhuma funcionalidade crítica poderá existir sem logs, métricas e eventos associados.

---

## Stack de Observabilidade

| Ferramenta | Responsabilidade |
|---|---|
| **Grafana** | Visualização de dashboards técnicos e de negócio |
| **Prometheus** | Coleta e armazenamento de métricas |
| **Loki** | Coleta, indexação e consulta de logs |
| **OpenTelemetry** | Instrumentação, traces distribuídos e correlação |

O runtime de produção usa `opentelemetry-instrument` no web e nos workers, exportando OTLP para
o Collector interno definido no stack Swarm. Métricas exigem Bearer token no acesso direto.

---

## Logs Estruturados

Todos os logs do sistema deverão ser emitidos em formato **JSON estruturado**.

O uso de `print()` para logging é proibido.

Cada entrada de log deverá conter:

| Campo | Descrição |
|---|---|
| `timestamp` | Data e hora ISO 8601 |
| `level` | Nível do log (INFO, WARNING, ERROR, CRITICAL) |
| `correlation_id` | ID único da requisição |
| `tenant` | Identificador do Tenant ativo |
| `user_id` | ID do usuário autenticado (quando disponível) |
| `module` | Módulo que emitiu o log |
| `message` | Mensagem descritiva |
| `extra` | Dados adicionais relevantes (sem informações sensíveis) |

---

## Correlation ID

Toda requisição HTTP deverá possuir um **Correlation ID** único.

- O Correlation ID deverá ser gerado no início da requisição.
- Deverá ser propagado em todos os logs, eventos e tarefas Celery originados dessa requisição.
- Um Middleware dedicado deverá ser responsável por gerar e injetar o Correlation ID no contexto.

---

## Métricas Obrigatórias

Cada módulo deverá expor métricas para o Prometheus:

- Número de operações realizadas
- Tempo de resposta (p50, p95, p99)
- Número de erros por tipo
- Tamanho das filas Celery
- Cache hit/miss ratio

---

## Dashboards Grafana

### Dashboard Técnico
- CPU, memória e disco
- Conexões ativas ao banco
- Latência das requisições
- Filas RabbitMQ (tamanho e velocidade de consumo)
- Workers Celery (ativos, pausados, falhos)

### Dashboard de Aplicação
- Erros 4xx e 5xx por endpoint
- Usuários ativos por Tenant
- Operações críticas (criação de aluno, frequência, etc.)

### Dashboard Executivo
- Número de Tenants ativos
- Crescimento de usuários
- Taxa de utilização da plataforma

---

## Alertas

Alertas deverão ser configurados para:

- Taxa de erro > 1% em 5 minutos
- Latência p99 > 2 segundos
- Fila Celery com mais de 1000 mensagens pendentes
- Falha em worker Celery
- Banco de dados inatingível

As regras iniciais ficam em `docker/prometheus/alerts.yml`; novas operações críticas devem incluir
alerta ou justificar explicitamente sua ausência.
