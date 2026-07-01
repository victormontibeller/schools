# Sprint 18 — Inteligência Artificial

## Objetivo

Incorporar funcionalidades de Inteligência Artificial para apoio pedagógico, análise preditiva e automação de tarefas repetitivas, preservando os princípios de simplicidade e modularidade da plataforma.

## Duração Estimada

2 semanas (ou mais, conforme escopo definido)

---

## Critérios de Aceite

- [ ] Toda funcionalidade de IA deverá ser processada de forma assíncrona via Celery.
- [ ] O sistema deverá identificar alunos em risco de reprovação com base em dados históricos.
- [ ] Geração de relatórios pedagógicos deverá ser assistida por IA.
- [ ] Toda chamada à API de IA deverá ser logada (sem dados sensíveis) e auditada.
- [ ] O sistema deverá funcionar normalmente se a IA estiver indisponível (degradação graceful).

---

## Tarefas

### Módulo `ai/`

- [ ] Criar model `AIRequest` (registro de chamadas à IA):
  - `type` (risk_analysis, report_generation, recommendation, etc.)
  - `input_summary` (resumo do input — sem dados sensíveis)
  - `output_summary` (resumo do output)
  - `model_used`, `tokens_used`, `latency_ms`
  - `status` (pendente, processando, concluído, falhou)
  - FK para `Student` ou `Class` (contexto)
  - Herança de `BaseModel`

- [ ] Implementar `AIService`:
  - `analyze_student_risk(student_id)` — analisa frequência, notas e atividades
  - `generate_pedagogical_report(student_id, period)` — relatório narrativo do desempenho
  - `suggest_activities(class_id, subject_id)` — sugestão de atividades com base no conteúdo
  - `classify_justification(justification_text)` — classifica justificativas de falta automaticamente

### Análise Preditiva de Risco

- [ ] Implementar algoritmo de score de risco por aluno baseado em:
  - Percentual de frequência
  - Média de notas nas últimas atividades
  - Tendência (melhorando ou piorando nas últimas 4 semanas)
  - Histórico de justificativas

- [ ] Integrar score de risco ao Dashboard Escolar
- [ ] Alertas automáticos para alunos com score de risco elevado

### Geração de Relatórios com IA

- [ ] Task Celery `generate_ai_report(student_id, period)`:
  - Coletar dados do aluno: frequência, notas, atividades, observações
  - Enviar para API de LLM (OpenAI, Anthropic ou modelo local via Ollama)
  - Armazenar relatório gerado como `ActivityReport`
  - Notificar coordenador quando o relatório estiver pronto

### Celery Tasks

- [ ] Task `run_weekly_risk_analysis`: executada toda semana, atualiza score de todos os alunos
- [ ] Task `generate_ai_report`: sob demanda, gera relatório para um aluno específico
- [ ] Task `process_ai_suggestions`: gera sugestões de atividades para turmas sem atividades na semana

### Frontend

- [ ] Widget "Alunos em Risco (IA)" no Dashboard Escolar com score e tendência
- [ ] Botão "Gerar Relatório IA" na tela do aluno (assíncrono com indicador de progresso)
- [ ] Tela de histórico de relatórios gerados por IA
- [ ] Tela de sugestões de atividades por IA para professores

### Segurança e Privacidade

- [ ] Nenhum dado identificável (nome, CPF, e-mail) deverá ser enviado à API externa de IA
- [ ] Dados enviados deverão ser apenas métricas numéricas e anonimizadas
- [ ] Toda chamada à API de IA deverá ser logada em `AIRequest`
- [ ] Configuração da API key via variável de ambiente, nunca em código

---

## Dependências

- Sprints 00-09 concluídas
- Definição do provedor de IA (OpenAI, Anthropic, Ollama, etc.)
- Aprovação da equipe sobre dados enviados à IA (LGPD)

---

## Definition of Done

- [ ] Todos os critérios de aceite validados
- [ ] Sistema funciona normalmente quando a API de IA está indisponível
- [ ] Análise de risco com testes unitários usando dados históricos simulados
- [ ] Conformidade com LGPD validada: nenhum dado pessoal enviado à IA
- [ ] `AIRequest` com auditoria completa
- [ ] Pipeline CI passando
