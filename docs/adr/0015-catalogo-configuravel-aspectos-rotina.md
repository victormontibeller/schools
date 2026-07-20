# ADR-0015 — Catálogo configurável de aspectos da rotina

## Status

Superado pela ADR-0017 em 2026-07-19. Os detalhes abaixo registram a decisão intermediária e não
descrevem o contrato atual de dados.

## Contexto

As escolas precisam adequar a Agenda da Educação Infantil às próprias rotinas. O catálogo fixo
de quatro aspectos não permitia cadastrar novas dimensões, ajustar linguagem nem retirar uma
opção de novos preenchimentos sem perder a referência histórica. Publicações já entregues às
famílias também não podem mudar quando o catálogo editável é renomeado.

## Decisão

- Tratar `DiaryCategory` e `DiaryOption` como catálogo tenant-scoped configurável. Os quatro
  aspectos predefinidos e suas opções permanecem como dados iniciais e podem ser editados.
- Manter os códigos estruturados dos itens predefinidos. Aspectos e opções personalizados usam
  `code = null`, inclusive no JSON de publicações.
- Usar disponibilidade reversível em aspectos e opções, sem exclusão física. Aspectos novos
  começam indisponíveis e com resposta obrigatória; nome, ordem e obrigatoriedade são editáveis.
- Exigir ao menos uma opção disponível para ativar um aspecto e impedir a desativação da última
  opção disponível enquanto o aspecto estiver ativo.
- Mostrar somente itens disponíveis para novas escolhas. Respostas persistidas continuam
  visíveis após uma desativação, sem autorizar a mesma escolha em outro registro.
- Copiar nome, rótulo e códigos para `DiaryPublishedEntry.routine_snapshot` a cada publicação.
  Edições posteriores do catálogo não alteram revisões publicadas.
- Proteger leitura, cadastro e edição pela capacidade `diary_configuration`, separada da
  capacidade operacional `student_diary`. Formulários de edição usam `version` para concorrência
  otimista e as escritas permanecem auditadas por `StudentDiaryService`.

## Consequências

Cada escola pode representar sua rotina sem perder o catálogo inicial nem o histórico existente.
O cadastro passa a ocorrer em etapas — aspecto inativo, opções e ativação — evitando colunas sem
resposta possível. Desativação não reduz a rastreabilidade, mas seletores e validações precisam
distinguir escolhas novas de respostas persistidas. Empates de ordem usam nome ou rótulo como
critério determinístico.
