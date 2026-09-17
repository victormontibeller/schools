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
- Financeiro

## Rotina docente

- Chamadas registram presença individual e conteúdo ministrado por aula.
- Atividades podem ser individuais ou em grupo, mantendo nota e feedback finais por aluno. A grade
  começa em rascunho; o lançamento oficial a torna somente leitura e só pode ser revertido por
  reabertura com motivo obrigatório.
- A série da turma é selecionada em catálogo fixo e validada conforme a etapa de ensino.
- Turmas da Educação Infantil possuem Agenda diária unidirecional com itens configuráveis nas
  seções Como foi o dia e Alimentação, aplicação por turno e consulta pelos responsáveis ativos
  que mantêm guarda. Humor, Descanso, Evacuação, Participação e as três refeições são itens
  iniciais editáveis de cada escola.
- A Agenda da turma é salva em uma única operação atômica; todas as crianças ativas e todos os
  itens habilitados e aplicáveis ao turno devem estar válidos.
- O professor envia a folha para revisão. Somente coordenação ou administração publica ou devolve
  para correção; professores não publicam diretamente.
- O envio para revisão cria notificação interna e e-mail genérico para revisores ativos, com link
  autenticado para a turma/data. O dashboard mantém até dez pendências recentes visíveis.
- Cada publicação cria uma revisão e um `answers_snapshot` imutável por aluno, com as respostas
  das duas seções. Uma correção reabre a folha e cria nova revisão sem alterar o histórico anterior.
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

## Integrações futuras

- A interface web atual usa Django Templates + HTMX e não depende de API REST.
- Uma API REST versionada será introduzida quando houver consumidor independente, como aplicativo
  mobile, frontend separado ou integração externa.

## Indicadores da Agenda

- Visualização da revisão mais recente em até 24 horas entre responsáveis notificados.
- Dias letivos com publicação por turma elegível da Educação Infantil.
- Tempo mediano entre envio para revisão e publicação.
- Indicadores auxiliares: ativação dos responsáveis, adesão ao Push, falhas de entrega,
  republicações e incidentes de acesso indevido.
- As primeiras quatro semanas de uso formam a linha de base antes da definição de metas.

## Financeiro — Contas a Receber

- Modelos de plano definem condições reutilizáveis para contratos futuros; cada contrato copia
  seus termos e não muda quando o modelo é editado.
- Contratos são individuais por aluno e ano letivo. A ativação materializa atomicamente o
  calendário completo de competências; contratos ativos mudam somente por aditivo futuro.
- Cobranças contratuais e avulsas discriminam principal, desconto, multa e juros. Quitação e
  atraso são derivados do saldo e das datas, sem varredura que grave o estado Vencido.
- Uma baixa manual nasce pendente e pode ser alocada em várias cobranças. Somente a confirmação
  altera os saldos e o caixa; o estorno preserva o pagamento e produz o movimento inverso.
- Pagamentos confirmados recebem recibo interno não fiscal `REC-AAAA-NNNNNN`. O aluno possui
  extrato consolidado em PDF e documentos estornados continuam disponíveis com identificação.
- Relatórios separam competência — previsto, encargos, recebido alocado e saldo — de caixa —
  entradas pela data do pagamento e estornos pela data do estorno. A inadimplência permite
  detalhamento por faixa, aluno, turma e contrato e exportação CSV.
- A régua de cobrança começa desabilitada, exige regras explícitas e deduplica por cobrança,
  regra, responsável e canal. Mensagens externas são genéricas e exigem consentimento, guarda
  ativa e acesso ao aluno.
- Os acessos são independentes para Visão Financeira, Modelos, Contratos, Cobranças, Baixas e
  Conciliações, Lembretes, Competência e Caixa e Inadimplência. Somente o papel Financeiro recebe
  esses processos por padrão; Secretaria e Coordenação podem ser configuradas pela escola.
- Responsáveis não recebem acesso financeiro por padrão. Quando habilitados, podem apenas
  visualizar Visão Financeira e Cobranças dos alunos sob guarda ativa; notas internas,
  conciliação e auditoria permanecem restritas. Professores não são elegíveis aos processos.

Ficam fora deste ciclo despesas, fornecedores, contas a pagar, integrações bancárias reais,
OFX/CSV bancário, PIX/boleto, webhooks financeiros e documentos fiscais.

## Secretaria — Matrículas

- Toda matrícula acadêmica nasce de uma solicitação interna para aluno já cadastrado. O workflow
  cobre matrícula nova, rematrícula, transferência interna, recebida e de saída.
- Aprovar reserva vaga; se a capacidade estiver comprometida, a solicitação entra em lista de
  espera, ordenada deterministicamente por maior prioridade e entrada mais antiga. A posição é
  exibida por turma e não existe promoção automática.
- Cada solicitação mantém protocolo anual `MAT-AAAA-NNNNNN`, versão concorrente e histórico
  append-only de transições. Recusa, correção, transferência e cancelamento exigem motivo.
- Requisitos documentais são configurados por tipo e copiados para um checklist imutável na
  abertura. Documentos obrigatórios bloqueiam apenas a efetivação; Administrador pode dispensar
  um item com justificativa.
- Rematrícula confirma atomicamente um mapeamento aluno–turma do ano seguinte. A interface sugere
  a próxima série no mesmo turno, permite selecionar somente parte dos alunos e aceita repetência
  ou exceção justificada. A atomicidade cobre exatamente o subconjunto confirmado.
- Pré-matrícula e Correção necessária podem ser canceladas com motivo e versão esperada; o
  encerramento libera o aluno/ano para uma nova solicitação.
- Rematrícula em lote e Requisitos documentais são capacidades independentes, delegáveis somente
  a Secretaria e Coordenação. Secretaria recebe rematrícula por padrão; a configuração documental
  não possui concessão padrão. A dispensa de item continua exclusiva do Administrador.
- Lembretes são e-mails genéricos ao responsável principal com guarda e consentimento e ao aluno
  elegível e consentido. Família/público, WhatsApp e promoção automática da espera não integram
  esta versão.

## Secretaria — Alunos

- O e-mail exibido na edição do aluno é somente leitura e tentativas adulteradas de alteração são
  recusadas também pelo service. Observações internas permanecem editáveis, limitadas e protegidas
  pela allowlist de escrita e pela redação canônica da auditoria.
