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

- `RoleModuleAccess` é único por papel e chave de módulo em cada schema. Seus quatro booleanos
  representam Visualizar, Cadastrar, Editar e Desativar; mudanças incrementam `version` e são
  auditadas. O papel Administrador não possui linhas nessa tabela.

- Matrículas de professores e alunos são geradas por sequência anual isolada no schema do tenant.
- Preferências de e-mail e WhatsApp são armazenadas separadamente e começam desmarcadas.
- Turmas possuem etapa de ensino estruturada, incluindo `OTHER` como opção canônica.
- Turmas usam um catálogo fixo e ordenado de séries compatíveis com a etapa de ensino.
- A Agenda mantém um registro ativo por aluno, turma e data, uma resposta por aspecto fixo
  habilitado e uma situação por refeição aplicável ao turno. `DiaryCategory` e `DiaryOption`
  aceitam somente o catálogo com código estruturado.
- Os estados de alimentação são `ATE_WELL`, `ATE_PARTIALLY`, `DID_NOT_EAT` e `NOT_PRESENT`.
  O responsável pedagógico (`DailyDiary.teacher`) pode ser nulo quando administração ou
  coordenação registra a turma; autoria e atualização continuam identificadas pelo `BaseModel`.
- Entregas de atividades são únicas por atividade e aluno enquanto ativas. A turma da atividade
  pode mudar somente antes de qualquer nota, feedback ou resultado coletivo; entregas ainda
  vazias acompanham a nova turma por soft delete e restauração auditada.
- Atividades e chamadas aceitam apenas combinações professor–turma–disciplina existentes e
  vigentes na grade horária, inclusive quando o professor é o responsável da turma.
- Toda atualização de `BaseModel` condiciona a escrita à versão lida e incrementa `version`
  atomicamente. Soft delete, restore e transições seguem a mesma regra; conflitos não
  sobrescrevem o registro atual. Invariantes agregadas usam `select_for_update` em transação.

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
