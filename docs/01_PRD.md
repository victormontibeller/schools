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
- Turmas da Educação Infantil possuem Agenda diária com os aspectos fixos Humor, Descanso,
  Evacuação e Participação, alimentação conforme o turno e consulta pelos responsáveis
  vinculados.
- A Agenda da turma é salva em uma única operação atômica; todas as crianças ativas e todos os
  aspectos habilitados devem estar válidos.
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
