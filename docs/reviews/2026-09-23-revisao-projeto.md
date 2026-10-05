# Revisão do projeto — 23/09/2026

Base Git: `ba0ea64`, incluindo o conjunto de alterações locais preexistentes. Revisão somente leitura de produto, com reproduções em banco SQLite em memória. Esta revisão não atribui os problemas exclusivamente ao diff: os seis achados abaixo já estão presentes na base ou em caminhos preservados pelas alterações atuais.

## Decisão

Corrigir os três achados P1 de autorização e integridade financeira antes de usar os fluxos afetados com dados reais. Tratar também os três achados P2 de relatório, edição concorrente e ausência de perfil docente. A aprovação das verificações existentes não cobre os cenários adicionais reproduzidos nesta revisão.

Não foi demonstrado acesso entre tenants nem incidente em produção. Os problemas de autorização reproduzidos ocorrem entre objetos da mesma escola.

## Achados confirmados

### 1. P1 — Professor consulta alunos em risco de turma fora de seu vínculo

- Local: `attendance/views.py:240-246`.
- O endpoint `students_at_risk` lista todas as turmas e aceita `class_obj` na query string. A consulta não aplica o escopo docente. O middleware verifica o parâmetro de rota `class_id`, que não está presente neste caminho.
- Reprodução HTTP com professor sem vínculo com a turma: o seletor de autorização retorna falso, mas a resposta é 200 e contém o aluno de outra turma (`scope=False status=200 student_exposed=True`). A lista global de turmas permite selecionar o objeto diretamente.
- Impacto: exposição de identidade e frequência de alunos fora da atribuição docente.
- Correção sugerida: filtrar as opções pelo escopo do usuário e verificar o objeto selecionado antes de carregar o relatório. Cobrir GET normal e turma enviada diretamente pela query string.

### 2. P1 — Desativar o perfil do professor não revoga acesso a suas chamadas e atividades

- Local: `core/access_selectors.py:146-150`; a mesma lacuna aparece em `teacher_can_access_activity`, linhas 128-132.
- Os seletores conferem apenas a autoria (`teacher__user_id`), sem exigir perfil docente ativo/não excluído. A operação normal `TeacherService.deactivate_teacher` desativa o perfil, preservando a conta de usuário.
- Reprodução HTTP depois da exclusão lógica do perfil: leitura da chamada retorna 200 com dados do aluno; leitura da atividade retorna 200; POST na chamada é aceito e persiste a mudança para PRESENT. O escopo de aluno do mesmo professor já retorna falso.
- Impacto: a revogação fica incompleta e o professor mantém capacidade de ler e alterar dados pela URL conhecida.
- Correção sugerida: exigir perfil docente ativo em todos os seletores de autoria e validar a revogação tanto em HTTP quanto nos services. Não confundir acesso ao histórico por professor ativo com acesso por perfil desativado.

### 3. P1 — Pagamento pontual lançado depois da apuração de encargos deixa dívida indevida

- Local: `financeiro/services/billings.py:175-178`, com consumo em `financeiro/services/payments.py:144-165`.
- `_assess_late_charges` retorna quando a data do pagamento é anterior ou igual ao vencimento, antes de conferir a data da última apuração. Multa e juros já apurados permanecem no título e são consumidos primeiro pela confirmação.
- Reprodução pelos services: título de R$ 100 vencendo em 10/01; multa de R$ 2 e juros de R$ 1 apurados até 20/01; registro posterior de pagamento de R$ 100 com data efetiva 10/01. Resultado: pagamento CONFIRMED, principal pago R$ 97 e saldo R$ 3.
- Impacto: pagamento integral no prazo não quita a obrigação e pode alimentar cobrança/inadimplência indevida.
- Correção sugerida: aplicar a guarda cronológica antes desse retorno ou implementar recomposição consistente dos encargos conforme a política do domínio. Acrescentar teste para pagamento no vencimento e anterior ao vencimento após apuração posterior.

### 4. P2 — Renegociação faz recebimento confirmado desaparecer do relatório de competência

- Local: `financeiro/report_selectors.py:70-83`.
- `competence_report` exclui títulos CANCELLED antes de somar `paid_value`. A renegociação cancela o título de origem, mas preserva legitimamente seus pagamentos parciais e gera novos títulos apenas para o saldo restante.
- Reprodução pelos services/selectors: cobrança de R$ 100 com pagamento confirmado de R$ 40; após renegociar o saldo, o recebido por competência cai de R$ 40 para R$ 0. O pagamento continua CONFIRMED e a entrada de caixa continua R$ 40.
- Impacto: subavaliação dos recebimentos e divergência entre relatórios de competência e caixa sem estorno real.
- Correção sugerida: separar cálculo de dívida exigível de recebimentos históricos, utilizando as alocações confirmadas e o tratamento de estornos. Não resolver apenas incluindo todo o principal cancelado, pois isso pode duplicar a obrigação renegociada.

### 5. P2 — Formulário antigo de chamada sobrescreve presença e observação sem conflito

- Local: `attendance/services.py:214-228`; integração em `attendance/views.py:174-178`.
- O formulário não envia versão da chamada/entradas. O service relê cada entrada no momento da gravação, portanto o controle de versão de `BaseModel.save()` protege apenas alterações concorrentes após essa leitura, sem detectar uma tela aberta anteriormente.
- Reprodução: guardar um payload antigo PRESENT/sem observação; salvar ABSENT/com observação; reenviar o payload antigo. Resultado observado: `after_first_save ABSENT True 1`, seguido de `after_stale_save PRESENT False 2`, sem erro.
- Impacto: duas abas ou dois operadores podem apagar silenciosamente as correções um do outro.
- Correção sugerida: transportar as versões vistas pelo cliente e validar o lote inteiro atomicamente, preservando todos os dados quando houver conflito.

### 6. P2 — Conta com papel Professor sem perfil recebe a listagem geral de chamadas

- Local: `attendance/views.py:75-78`, com interpretação do filtro em `attendance/selectors.py:31-35`.
- Quando o usuário TEACHER não tem `teacher_profile`, a view passa `teacher_id=None`. O selector interpreta esse valor como ausência de filtro, retornando chamadas de todos os docentes da escola.
- O estado é alcançável pela criação de conta com papel Professor via `AccountService.create_user`, sem criação automática de perfil docente.
- Reprodução HTTP no ambiente temporário: `MISSING_PROFILE status=200 outside_class_rendered=True`.
- Correção sugerida: negar acesso ou retornar lista vazia para professor sem perfil válido; reservar ausência de filtro para os papéis autorizados a consultar a escola inteira. Cobrir usuário sem perfil e perfil desativado.

## Verificações

- Ruff: passou.
- Black: passou; 503 arquivos sem alteração necessária.
- Checkers de importação, comandos de service, UI e política pré-produção: passaram; grafo com 30 migrations.
- `git diff --check`: passou.
- A `.venv` existente usa Python 3.14.5/Django 5.2.16 e não tem WhiteNoise; a suíte nela parou na coleta. `pip check` sozinho não detectou essa ausência porque o ambiente não refletia os requisitos do projeto.
- Foi criado `/tmp/schools-review-venv`, com Python 3.13.14 e dependências instaladas de `requirements-dev.lock` com verificação de hashes; Django 5.2.17 e `pip check` aprovados. A `.venv` do projeto foi preservada.
- Reproduções financeiras, de chamada e HTTP foram executadas nesse ambiente temporário. Os testes HTTP de autorização mantiveram a cadeia normal de middlewares, inclusive WhiteNoise, usando o perfil SQLite.
- Suíte geral: **1.503 testes passaram**, 71 desmarcados (`tenant`/`ui`), em 275,20 segundos. Comando: `/tmp/schools-review-venv/bin/pytest -q --tb=short`. Log: `/tmp/schools-review-pytest-py313.log`. Cobertura não foi recalculada nesta rodada.

## Limites e acompanhamento

- Não foram reexecutados Chromium, testes PostgreSQL tenant-scoped, auditoria online de vulnerabilidades, build/scan da imagem Linux ou smoke de Swarm. Os resultados de 17/09 registrados no relatório anterior são históricos e não constituem uma validação nova.
- O Docker não está disponível no PATH desta execução. A verificação de migrations pelo agente não detectou mudanças, mas não conseguiu verificar a consistência com o PostgreSQL local por restrição de conexão.
- Desempenho: `dashboard/selectors.py:105-134` executa até 14 consultas para sete dias de frequência. É candidato a agregação por data; não foi medido impacto em produção.
- Operação: as tasks de refresh periódico do dashboard não aparecem na agenda atual do Beat. O preenchimento por demanda continua funcionando; conferir se o compromisso histórico de refresh a cada 5/15 minutos permanece desejado.
- O runbook orienta migrar shared e tenants antes do tráfego, mas `make migrate` executa apenas `--shared`. Convém tornar o procedimento completo explícito e validá-lo na futura preparação de produção, respeitando a atual política de reset pré-produção.

## Alterações realizadas nesta revisão

Produto/configuração: nenhum arquivo alterado. Testes do repositório: nenhum arquivo alterado. Migrations: nenhuma alteração ou reset dev/demo. Documentação: apenas este relatório novo. Caminhos legados removidos: nenhum; esta entrega é uma revisão, não a implementação das correções. Todas as alterações locais anteriores foram preservadas.
