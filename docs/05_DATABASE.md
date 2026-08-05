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

### Histórico de migrations em pré-produção

Enquanto não existir ADR declarando a entrada em produção, o histórico do banco é descartável e
representa diretamente o schema atual:

- mudanças em models regeneram todas as migrations próprias e são validadas após reset completo
  de `schools_db`, `schools_test_db`, tenants demo, mídia, cache e filas locais;
- o grafo pode conter mais de um arquivo `initial=True` por app quando o Django precisar quebrar
  dependências circulares; esses arquivos formam uma única instalação inicial, não evolução;
- somente `locations/0002_seed_locations.py` e
  `student_diary/0002_seed_agenda_items.py` podem ser migrations de dados;
- `replaces`, backfills, reconciliações e migrations evolutivas são proibidos e bloqueados pelo
  contrato de pré-produção no CI;
- a configuração do tenant demo pertence a `seed_dev`, não a migration.

A primeira entrada em produção exige novo ADR. Depois desse marco, migrations publicadas serão
imutáveis e qualquer alteração de schema seguirá uma cadeia evolutiva revisada.

- `RoleModuleAccess` é único por papel e chave de módulo em cada schema. Seus quatro booleanos
  representam Visualizar, Cadastrar, Editar e Desativar; mudanças incrementam `version` e são
  auditadas. O papel Administrador não possui linhas nessa tabela.

- Matrículas de professores e alunos são geradas por sequência anual isolada no schema do tenant.
- Solicitações de matrícula usam a mesma sequência tenant-scoped no escopo próprio e recebem
  protocolo `MAT-AAAA-NNNNNN`. `EnrollmentApplication` admite uma única solicitação aberta por
  aluno e ano; `Enrollment` admite um único vínculo ativo por aluno e ano.
- A aprovação é a reserva persistida de vaga. `EnrollmentTransition` registra cada estado sem
  atualização ou remoção; `StudentDocument` guarda o snapshot de `DocumentRequirement` existente
  na abertura, inclusive obrigatoriedade e aceitação de conferência física.
- Transferências e cancelamentos preservam os vínculos acadêmicos encerrados. A matrícula de
  origem passa a `TRANSFERRED`; cancelamento pós-efetivação mantém os registros pedagógicos e
  passa o vínculo final a `CANCELLED`.
- Preferências de e-mail e WhatsApp são armazenadas separadamente e começam desmarcadas.
- Turmas possuem etapa de ensino estruturada, incluindo `OTHER` como opção canônica.
- Turmas usam um catálogo fixo e ordenado de séries compatíveis com a etapa de ensino.
- A Agenda mantém um registro ativo por aluno, turma e data e uma `DiaryAnswer` por item
  aplicável. `DiaryCategory` e `DiaryOption` formam um catálogo unificado, configurável e isolado
  por tenant para as seções Como foi o dia e Alimentação. Itens iniciais e personalizados usam
  a mesma estrutura e não possuem identificadores funcionais fixos.
- Itens configuram seção, ordem, obrigatoriedade, disponibilidade e aplicação aos turnos Manhã e
  Tarde. Em turmas de período Integral, um item só é aplicável quando ambos os turnos estão
  marcados. Todo item ativo exige ao menos um turno e uma opção disponível; sua última opção
  disponível não pode ser desativada. Itens novos começam indisponíveis, obrigatórios, na seção
  Como foi o dia e aplicáveis à Manhã e à Tarde.
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
- Atividades mantêm o workflow de notas `DRAFT` e `LAUNCHED`, com a data do lançamento oficial.
  O estado oficial bloqueia alterações individuais e coletivas até uma reabertura auditada com
  motivo obrigatório.
- Atividades e chamadas aceitam apenas combinações professor–turma–disciplina existentes e
  vigentes na grade horária, inclusive quando o professor é o responsável da turma.
- A grade horária usa `TimeSlot` como período comum da escola, sem dia da semana, vinculado
  obrigatoriamente a Manhã, Tarde ou Noite. Turmas Matutinas, Vespertinas e Noturnas usam somente
  períodos do respectivo turno; turmas Integrais combinam Manhã e Tarde, nunca Noite. A numeração
  do período não é única e a matriz é ordenada cronologicamente. Intervalos iguais ou
  sobrepostos continuam proibidos globalmente, mesmo entre turnos. `Schedule`
  associa turma, professor, disciplina e sala a um período compatível e a um dia letivo de
  segunda a sexta. O turno de uma turma com qualquer versão de grade não pode ser alterado.
  A segunda-feira é o identificador e a data efetiva canônica de toda semana: referências de
  criação, cópia e edição são normalizadas para ela. Cada célula tem vigência inclusiva; editar
  cria uma versão sucessora na segunda escolhida e encerra a anterior no domingo precedente;
  encerrar uma célula a partir de uma semana também a encerra no domingo anterior. Turma,
  professor e sala não podem ter vigências sobrepostas no mesmo dia e período, e o professor
  precisa estar vinculado à disciplina. A cópia de dia valida todas as células e cria o lote
  inteiro em uma única transação.
- Toda atualização de `BaseModel` condiciona a escrita à versão lida e incrementa `version`
  atomicamente. Soft delete, restore e transições seguem a mesma regra; conflitos não
  sobrescrevem o registro atual. Invariantes agregadas usam `select_for_update` em transação.

- Toda migration deverá ser gerada, revisada e validada antes do reset dos ambientes.
- Durante a pré-produção, alterações destrutivas são absorvidas no novo grafo inicial; após o
  go-live, exigirão ADR e estratégia de migração compatível com dados persistentes.
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

O grafo inicial do `financeiro` instala diretamente o schema final do contas a receber. Não há
backfill, aliases de modelos ou estados financeiros legados.

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
