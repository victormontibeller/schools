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

## Estabilização de integridade — 17/09/2026

- Cada cobrança copia multa e juros diários não negativos dos termos que a originaram. A apuração
  usa exclusivamente esses snapshots; aditivos futuros nunca mudam encargos históricos.
- Materialização individual e por turma compartilham uma rotina sob lock do contrato e reconhecem
  títulos em qualquer revisão, inclusive cancelados/quitados. Lacuna anterior ao último aditivo
  produz erro explícito, sem usar termos novos para reconstruir passado.
- Aditivos têm vigências não decrescentes e não alteram títulos de renegociação. O vínculo
  `cancelling_amendment` distingue supressão contratual de cancelamento manual: expansão explícita
  do calendário pode reintroduzir parcelas suprimidas, preservando cancelamentos e renegociações.
- Renegociação contratual bloqueia contrato antes da cobrança e serializa a numeração. Avulsas
  mantêm `installment_number=None`; substitutas conservam as taxas da origem.
- Estorno de título cancelado por renegociação cria uma cobrança ADJUSTMENT avulsa por alocação,
  ligada por `reversal_allocation` único. Principal, multa, juros e competência são preservados
  separadamente. O vencimento de recomposição é informado, atual ou futuro, sugerindo hoje na UI.
  O ajuste tem taxas zero; não altera sucessoras, mesmo quitadas ou renegociadas novamente.
- O pagamento torna-se estornado e os componentes pagos da original são reduzidos, mantendo seu
  estado CANCELLED e histórico auditável. Saldos cancelados não integram o total exigível do
  extrato. Cancelamentos sem sucessora de renegociação recusam estorno explicitamente.
- Estorno e recomposição, inclusive auditoria, compartilham a mesma transação e locks ordenados.
  Repetição após sucesso é recusada sem produzir outro ajuste. Falha de auditoria reverte o lote.

O grafo inicial completo é regenerado pelo Django. Reset dev/demo e validações PostgreSQL fazem
parte da integração; nenhuma migration evolutiva ou reconciliação de dados antigos é mantida.
