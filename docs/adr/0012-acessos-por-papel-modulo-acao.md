# ADR-0012 — Acessos por papel, módulo e ação

## Status

Aceito e implementado em 2026-07-13.

## Contexto

A autorização escolar estava duplicada entre listas estáticas de módulos e `auth.Permission`.
Além de divergirem, os defaults eram reaplicados por `post_migrate`, impedindo personalização
segura por tenant e tratando todas as operações de um módulo como equivalentes.

## Decisão

- `RoleModuleAccess` é a fonte persistida por papel, módulo e ação: visualizar, cadastrar,
  editar e desativar.
- Administrador é irrestrito e não possui linha configurável; permissões individuais e grupos
  do Django não ampliam acessos do produto.
- O catálogo em código define módulos, departamentos, ações suportadas, papéis elegíveis,
  defaults e contratos de escopo para Professor e Responsável.
- Middleware, services, navegação e templates consultam `core.permissions.can_access`.
- Chaves desconhecidas são negadas. Novos módulos herdam defaults do departamento somente ao
  serem registrados; `post_migrate` cria ausências sem sobrescrever escolhas existentes.
- Usuários, Escola, Unidades e a Central de Acessos permanecem exclusivamente administrativos.
- Calendário e eventos permanecem em `academic_calendar`; Feriados e Anos Letivos possuem as
  capacidades independentes `holidays` e `academic_years`, configuráveis para Secretaria,
  Coordenação e Financeiro somente com visualizar, cadastrar e editar.
- A Central apresenta módulos nas linhas e os cinco papéis configuráveis nas colunas. Cada célula
  envia um conjunto de ações e a matriz completa é validada e persistida em uma única transação.
- `get_full_matrix()` e `update_access_matrix()` são as únicas interfaces públicas da Central;
  não há leitura ou atualização isolada por papel.

## Consequências

Alterações feitas em Administração → Acessos valem imediatamente no tenant e são auditadas com
concorrência otimista. Toda nova tela e mutação precisa resolver um módulo e uma das quatro ações;
Professor e Responsável continuam sujeitos aos filtros de objetos vinculados.

O formulário envia a versão de cada papel. Todas são verificadas antes da primeira escrita, de
modo que um conflito impede alterações parciais. Essa representação visual não altera o modelo
persistido `RoleModuleAccess` nem exige migração de schema.

A separação posterior de Feriados e Anos Letivos não alterou o schema. Uma migração de dados
criou somente os registros ausentes copiando as ações equivalentes de `academic_calendar`, sem
copiar Desativar nem sobrescrever configurações já existentes.
