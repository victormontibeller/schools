# Banco de Dados

## Banco de Dados Principal

O sistema deverá utilizar **PostgreSQL** como único banco de dados relacional.

---

## BaseModel

Todas as entidades de domínio deverão herdar de `BaseModel`.

Nenhuma entidade de domínio poderá ser criada sem herdar de `BaseModel`.

As únicas exceções de infraestrutura são:

- `BaseModel`, por ser a classe abstrata que define os campos e invariantes compartilhados;
- `AuditLog`, para evitar recursão da própria auditoria e manter o registro imutável;
- `Domain` e os mixins de tenancy, por seguirem o contrato estrutural de `django-tenants`.

Novas exceções exigem decisão arquitetural explícita e atualização deste documento.

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

O Soft Delete deverá ser utilizado em todas as entidades de domínio.

- Nenhum registro de domínio poderá ser removido fisicamente do banco de dados.
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
- A Agenda mantém um registro ativo por aluno, turma e data e uma `DiaryAnswer` por item
  aplicável. `DiaryCategory` e `DiaryOption` formam um catálogo unificado, configurável e isolado
  por tenant para as seções Como foi o dia e Alimentação. Itens iniciais e personalizados usam
  a mesma estrutura e não possuem identificadores funcionais fixos.
- Itens configuram seção, ordem, obrigatoriedade, disponibilidade e aplicação aos turnos Manhã,
  Tarde e Integral. Todo item ativo exige ao menos um turno e uma opção disponível; sua última
  opção disponível não pode ser desativada. Itens novos começam indisponíveis, obrigatórios, na
  seção Como foi o dia e aplicáveis aos três turnos.
- Respostas existentes podem continuar ligadas a itens posteriormente indisponíveis. Cada
  `DiaryPublishedEntry` copia seção, nome, rótulo e ordem para `answers_snapshot` no momento da
  publicação, de modo que alterações futuras no catálogo não reescrevem o histórico publicado.
- Café da manhã, Almoço e Café da tarde são categorias iniciais da seção Alimentação; suas
  opções iniciais são Comeu bem, Comeu parcialmente, Não comeu e Não estava presente.
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

## Contas a receber

- `FinancialPlanTemplate` armazena termos reutilizáveis. `StudentFinancialContract` mantém o
  snapshot dos termos, vigência por competência, revisão e estado do contrato.
- `FinancialContractAmendment` é único por contrato e revisão. Um aditivo bloqueia o contrato e
  as cobranças futuras; títulos anteriores, pagos ou parcialmente pagos nunca são reescritos.
- `BillingEntry` aceita origem contratual ou avulsa, guarda competência, vencimento, principal,
  desconto, multa, juros e os respectivos componentes pagos. A unicidade por contrato, parcela e
  revisão torna a materialização idempotente. Atraso e quitação são calculados por expressão no
  banco e propriedades de domínio; o ciclo persistido contém somente `ACTIVE` e `CANCELLED`.
- `PaymentRecord` representa a transação pendente, confirmada ou estornada. `PaymentAllocation`
  distribui uma baixa por cobrança e discrimina principal, multa e juros. A confirmação usa
  `select_for_update` sobre pagamento, alocações e cobranças, revalida o saldo e rejeita excesso.
- `FinancialSequence` é única por tipo e ano dentro do schema do tenant. A emissão de recibo
  incrementa a sequência sob lock pessimista, produzindo `REC-AAAA-NNNNNN`.
- `CollectionReminderPolicy` começa desabilitada. `CollectionReminder` possui constraint de
  deduplicação por cobrança, responsável, canal, regra e data programada.

A migration `financeiro/0001_initial.py` instala diretamente o schema final do contas a receber.
Não há backfill, aliases de modelos ou estados financeiros legados.

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
