# ADR-0023 — Revisões de comunicados e entrega durável

- Status: aceito para implementação pré-produção
- Data: 2026-10-25
- Escopo: comunicados institucionais e entrega da Agenda

## Decisão

`Announcement` é o único fluxo de autoria. Administração e Coordenação criam rascunhos
versionados, conferem a audiência e publicam ou agendam. O agendamento resolve a audiência no
momento de publicar. Cancelar retorna a rascunho. Corrigir abre um novo rascunho e preserva todas
as revisões anteriores.

Cada `AnnouncementRevision` congela título, mensagem, seleção da audiência, anexos e exigência de
ciência. `AnnouncementRecipient` registra a audiência efetiva, deduplicada por responsável em
comunicados coletivos, com IDs das crianças que justificam o acesso. Leitura, download e worker
revalidam conta, papel, perfil, escola e guarda atuais; possuir um recibo histórico não concede
acesso após revogação. A audiência não é ampliada silenciosamente quando surgem novas famílias.
Anexos PDF/imagem usam validação e storage privado canônicos, sem URLs públicas.

Visualização autenticada e ciência são recibos diferentes. Ciência exige POST com CSRF e ação
do próprio destinatário, é idempotente por revisão e não deriva de leitura de notificações,
e-mail entregue ou ciência de revisão anterior. Não constitui autorização nem assinatura.

`MessageLog` também é a intenção durável de entrega. Não há uma segunda tabela concorrente de
estado do provedor. Publicação, recibos, inbox e intenções individuais por canal são atômicos;
`on_commit` apenas sinaliza a fila. Beat recupera a cada minuto agendamentos de comunicados,
intenções pendentes, retentativas vencidas e leases expirados. Uma indisponibilidade do broker
não perde a intenção persistida. A Agenda preserva seus recibos/inbox e publica o e-mail por esse
mesmo contrato durável.

Claim e conclusão são comandos transacionais separados; a rede acontece fora da transação.
O claim bloqueia somente o MessageLog, inclusive quando as relações carregadas são anuláveis no
PostgreSQL. UUID de lease impede conclusão por worker antigo. A retentativa técnica reutiliza
MessageLog, chave `message-log/<UUID>`, destinatário e payload completos, incluindo remetente.
São no máximo três tentativas automáticas, com espera exponencial. Webhooks repetidos são
idempotentes sob lock e nunca fazem regredir o estado do provedor. Uma falha terminal recebida
antes ou depois do retorno do worker aparece como falha operacional recuperável.

Antes da rede são reconferidos conta/perfil, guarda, consentimento e endereço. Mudança de endereço
ou remetente impede alterar o payload sob uma chave possivelmente aceita. O reprocessamento
humano autorizado cria uma geração sucessora, auditada, com nova chave e configuração atual,
mantendo o log anterior intacto. A relação única com o predecessor torna duplo clique idempotente.
Uma confirmação tardia de sucesso em qualquer geração anterior bloqueia o próximo envio, também
na conferência imediatamente anterior à rede. Não há promessa de entrega exatamente uma vez
entre nosso banco e o provedor: uma confirmação externa pode chegar depois da última conferência.

E-mail contém somente identificação escolar, frase genérica e um link autenticado. Não contém
nome da criança, texto pedagógico, valor financeiro ou anexo privado. Payload funcional fica no
log de entrega; auditoria redige endereço/remetente e conteúdo sensível. Inbox e publicação não
dependem de consentimento para alertas ou de sucesso do e-mail.

## Clean break e implantação

Foram removidos envio batch de Announcement no transporte, tasks antigas de envio institucional
por e-mail/WhatsApp, a task específica de e-mail da Agenda e suas superfícies/testes substituídos.
Não há um novo app paralelo de comunicação nem aliases para métodos antigos. O contrato interno
`OutboxService.create_event_deliveries` será integrado aos eventos de atendimento e secretaria na
etapa seguinte; serviços legados de outros domínios ainda são tratados nessa etapa, não coexistem
como alternativas para os comunicados substituídos aqui.

O grafo inicial foi regenerado pelo Django para a validação intermediária e preserva os seeds
permitidos de localidades e Agenda. Nova regeneração ocorrerá após os models do atendimento.
Somente bancos temporários de teste são recriados nesta rodada; instalações existentes não são
resetadas. A política pré-produção permanece vigente. SMTP da recuperação de senha, operação de
provedor real, navegador completo, cobertura global e recuperação banco+mídia exigem validação
na consolidação. Nenhum e-mail real é enviado pela homologação fictícia.
