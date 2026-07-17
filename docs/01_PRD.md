# PRD

## Objetivo
Sistema SaaS para escolas.

## Módulos
- Autenticação
- Escolas
- Professores
- Coordenadores
- Alunos
- Responsáveis
- Turmas
- Salas
- Agenda
- Atividades
- Frequência
- Calendário
- Comunicados
- Notificações
- Dashboard
- Auditoria

## Rotina docente

- Chamadas registram presença individual e conteúdo ministrado por aula.
- Atividades podem ser individuais ou em grupo, mantendo nota e feedback finais por aluno.
- A série da turma é selecionada em catálogo fixo e validada conforme a etapa de ensino.
- Turmas da Educação Infantil possuem Agenda diária unidirecional com os aspectos fixos Humor,
  Descanso, Evacuação e Participação, alimentação conforme o turno e consulta pelos responsáveis
  ativos que mantêm guarda.
- A Agenda da turma é salva em uma única operação atômica; todas as crianças ativas e todos os
  aspectos habilitados devem estar válidos.
- O professor envia a folha para revisão. Somente coordenação ou administração publica ou devolve
  para correção; professores não publicam diretamente.
- O envio para revisão cria notificação interna e e-mail genérico para revisores ativos, com link
  autenticado para a turma/data. O dashboard mantém até dez pendências recentes visíveis.
- Cada publicação cria uma revisão e snapshots imutáveis por aluno. Uma correção reabre a folha e
  cria nova revisão sem alterar o histórico anterior.
- A abertura autenticada registra primeira e última visualização. Não existem respostas, reações,
  confirmações nem mensagens de responsáveis.
- A publicação gera notificação interna e, conforme consentimento, e-mail sem nome do aluno ou
  conteúdo da agenda no texto externo. Web Push está adiado.
- E-mails transacionais usam a Resend API com uma chave global da plataforma em variável de
  ambiente e remetente verificado por escola. Webhooks assinados atualizam a situação da entrega.
- A aplicação permanece instalável como PWA e oferece fallback offline genérico, sem notificações
  Push e sem cache de conteúdo autenticado.
- O acesso inicial do responsável usa convite assinado válido por sete dias e de uso único. A
  remoção da guarda revoga imediatamente a consulta às publicações do aluno.
- A primeira ativação é controlada por
  `School.settings["student_diary"]["interactive_enabled"]` e fica habilitada somente na escola de
  demonstração até a validação do fluxo.
- Administração escolar tem acesso irrestrito aos módulos dentro do tenant atual, sem ampliar
  acesso à plataforma ou a outras escolas.

## Requisitos obrigatórios
- Multi-tenant.
- Auditoria completa.
- Soft delete.
- Versionamento.
- Logs estruturados.
- Observabilidade.
- API REST interna.

## Indicadores da Agenda

- Visualização da revisão mais recente em até 24 horas entre responsáveis notificados.
- Dias letivos com publicação por turma elegível da Educação Infantil.
- Tempo mediano entre envio para revisão e publicação.
- Indicadores auxiliares: ativação dos responsáveis, adesão ao Push, falhas de entrega,
  republicações e incidentes de acesso indevido.
- As primeiras quatro semanas de uso formam a linha de base antes da definição de metas.
