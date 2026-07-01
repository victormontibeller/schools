# Sprint 17 — Financeiro Escolar

## Objetivo

Disponibilizar um nucleo financeiro escolar para emissao de cobrancas, acompanhamento de inadimplencia, conciliacao basica e visao operacional de receitas.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] Sistema devera registrar planos, mensalidades e descontos por aluno/turma.
- [ ] Cobrancas deverao possuir status: aberto, pago, vencido, cancelado.
- [ ] Inadimplencia devera ser visivel por faixa de atraso.
- [ ] Baixa manual e conciliacao basica deverao estar disponiveis para secretaria.
- [ ] Relatorio mensal de receita prevista x recebida devera ser gerado.

---

## Tarefas

### Modelagem e Regras

- [ ] Criar models financeiros basicos:
  - FinancialPlan
  - BillingEntry
  - PaymentRecord
- [ ] Implementar FinanceService com regras de geracao de cobrancas.
- [ ] Implementar politicas de multa e juros configuraveis.

### Operacao Financeira

- [ ] Gerar cobrancas em lote por turma e competencia.
- [ ] Registrar pagamento parcial e pagamento total.
- [ ] Implementar renegociacao simples com novo vencimento.

### Relatorios e Dashboard

- [ ] Criar KPIs financeiros no dashboard escolar:
  - total em aberto
  - total vencido
  - recebido no mes
- [ ] Relatorio de inadimplencia por faixa (1-30, 31-60, 60+).

### Integracao Inicial

- [ ] Preparar camada de adaptador para gateway de pagamento (sem acoplamento direto).
- [ ] Garantir fallback para operacao 100% manual.

---

## Dependencias

- Sprints 03, 04 e 08 concluidas
- Definicao de politica financeira da escola

---

## Definition of Done

- [ ] Criterios de aceite validados
- [ ] Fluxos financeiros cobertos por testes de servico
- [ ] Relatorios financeiros validados com dados de exemplo
- [ ] Auditoria e logs estruturados em operacoes de escrita
