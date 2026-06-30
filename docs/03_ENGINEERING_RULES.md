# Regras de Engenharia

## Princípio

Todo código deverá ser escrito como se fosse ser mantido por outra pessoa no futuro. Clareza, previsibilidade e consistência deverão ser priorizadas em todas as decisões.

---

## É Obrigatório

### Qualidade de Código

- Todo código Python deverá ser formatado com **Black**.
- Todo código Python deverá ser verificado com **Ruff** (linting e import sorting).
- Todo código Python deverá seguir **PEP 8**.
- Toda função e método público deverá possuir **type hints** completos.
- Todo módulo, classe e função pública deverá possuir **docstring**.

### Arquitetura

- Toda regra de negócio deverá residir na camada `services`.
- Toda consulta complexa deverá residir na camada `selectors`.
- Toda operação de escrita deverá passar por um `service`.
- O princípio **DRY** deverá ser aplicado: nenhum trecho de lógica poderá ser duplicado.
- Os princípios **SOLID** deverão guiar toda decisão de design.

### Observabilidade

- Todo `service` deverá emitir logs estruturados em JSON.
- Toda operação crítica deverá ser auditada.
- Todo erro deverá ser logado com contexto suficiente para diagnóstico.

### Testes

- Toda regra de negócio crítica deverá possuir testes unitários.
- Todo `service` deverá ser testável de forma isolada (sem dependência de infraestrutura).
- Testes de integração deverão cobrir fluxos críticos de ponta a ponta.

### Decisões Arquiteturais

- Toda decisão arquitetural significativa deverá ser documentada como **ADR** (Architecture Decision Record) na pasta `docs/adr/`.
- Todo provedor de serviço externo (e-mail, WhatsApp, SMS, push) deverá ser abstraído atrás de uma interface **SDK** (`channels/BaseChannel`), nunca chamado diretamente. Ver ADR-0005.
- Toda lógica de transporte de mensagens (renderização de template, log de entrega, retry) deverá ser centralizada no **MessageTransport**, não duplicada em tasks.
- Rotinas genéricas reutilizáveis (validação de campos obrigatórios, soft-delete) deverão residir no **BaseService**. Ver `docs/10_CODING_STANDARDS.md` — Catálogo de Rotinas Genéricas.

---

## É Proibido

| Proibido | Motivo |
|---|---|
| `print()` para logging | Usar `logging` com saída JSON estruturada |
| SQL direto nas Views | Usar ORM ou Repositories |
| Regras de negócio nas Views | Views são apenas orquestração |
| Duplicação de código | Extrair para `base/` helpers ou SDK channels |
| Dependências circulares entre módulos | Redesenhar via interfaces ou eventos |
| Ignorar o contexto do Tenant | Toda query deve operar no schema correto |
| Ignorar auditoria em operações de escrita | Usar `BaseService` que já audita automaticamente |
| Secrets em código fonte | Usar variáveis de ambiente |
| Migrations sem revisão | Toda migration deve ser revisada antes de aplicar |
| Chamada direta a API de terceiros em tasks | Usar `channels/` SDK — `BaseChannel.send()` |

---

## Fluxo de Desenvolvimento

1. Escrever o teste antes ou junto com a implementação.
2. Implementar a lógica na camada correta (`service`, `selector`, etc.).
3. Rodar `black .` e `ruff check .` antes de qualquer commit.
4. Garantir que nenhum teste esteja quebrado.
5. Atualizar documentação se a decisão for arquitetural.
6. Criar ADR se necessário.
