# ADR-0017 — Catálogo unificado de itens da Agenda

## Status

Aceito em 2026-07-19. Amplia a ADR-0015 e supera a separação de persistência de alimentação
definida na ADR-0008. Revisado em 2026-08-01, antes da existência de dados reais.

## Contexto

Rotina e alimentação precisavam compartilhar o mesmo catálogo configurável. Como o produto ainda
estava em desenvolvimento e possuía somente dados descartáveis, manter modelos, identificadores,
snapshots e migrations intermediários aumentaria a complexidade sem proteger dados reais.

## Decisão

- Usar `DiaryCategory`, `DiaryOption` e `DiaryAnswer` como única persistência de respostas da
  Agenda, tanto para Como foi o dia quanto para Alimentação.
- Adicionar seção e aplicação explícita somente aos turnos Manhã e Tarde em cada categoria. Para
  turmas Integrais, aplicar o item somente quando ambos os turnos estiverem marcados; não existe
  flag ou persistência de Integral independente.
- Manter Café da manhã, Almoço e Café da tarde, com quatro opções de alimentação, como dados
  iniciais tenant-scoped editáveis e sem identidade funcional especial.
- Manter as duas seções separadas na grade e nas publicações, embora compartilhem o mesmo catálogo.
- Preservar respostas já gravadas quando item, turno ou opção deixar de estar disponível, sem
  permitir essa escolha para novos registros.
- Remover identificadores estruturados de categorias e opções; seção, turnos e relacionamentos
  definem o comportamento.
- Guardar toda publicação em um único `answers_snapshot`, contendo seção, nome, rótulo e ordem.
- Regenerar as migrations de `student_diary` com uma inicial limpa e manter a semente permitida por
  tenant com os dois turnos canônicos. Bancos criados com qualquer schema anterior devem ser
  descartados, não migrados.

## Consequências

A escola passa a configurar rotina e alimentação no cadastro Itens da Agenda, com ordem
independente por seção. O formulário diário e o service usam um único payload de respostas, e o
schema nasce sem persistência paralela nem flag Integral. A publicação continua imutável, mas
apenas o formato unificado é suportado. A adoção exige recriar bancos e schemas de desenvolvimento
a partir do zero.
