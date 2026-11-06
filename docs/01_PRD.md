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

## Piloto de Educação Infantil — implantação e identidades

O escopo consolidado do piloto e a implantação assistida são acompanhados em
[37_PILOT_IMPLEMENTATION.md](37_PILOT_IMPLEMENTATION.md). A ADR-0022 define bootstrap público
sem impersonação, equipe por convite com validade de sete dias, proteção do último administrador,
carga integral e reversível antes do uso e preservação da cronologia financeira. Crianças não
recebem conta no piloto; guarda, autorização de retirada e consentimento de alertas são distintos.
A primeira homologação usa escola fictícia e não equivale à entrada em produção.

## Piloto — comunicação institucional

Administração e Coordenação redigem, conferem a prévia, publicam, agendam, cancelam o agendamento
e abrem correções. Seleção: famílias da escola, famílias de várias turmas, equipe ou pessoas
específicas; a opção individual aceita contexto da criança. A prévia informa total, contas ainda
não ativadas e ausência de e-mail. PDF/imagens são privados. A correção gera revisão imutável e
nova pendência de ciência quando exigida, preservando o histórico.

Cada pessoa consulta somente revisões destinadas a ela e ainda autorizadas pelos vínculos
atuais. Responsável com irmãos recebe uma entrega coletiva por revisão. Visualização e ciência
explícita têm registros separados da entrega de e-mail e da leitura da notificação. Ciência pode
ter prazo e nunca substitui assinatura, autorização de passeio ou consentimento geral.

A ficha mostra os estados por destinatário e canal, incluindo não ativado, sem endereço,
preferência desabilitada, revogado, falha transitória e falha terminal. E-mail falho não retira o
comunicado do sistema. Após corrigir a causa, a equipe pode criar um novo envio apenas para o
destinatário afetado, preservando tentativas anteriores. Agenda e comunicados usam intenções
persistidas e recuperação periódica, com mensagens externas genéricas e link autenticado.

## Piloto — atendimento privado e avisos de operação

Famílias abrem uma solicitação para uma criança sob sua guarda e escolhem Secretaria,
Coordenação ou Financeiro. A conversa mostra protocolo, mensagens, anexos privados, estado,
prazo e contato imediato. Apenas o autor e a equipe autorizada consultam o conteúdo. Outros
responsáveis pela criança não são incluídos automaticamente. Correções são novas mensagens.

Atendentes precisam de vínculo no setor e capacidade do papel. Administração supervisiona e
transfere preservando o prazo; o setor anterior perde acesso. Setor habilitado exige pelo menos
um atendente ativo e capaz, inclusive após desligamentos e mudanças de permissões. Acesso ao
atendimento financeiro não concede acesso às cobranças.

A primeira resposta humana pública vence no encerramento do próximo dia administrativo após a
data de abertura, em São Paulo. Padrão: segunda a sexta, 8h–18h, com feriados/fechamentos
configuráveis. Mudança de estado não cumpre esse prazo. A família pode reabrir uma solicitação
resolvida e recebe novo prazo. Atrasos são sinalizados à equipe e Administração sem repetir
cobranças automáticas à família.

Atividades e eventos públicos chegam aos responsáveis elegíveis; matrícula e ação documental
ao principal; baixa, estorno e lembretes a responsáveis autorizados ao financeiro. Contas de
crianças não são necessárias. Todos usam intenções persistidas, recuperação individual e
revalidação de acesso. E-mails são genéricos e os detalhes permanecem autenticados no sistema.

### Cadastro inicial infantil e recuperação de carga

No piloto infantil, criança é cadastro escolar sem conta. Nome, sobrenome e data de nascimento
são obrigatórios; CPF/RG/tipo sanguíneo e contato digital podem estar desconhecidos. Documentos
faltantes seguem o atendimento da Secretaria, sem exigir dados inventados para importar.
Identificadores de origem fazem a ligação entre os CSVs; CPF é validado quando informado.
Responsável e pessoa autorizada à retirada podem ser cadastrados sem e-mail. Convite digital
continua condicionado a endereço disponível, e retirada não concede guarda nem conta.

Primeiro uso operacional torna a carga não reversível. Uma carga desfeita pode ser recuperada
integralmente por comando explícito e auditado, com os mesmos IDs e sem conflitos de identidade;
após recuperar, a equipe faz correções normais. O CSV não restaura silenciosamente pessoas.

### Preparação operacional do piloto

Homologação fictícia usa escola inteira, crianças sem conta/contato digital obrigatório e canais
locais explicitamente identificados. Convites persistem na mesma outbox dos eventos, com validade
original e recuperação por destinatário, independentemente de alertas consentidos. Exportação
privada por ADMIN inclui histórico e mídia sem segredos. Backup/restauração exigem consistência,
reconciliação do intervalo perdido e ambiente isolado antes de reabrir. O exercício local não
substitui entrada real, SLA contínuo nem quatro semanas de acompanhamento. Runbook: documento 36;
evidência e gates: documento 37; decisões: ADR-0026.
