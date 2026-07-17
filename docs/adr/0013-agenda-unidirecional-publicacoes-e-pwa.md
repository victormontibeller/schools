# ADR-0013 — Agenda unidirecional, publicações imutáveis e PWA

## Status

Aceito em 2026-07-15; Web Push adiado em 2026-07-16.

## Contexto

A Agenda da Educação Infantil era um registro editável consultado diretamente pelos responsáveis.
O produto precisa incorporar revisão pedagógica, prova do conteúdo efetivamente publicado e
entrega multicanal sem transformar a rotina escolar em chat.

## Decisão

- Modelar a folha diária nos estados `DRAFT`, `PENDING_REVIEW`, `CHANGES_REQUESTED` e `PUBLISHED`.
- Permitir preenchimento e envio ao professor, reservando publicação e devolução à coordenação e
  administração.
- Criar a cada publicação uma revisão imutável, com snapshot por aluno dos aspectos, refeições e
  observações. Reabrir permite editar a fonte, mas a republicação cria outra revisão.
- Criar um recibo por publicação, aluno e responsável ativo com guarda, preservando a primeira e
  atualizando a última visualização de forma idempotente.
- Não modelar respostas, mensagens, reações ou confirmações do responsável e não expor API REST
  pública nesta fase.
- Entregar notificação interna e e-mail consentido. O texto externo é genérico e exige
  autenticação para abrir o conteúdo.
- Manter no cache PWA somente assets públicos e uma página offline genérica. Web Push, VAPID,
  assinaturas e notificações do navegador ficam adiados.
- Migrar registros históricos para revisão 1 publicada, preservando os dados existentes sem gerar
  entregas retroativas.

## Consequências

A escola passa a ter histórico auditável do que cada família pôde visualizar, e uma correção não
reescreve comunicações anteriores. A publicação cria mais registros por aluno e responsável e
exige processamento assíncrono por e-mail. O responsável precisa de conta vinculada e guarda ativa;
sem esses requisitos não recebe nem consulta a Agenda. A aplicação continua instalável, porém não
solicita permissão de notificação. O rollout permanece protegido pela configuração da escola de
demonstração até a validação da experiência.
