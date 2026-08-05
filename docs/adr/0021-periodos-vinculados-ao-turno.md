# ADR-0021 — Períodos vinculados ao turno da turma

## Status

Aceito em 2026-08-03.

## Contexto

Os períodos da grade eram comuns a todas as turmas do tenant sem indicar se pertenciam à manhã,
à tarde ou à noite. A matriz exibia todos eles para qualquer turma, permitindo combinações
incompatíveis e tornando a configuração operacional ambígua. Apenas filtrar a interface não
protegeria chamadas diretas ao service nem URLs manipuladas.

## Decisão

- `TimeSlot` pertence obrigatoriamente a um único turno: Matutino, Vespertino ou Noturno. Não
  existe período Integral.
- A compatibilidade é Matutino → Manhã, Vespertino → Tarde, Noturno → Noite e Integral →
  Manhã + Tarde. A mesma política é reutilizada pela matriz, pela resolução HTTP e pelos comandos.
- A matriz mostra somente períodos compatíveis e os ordena cronologicamente. `slot_number`
  permanece apenas informativo, sem nova unicidade.
- Intervalos iguais ou cronologicamente sobrepostos permanecem proibidos globalmente, inclusive
  entre turnos, preservando os invariantes de turma, professor e sala baseados no período. No
  PostgreSQL, criação e edição do catálogo são serializadas pelo lock da escola do schema ativo.
- Qualquer histórico de grade torna o turno da turma imutável. Outras propriedades continuam
  editáveis e uma turma sem grade pode mudar de turno. A turma é bloqueada e relida tanto pela
  mudança de turno quanto pela criação da grade, que revalida a compatibilidade depois dos locks.
- O isolamento continua sendo o schema do tenant; não é adicionada FK para escola.
- O catálogo usa a capacidade própria `schedule_configuration`, separada de `schedule`. Somente
  Secretaria e Coordenação são elegíveis; Coordenação recebe leitura, criação e edição por padrão,
  enquanto Secretaria depende de concessão explícita. Professor pode operar a grade no próprio
  escopo sem visualizar nem alterar períodos.
- Conforme o ADR-0019, a mudança entra diretamente na migration inicial de `agenda` e exige reset
  integral de dev/demo, sem default temporário, backfill ou migration evolutiva.

## Consequências

A grade passa a apresentar apenas células que podem ser persistidas, e chamadas diretas também
rejeitam combinações incompatíveis antes de locks, escrita e auditoria. Turmas Integrais usam os
dois conjuntos diurnos sem duplicar períodos. Ambientes locais existentes devem ser descartados e
recriados antes de executar o seed, que classifica os períodos 1–5 como Matutinos e 6–10 como
Vespertinos.
