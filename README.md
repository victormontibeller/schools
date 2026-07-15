# School Manager

Plataforma SaaS multi-tenant de gestão escolar em Django 5.2 LTS + PostgreSQL.

## Pré-requisitos
- Python 3.13, PostgreSQL 15+, RabbitMQ, Redis
- `make setup` cria o ambiente virtual `.venv` e instala as dependências de desenvolvimento.

## Início rápido

```bash
make setup
make migrate
export DEV_PLATFORM_ADMIN_PASSWORD='defina-uma-senha-local'
export DEV_DEMO_ADMIN_PASSWORD='defina-outra-senha-local'
./.venv/bin/python manage.py seed_dev
make dev
```

As variáveis locais são configuradas pelo ambiente de cada desenvolvedor; o projeto não mantém
arquivo `.env.example`.

Com o ambiente iniciado, acesse:

- `http://demo.localhost:8000/` para o ambiente escolar de demonstração;
- `http://localhost:8000/` como atalho local para o mesmo ambiente de demonstração;
- `http://platform.localhost:8000/` para o painel da plataforma.

## Comandos úteis

| Comando | Descrição |
|---------|-----------|
| `make dev` | Servidor de desenvolvimento |
| `make test` | Todos os testes com cobertura |
| `make lint` | Verificar código |
| `make format` | Formatar código |
| `make migrate` | Aplicar migrations compartilhadas multi-tenant |
| `make reset-dev` | Recriar bancos e mídia local com confirmação `RESET` |
| `make worker` | Celery worker |

## Estrutura

```
base/           Módulo Python puro (modelos abstratos, serviços, etc.)
tenancy/        Catálogo compartilhado (School e Domain)
core/           Configuração e modelos tenant-specific (Role, CustomUser, BusinessUnit)
accounts/       App de gestão de usuários
audit/          App de auditoria
templates/      Templates base e auth
static/          Assets locais curados usados em produção
design_system/  Pacote Duralux mantido somente como referência visual
docker/         Configs de Traefik, Prometheus, Grafana e Loki
```

Somente `static/` participa de `collectstatic`. O conteúdo completo em `design_system/` não é
publicado e serve como fonte de consulta para evoluções do tema.

## Documentação

Os documentos normativos estão em `docs/`. Consulte primeiro:

- `docs/02_ARCHITECTURE.md` — arquitetura e módulos;
- `docs/03_ENGINEERING_RULES.md` — regras de engenharia;
- `docs/04_SECURITY.md` — segurança e PII;
- `docs/06_MULTI_TENANT.md` — isolamento por tenant;
- `docs/09_UI_GUIDELINES.md` — fonte de verdade dos padrões de interface;
- `docs/12_DEFINITION_OF_DONE.md` — critérios de entrega.

Os documentos de Sprint registram decisões e entregas históricas; em caso de divergência, prevalecem os documentos normativos.

## Observabilidade

`make up` sobe a stack completa: PostgreSQL, Redis, RabbitMQ, Celery (worker + beat),
Traefik (HTTPS + Let's Encrypt) e a stack de observabilidade.

| Serviço     | URL                                | Uso                                    |
|-------------|------------------------------------|----------------------------------------|
| App         | https://localhost                  | Aplicação                              |
| Prometheus  | http://localhost:9090              | Coleta de métricas                     |
| Grafana     | http://localhost:3000 (admin/admin) | Dashboards técnicos e de aplicação     |
| Loki        | interno                            | Logs JSON indexados (via Promtail)     |
| /metrics/   | https://localhost/metrics/ (`Authorization: Bearer <token>`) | Endpoint Prometheus do Django |

## Desenvolvimento multi-tenant

`python manage.py seed_dev` provisiona duas identidades independentes:

- `platform-admin@schools.local` no schema `public`, para o painel da plataforma;
- `admin@demo.com` no schema `demo`, para o desenvolvimento cotidiano.

Operadores públicos administram o catálogo de escolas e operadores, mas não entram em tenants.
Usuários escolares nunca atravessam schemas automaticamente.
As sessões usam o backend de banco do Django e, portanto, a tabela `django_session`
do schema resolvido pelo domínio; Redis é usado para cache, não para sessões.

## Produção

`docker-stack.yml` é a referência de Docker Swarm. Os secrets declarados no arquivo
devem existir antes do deploy. `SCHOOLS_IMAGE` é obrigatório e deve incluir um digest
(`registry/imagem@sha256:...`). O `docker-compose.yml` permanece exclusivo para desenvolvimento.
Consulte `docs/36_PRODUCTION_RUNBOOK.md` antes de migrar mídia ou publicar a stack.
