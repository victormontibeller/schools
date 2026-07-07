# Multi-Tenant

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

---

## Estrutura dos Schemas

| Schema | Conteúdo |
|---|---|
| `public` | Tabelas compartilhadas: lista de tenants, planos, configurações globais |
| `<tenant_slug>` | Todos os dados da escola: usuários, alunos, professores, turmas, etc. |

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
