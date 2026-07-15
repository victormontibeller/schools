# ADR-0007 — Matrículas automáticas e convite de professores

## Status

Aceito. Renumerado em 2026-07-13 para remover colisão com o ADR-0006.

## Contexto

Matrículas eram digitadas manualmente e professores dependiam da seleção prévia de um usuário.

## Decisão

- Matrículas são geradas por tenant, tipo e ano no formato `PRO-AAAA-NNNNNN` ou
  `ALU-AAAA-NNNNNN`.
- Um contador persistido é incrementado com bloqueio transacional; constraints únicas continuam
  protegendo o identificador final.
- Importações de alunos podem preservar matrículas legadas explicitamente informadas.
- O cadastro de professor recebe o e-mail diretamente. Contas novas permanecem inativas, com
  senha inutilizável, até consumirem um convite assinado de uso único e validade de sete dias.
- Convites por e-mail só são enviados quando o professor consentiu com esse canal.

## Consequências

Matrículas deixam de ser editáveis, contas pendentes não autenticam e a sequência anual pode ter
lacunas quando uma transação posterior ao incremento falha, sem reutilização de identificadores.
