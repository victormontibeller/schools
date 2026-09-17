# Multi-Tenant

> **Estado em 2026-07-13:** isolamento por schema, resolução por host, catálogo público,
> validação de domínio e contexto Celery estão implementados. Apenas subdomínios gerenciados
> são suportados em produção nesta etapa.

## Estratégia

O sistema deverá utilizar **isolamento por Schema PostgreSQL**.

Cada escola (Tenant) deverá possuir seu próprio Schema PostgreSQL isolado.
Dentro de um mesmo tenant poderão existir múltiplas unidades de negócio
ou empresas operacionais, sem criar novos schemas.

A biblioteca **django-tenants** deverá ser utilizada para gerenciar o roteamento entre schemas.

---

## Regras Invioláveis

- É proibido compartilhar dados entre Tenants.
- Todo acesso ao banco de dados deverá ocorrer dentro do contexto do Tenant ativo.
- Nenhum módulo poderá acessar dados de outro Tenant diretamente.
- Toda requisição deverá identificar automaticamente o Tenant ativo.
- O Tenant deverá ser resolvido pelo domínio da requisição.

---

## Resolução do Tenant

O Tenant deverá ser resolvido automaticamente via domínio:

```
escola-a.plataforma.com  →  Schema: escola_a
escola-b.plataforma.com  →  Schema: escola_b
```

Um Middleware dedicado deverá identificar e ativar o Tenant em cada requisição. Caso o Tenant não seja identificado, a requisição deverá ser rejeitada.

Em produção, `PLATFORM_DOMAIN` identifica o schema público e cada escola usa exatamente um nível
sob `TENANT_BASE_DOMAIN`, por exemplo `escola.<base>`. Hosts são normalizados em minúsculas, sem
porta, caminho ou ponto final; hosts desconhecidos ou fora da base são recusados. Somente
`PLATFORM_DOMAIN` e `TENANT_BASE_DOMAIN` compõem a política de hosts.

DNS deve publicar o host da plataforma e o wildcard `*.<base>`. O certificado wildcard é emitido
por ACME DNS-01, com credencial do provedor armazenada como secret. Veja
`docs/36_PRODUCTION_RUNBOOK.md`.

---

## Estrutura dos Schemas

| Schema | Conteúdo |
|---|---|
| `public` | Tabelas compartilhadas: lista de tenants, planos, configurações globais |
| `<tenant_slug>` | Todos os dados da escola: usuários, alunos, professores, turmas, etc. |

Auth, sessions e `CustomUser` possuem tabelas independentes em cada schema. O `public` mantém
somente operadores da plataforma. Trocar o domínio troca a tabela de usuários consultada; uma
sessão escolar não concede identidade em outra escola.

A ficha de Escola resolve o cadastro público pelo schema da conexão ativa. Os comandos de
edição de dados e logotipo recusam identificadores de outra escola antes de escrever ou
auditar. Somente o perfil de testes SQLite (`TESTING`, ADR-0001), sem schemas, usa a primeira
escola da fixture como contexto.

Ao editar a própria Escola a partir de um tenant PostgreSQL, `School.updated_by` fica nulo:
essa FK pertence ao catálogo `public` e não pode referenciar um usuário privado da escola.
O autor autenticado permanece obrigatório na autorização e no `AuditLog` do tenant, na mesma
transação da alteração. `created_by` é preservado; não se copia nem se substitui o usuário por
um operador público. Operações no schema `public` e testes SQLite mantêm a atribuição normal
de `updated_by` ao ator do respectivo schema.

---

## Ciclo de Vida do Tenant

1. Nova escola é cadastrada na plataforma.
2. Um novo Schema PostgreSQL é criado automaticamente via django-tenants.
3. As migrations são aplicadas no novo Schema.
4. O domínio é configurado e o Tenant fica ativo.
5. Em caso de desativação, o Schema é preservado e apenas o Tenant é marcado como inativo.

---

## Tarefas Celery e Multi-Tenant

Toda tarefa Celery deverá receber o identificador do Tenant e ativar o Schema correto no início da execução.

Nenhuma tarefa assíncrona poderá ser executada sem o contexto do Tenant definido.

O correlation ID é propagado automaticamente nos headers Celery. O schema continua argumento
explícito e obrigatório das tarefas tenant-scoped; sinais apenas transportam observabilidade,
não inferem autorização nem tenant.

Publicações comuns usam os helpers resilientes de `base.events`, capturam o schema explicitamente
e são registradas somente após commit. O dispatcher diário da régua financeira consulta o catálogo
público, exclui `public` e publica uma tarefa isolada por escola ativa; falha em um schema não
interrompe os seguintes. O Beat o executa às 08:00 em `America/Sao_Paulo`. A recuperação de
lembretes de matrícula mantém sua reconciliação especializada; expiração DEMO e dashboards não
possuem agendamento neste estágio.

Toda chave Redis que represente dados escolares deve começar com `tenant:<schema>:`.
