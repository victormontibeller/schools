# ADR-0018 — Contratos financeiros, alocações e bases de relatório

## Status

Aceito em 2026-07-19.

## Contexto

O MVP financeiro vinculava cada pagamento a uma única cobrança, persistia o estado Vencido e
misturava competência da cobrança com data do recebimento. Planos ativos podiam mudar sem uma
revisão explícita, o que impedia reconstruir com segurança os termos que originaram cada título.
Como o módulo ainda continha somente dados de desenvolvimento, o domínio pôde adotar diretamente
os nomes e estados definitivos.

## Decisão

- Tratar o vínculo individual como `StudentFinancialContract`, sem alias ou tabela intermediária.
- Copiar os termos do modelo para o contrato e materializar toda a agenda na ativação. Alterações
  de contrato ativo usam `FinancialContractAmendment`, têm vigência futura e cancelam/substituem
  apenas títulos futuros sem pagamento.
- Manter `PaymentRecord` como transação imutável e introduzir `PaymentAllocation`. A baixa nasce
  pendente; a confirmação bloqueia pagamento, cobranças e sequência, apura encargos e amortiza
  multa, juros e principal nessa ordem.
- Representar estorno no mesmo registro, com motivo, autoria e data. A leitura de caixa considera
  uma saída na data do estorno; nenhum pagamento ou recibo é apagado.
- Persistir em `BillingEntry` somente o ciclo `ACTIVE` ou `CANCELLED`; derivar quitação e atraso
  do saldo e do vencimento, sem rotina periódica.
- Separar relatórios de competência, baseados em `BillingEntry.competency`, e caixa, baseado em
  `PaymentRecord.paid_date` e `reversed_at`.
- Emitir recibos por uma sequência anual tenant-scoped sob `select_for_update`.

## Instalação

Uma única migration inicial cria diretamente contratos, cobranças, pagamentos, alocações,
sequências, aditivos e lembretes. Os bancos de desenvolvimento e teste são recriados, pois não há
instalação externa nem dado financeiro a preservar. Somente URLs de Contratos são públicas.

## Consequências

Pagamentos múltiplos, parciais e concorrentes passam a ter uma trilha auditável, e competência e
caixa deixam de produzir números ambíguos. A confirmação exige mais locks e consultas, e o domínio
mantém um único vocabulário de domínio e não admite estados persistidos de quitação ou atraso.
