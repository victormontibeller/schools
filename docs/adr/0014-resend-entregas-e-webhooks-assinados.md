# ADR-0014 — Resend, entregas e webhooks assinados

## Status

Aceito em 2026-07-15.

## Contexto

O backend SMTP do Django informa que o servidor aceitou uma mensagem, mas não acompanha entrega,
atraso, bounce, supressão ou reclamação. A Agenda precisa de indicadores operacionais de entrega
sem usar abertura de e-mail como substituto da visualização autenticada.

## Decisão

- Usar a Resend API atrás de `EmailChannel`, com uma única `RESEND_API_KEY` global em variável de
  ambiente e remetente verificado por escola em `School.settings["email"]`.
- Criar `MessageLog` antes da chamada externa. Seu UUID gera a chave de idempotência e segue nas
  tags com o schema do tenant, permitindo correlacionar webhooks sem consulta cross-schema.
- Receber eventos no domínio público da plataforma, verificar a assinatura Svix sobre o corpo
  bruto e processar no schema validado pela tag.
- Persistir apenas identificadores, tipo e horário do evento. `svix-id` é único e estados finais
  não regridem por eventos duplicados ou fora de ordem.
- Acompanhar `sent`, `delivered`, `delivery_delayed`, `bounced`, `failed`, `suppressed` e
  `complained`. Não acompanhar abertura ou clique.
- Verificar domínios manualmente no painel Resend nesta fase; onboarding DNS automatizado fica
  adiado.
- Manter `EMAIL_BACKEND`/SMTP somente para a recuperação de senha nativa do Django. Essa exceção
  não participa dos indicadores de entrega da Agenda.

## Consequências

O produto passa a manter histórico de entrega além da retenção do provedor e oferece resumo por
publicação sem expor destinatários. A conta Resend continua sendo infraestrutura compartilhada,
mas remetentes e dados operacionais permanecem isolados por tenant. O endpoint público exige
segredo de webhook, deduplicação e testes de eventos fora de ordem.
