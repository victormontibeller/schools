# ADR-0008 — Agenda infantil e etapa de ensino estruturada

## Status

Aceito em 2026-07-12. Atualizado e renumerado em 2026-07-13.

## Contexto

O app `agenda` representa a grade horária. A rotina diária da Educação Infantil possui regras,
permissões e ciclo de dados distintos e não pode depender de inferência pelo texto livre da série.

## Decisão

- Criar o app tenant-scoped `student_diary` para aspectos da rotina, respostas, alimentação e
  registros diários por criança.
- Adicionar `Class.education_stage`, com `OTHER` para dados existentes e habilitação da agenda
  apenas em `EARLY_CHILDHOOD`.
- Estruturar `Class.grade` como catálogo fixo por etapa, sem entidade configurável, normalizando
  apenas grafias legadas reconhecidas e exigindo correção manual das demais.
- Manter o app `agenda` exclusivamente responsável por grade horária.
- Adotar quatro aspectos estruturados: Humor, Descanso, Evacuação e Participação, com opções
  fixas. A escola controla somente a ativação de cada aspecto.
- Preservar `DiaryCategory` e `DiaryOption` para compatibilidade: registros livres anteriores não
  aparecem em novos preenchimentos, mas suas respostas continuam no histórico.
- Salvar toda a turma em transação única e permitir responsável pedagógico nulo quando o autor
  real for administração ou coordenação.
- Reconhecer o papel `ADMIN` como irrestrito apenas dentro do schema da própria escola; acesso à
  plataforma, suporte e outros tenants permanece separado.

## Consequências

A escola não cria nomenclaturas próprias para a rotina, reduzindo ambiguidade entre professores
e responsáveis. As regras de alimentação permanecem estruturadas por turno e incluem o estado
`NOT_PRESENT`. Turmas legadas precisam ser classificadas explicitamente antes de usar a Agenda.
Novas gravações de turma aceitam somente combinações de etapa e série previstas no catálogo
pedagógico comum a todos os tenants.
