# School Manager

Plataforma SaaS multi-tenant de gestão escolar em Django 5.1 + PostgreSQL.

## Pré-requisitos
- Python 3.13, PostgreSQL 15+, RabbitMQ, Redis
- `pip install -r requirements-dev.txt`
- Criar `.env` a partir de `.env.example`

## Início rápido

```bash
make setup
make migrate
python manage.py createsuperuser
make dev
```

## Comandos úteis

| Comando | Descrição |
|---------|-----------|
| `make dev` | Servidor de desenvolvimento |
| `make test` | Todos os testes com cobertura |
| `make lint` | Verificar código |
| `make format` | Formatar código |
| `make migrate` | Aplicar migrações |
| `make worker` | Celery worker |

## Estrutura

```
base/           Módulo Python puro (modelos abstratos, serviços, etc.)
core/           App Django principal (School, Domain, Role, CustomUser)
accounts/       App de gestão de usuários
audit/          App de auditoria
templates/      Templates base e auth
design_system/  Assets Duralux (Bootstrap)
```
