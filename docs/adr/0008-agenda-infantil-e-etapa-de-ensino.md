# ADR-0008 — Agenda infantil e etapa de ensino estruturada

## Status

Aceito em 2026-07-12. Atualizado e renumerado em 2026-07-13. Parcialmente superado em
2026-07-17 pela ADR-0015 quanto à decisão de manter aspectos e opções fixos.

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
- Adotar inicialmente quatro aspectos estruturados: Humor, Descanso, Evacuação e Participação.
  A restrição posterior a nomes e opções fixos foi superada pela ADR-0015.
- Preservar `DiaryCategory` e `DiaryOption` para compatibilidade. A ADR-0015 passou a utilizá-los
  também para itens personalizados, mantendo o histórico de respostas.
- Salvar toda a turma em transação única e permitir responsável pedagógico nulo quando o autor
  real for administração ou coordenação.
- Reconhecer o papel `ADMIN` como irrestrito apenas dentro do schema da própria escola; acesso à
  plataforma, suporte e outros tenants permanece separado.

## Consequências

As regras de alimentação permanecem estruturadas por turno e incluem o estado `NOT_PRESENT`.
Turmas legadas precisam ser classificadas explicitamente antes de usar a Agenda. Novas gravações
de turma aceitam somente combinações de etapa e série previstas no catálogo pedagógico comum a
todos os tenants. As consequências do catálogo configurável estão na ADR-0015.
