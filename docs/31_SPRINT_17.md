# Sprint 17 — Financeiro Escolar

> **Documento histórico.** Em caso de divergência, prevalecem os documentos normativos em `docs/`.

## Objetivo

Disponibilizar um nucleo financeiro escolar para emissao de cobrancas, acompanhamento de inadimplencia, conciliacao basica e visao operacional de receitas.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] Sistema devera registrar planos, mensalidades e descontos por aluno/turma.
- [x] Cobrancas deverao possuir status: aberto, pago, vencido, cancelado.
- [x] Inadimplencia devera ser visivel por faixa de atraso.
- [x] Baixa manual e conciliacao basica deverao estar disponiveis para secretaria.
- [x] Relatorio mensal de receita prevista x recebida devera ser gerado.

---

## Tarefas

### Modelagem e Regras

- [x] Criar models financeiros basicos:
  - FinancialPlan
  - BillingEntry
  - PaymentRecord
- [x] Implementar FinanceService com regras de geracao de cobrancas.
- [x] Implementar politicas de multa e juros configuraveis.

### Operacao Financeira

- [x] Gerar cobrancas em lote por turma e competencia.
- [x] Registrar pagamento parcial e pagamento total.
- [x] Implementar renegociacao simples com novo vencimento.

### Relatorios e Dashboard

- [x] Criar KPIs financeiros no dashboard escolar:
  - total em aberto
  - total vencido
  - recebido no mes
- [x] Relatorio de inadimplencia por faixa (1-30, 31-60, 60+).

### Integracao Inicial

- [x] Preparar camada de adaptador para gateway de pagamento (sem acoplamento direto).
- [x] Garantir fallback para operacao 100% manual.

---

## Dependencias

- Sprints 03, 04 e 08 concluidas
- Definicao de politica financeira da escola

---

## Definition of Done

- [x] Criterios de aceite validados
- [x] Fluxos financeiros cobertos por testes de servico
- [x] Relatorios financeiros validados com dados de exemplo
- [x] Auditoria e logs estruturados em operacoes de escrita
