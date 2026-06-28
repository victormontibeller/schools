# Banco de Dados

## Banco de Dados Principal

O sistema deverá utilizar **PostgreSQL** como único banco de dados relacional.

---

## BaseModel

Todas as entidades do sistema deverão herdar de `BaseModel`.

Nenhuma entidade poderá ser criada sem herdar de `BaseModel`.

### Campos Obrigatórios

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | UUID (PK) | Identificador único universal, gerado automaticamente |
| `created_at` | DateTimeField | Data e hora de criação do registro |
| `updated_at` | DateTimeField | Data e hora da última atualização |
| `created_by` | FK User | Usuário que criou o registro |
| `updated_by` | FK User | Usuário que realizou a última atualização |
| `deleted_at` | DateTimeField | Data e hora da exclusão lógica (null se ativo) |
| `deleted_by` | FK User | Usuário que realizou a exclusão lógica |
| `is_active` | BooleanField | Indica se o registro está ativo |
| `version` | IntegerField | Controle de versão para contrôle de concorrência |

---

## Soft Delete

O Soft Delete deverá ser utilizado em todas as entidades do sistema.

- Nenhum registro poderá ser removido fisicamente do banco de dados.
- A exclusão deverá apenas preencher os campos `deleted_at`, `deleted_by` e definir `is_active = False`.
- Todas as queries padrão deverão filtrar automaticamente registros com `deleted_at` preenchido.
- Um Manager customizado deverá ser implementado no `BaseModel` para garantir este comportamento.

---

## Convenções

- Toda migration deverá ser revisada antes de ser aplicada.
- Migrations destrutivas (drop de colunas ou tabelas) deverão ser documentadas como ADR.
- Índices deverão ser criados para todos os campos usados em filtros frequentes.
- Chaves estrangeiras deverão ter `on_delete` explícito e justificado.
- O campo `version` deverá ser incrementado a cada atualização para suportar controle otimista de concorrência.

---

## Auditoria de Banco

Toda operação de escrita deverá gerar um registro no módulo de auditoria, contendo:

- Usuário responsável
- Tenant ativo
- Tabela e registro afetado
- Tipo de operação (INSERT, UPDATE, DELETE, RESTORE)
- Valores anteriores (old values)
- Valores novos (new values)
- Data, hora, IP e navegador
