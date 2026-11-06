# ADR-0024 — Atendimento privado e matriz durável do piloto

- Status: aceito para implementação pré-produção
- Data: 2026-10-25
- Escopo: atendimento, calendário administrativo, mensagens escolares e financeiras

## Decisão

O app `service_requests` mantém protocolo anual, criança, autor, setor, atendente, mensagens,
anexos privados e histórico. Secretaria, Coordenação e Financeiro são setores fixos. O autor
familiar precisa de guarda vigente; outro responsável pela mesma criança não herda a conversa.
A equipe precisa simultaneamente das capacidades de atendimento e do vínculo ativo no setor.
Administrador supervisiona e transfere; responder publicamente também exige vínculo de atendente.
Capacidade de atendimento Financeiro é independente das capacidades de cobrança/conciliação.

Estados: Aberta, Em atendimento, Aguardando família, Resolvida e Cancelada. Mensagens não têm
edição ou exclusão; correções são novas mensagens. Apenas resposta humana pública da equipe
registra primeira resposta. Alteração de estado, atribuição e confirmação automática não cumprem
o prazo. Transferência preserva prazo e revoga o setor anterior; o autor pode reabrir uma
solicitação resolvida, iniciando novo ciclo de resposta, sem apagar mensagens anteriores.

`AdministrativeCalendar` é separado do calendário letivo: São Paulo, segunda a sexta, 8h–18h
por padrão, com dias/horários e fechamentos ajustáveis. O vencimento é o encerramento do próximo
dia de atendimento **após a data local de abertura**, inclusive quando a abertura ocorre fora do
horário. Alterar o calendário não recalcula prazos já assumidos. Antes da abertura familiar, a
escola precisa configurar contato imediato e habilitar um setor com atendente capaz e ativo.

Os comandos de configuração, atendimento e ciclo de contas usam primeiro o lock estável do papel
ADMIN e depois os objetos. Assim, duas desativações não removem o último atendente, e mudanças de
matriz/papel não deixam setor habilitado sem alguém capaz. Versões recebidas do cliente impedem
resposta/transferência com formulário obsoleto. O lock é deliberadamente amplo para o piloto de
uma a três escolas; eventual granularização exige preservar a ordem e as provas de concorrência.

## Entregas e eventos

Outbox da ADR-0023 é a infraestrutura única para atendimento, Agenda, comunicados, atividades,
calendário, matrícula, documentos, baixa, estorno e lembretes financeiros. Eventos de abertura,
resposta e reabertura notificam a parte que precisa agir. Atraso é deduplicado por ciclo e avisa
somente equipe/Administração. Transferência e conclusão invalidam avisos operacionais obsoletos.

Produtores da matriz registram handlers `required=True` no dispatcher: a intenção durável é
parte da transação de negócio. Falha ao persistir ou auditar o aviso reverte também a mutação
original. Observadores opcionais continuam com isolamento de falhas. Broker é apenas sinalização
após commit; o scanner periódico recupera intenções já persistidas.

O modelo atual de atividade não possui rascunho de publicação: criar a atividade a torna
consultável. `score_status=DRAFT` significa notas ainda não publicadas e não impede o aviso da
atividade. Calendário só avisa famílias quando público; audiência CLASS exige turma válida.
Ambos resolvem responsáveis com guarda e matrícula ativa, sem depender de contas infantis. A
revalidação exige guarda e matrícula na **mesma criança**, mesmo em audiência coletiva de irmãos.
Matrícula efetivada e ação documental usam responsável principal vigente. Baixa, estorno e
lembretes financeiros exigem também acesso financeiro atual.

`EnrollmentReminder` e `CollectionReminder` preservam a intenção de negócio e apontam para a
atual geração `MessageLog`. Não possuem mais lease/worker próprio. Estado de transporte é uma
projeção da geração vigente; webhooks tardios de uma geração anterior não substituem essa
projeção. Reprocessamento humano cria nova geração e atualiza o vínculo de negócio sob lock.

A escola suspensa, conta desativada, guarda removida ou acesso revogado bloqueiam a rede no
worker. E-mails têm escola, texto genérico e um link autenticado, sem nome da criança, conteúdo,
valor ou anexo. Assunto livre da solicitação e contato imediato são redigidos na auditoria.

## Clean break e operação

Removidos os workers legados `deliver_collection_reminder_task`,
`send_enrollment_document_reminder`, a reconciliação própria dos lembretes de matrícula e
`notify_audience_all_task`, com métodos consumidores e testes exclusivos. Audiência de calendário
STUDENTS foi removida; no piloto infantil os destinatários são responsáveis. O grafo inicial foi
regenerado pelo Django, preservando somente os dois seeds autorizados. A política pré-produção
continua vigente: esta ADR não autoriza dados reais nem declara lançamento.

Falhas de entrega aparecem em **Atendimento → Entregas**, filtradas pelas capacidades do domínio.
Depois de corrigir a causa, reprocessar apenas a entrega afetada. Preferência de alertas continua
sob escolha da pessoa. Operadores monitoram Beat/worker e atrasos; validação real de provedor,
restauração, treinamento e quatro semanas de acompanhamento continuam gates operacionais.
