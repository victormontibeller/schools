# Segurança

> **Estado em 2026-07-13:** controles descritos como implementados abaixo estão no código;
> rate limiting abrangente e remoção total de `unsafe-inline` permanecem planejados.

## Princípio

O sistema deverá seguir a abordagem **Security First**. Toda nova funcionalidade deverá ser avaliada sob a ótica de segurança antes de ser implementada.

---

## Requisitos Obrigatórios

### Autenticação e Senhas

- O sistema deverá utilizar **Argon2** como algoritmo de hash de senhas.
- Sessões deverão utilizar o mecanismo nativo do Django para a interface web.
- JWT deverá ser utilizado apenas em APIs externas futuras.
- Toda senha nova ou alterada passa por `validate_password` do Django, com mínimo de 8
  caracteres e os validadores de similaridade, senha comum e senha totalmente numérica.
- Maiúscula, número e símbolo não são requisitos isolados. Senhas existentes não são
  invalidadas retroativamente e serão avaliadas quando forem trocadas.

### Proteções HTTP

| Proteção | Descrição |
|---|---|
| **HTTPS** | Toda comunicação deverá ser criptografada via TLS (gerenciado pelo Traefik) |
| **CSRF** | Proteção contra Cross-Site Request Forgery deverá estar ativada em todos os formulários |
| **CSP** | Content Security Policy deverá ser configurada para bloquear conteúdo não autorizado |
| **HSTS** | HTTP Strict Transport Security deverá estar ativado |
| **XSS** | Proteção contra Cross-Site Scripting deverá estar ativa |
| **Clickjacking** | Header `X-Frame-Options` deverá estar configurado |

A política CSP implementada bloqueia objetos, frames, origens de formulário e recursos externos
não autorizados. HTMX é servido como asset local. A exceção temporária `unsafe-inline` permanece
somente para scripts/estilos legados do tema e deverá ser removida conforme forem externalizados.

### Aplicação

- **SQL Injection:** O sistema deverá utilizar exclusivamente o ORM do Django. SQL direto é proibido, exceto em casos documentados e aprovados.
- **Upload Seguro:** Todo arquivo enviado deverá ter seu tipo, tamanho e conteúdo validados antes do armazenamento.
- **Rate Limiting:** Todos os endpoints de autenticação e APIs públicas deverão possuir rate limiting via Redis.

---

## Regras Invioláveis de Segurança

- Nenhuma informação sensível (senhas, tokens, dados pessoais) poderá aparecer em logs.
- Nenhum segredo poderá ser commitado no repositório. Todos os segredos deverão estar em variáveis de ambiente.
- Toda entrada de usuário deverá ser validada e sanitizada antes do processamento.
- Permissões deverão seguir o princípio do menor privilégio.
- Todo acesso administrativo deverá ser logado e auditado.

### Administração da plataforma

- Operadores públicos administram somente escolas, domínios e operadores do schema `public`.
- Não existe impersonação, conta técnica, grant ou rota de acesso cross-schema.
- Um eventual fluxo de suporte exigirá novo threat model e ADR antes de ser implementado.

### Controle de acesso escolar

- Administradores escolares possuem acesso total dentro do próprio tenant. Usuários, Escola,
  Unidades e configuração de Acessos não podem ser delegados.
- Secretaria, Coordenação, Professor, Financeiro e Responsável recebem somente capacidades
  persistidas em `RoleModuleAccess`; permissões individuais e grupos do Django são ignorados.
- Toda autorização combina módulo e ação e é repetida na fronteira HTTP e nos services.
- Calendário e eventos usam a capacidade `academic_calendar`; a administração de feriados e
  anos letivos usa, respectivamente, `holidays` e `academic_years`. Estas duas capacidades são
  delegáveis somente a Secretaria, Coordenação e Financeiro e não ampliam a leitura do calendário.
- A operação da grade usa `schedule`. O catálogo de períodos usa a capacidade independente
  `schedule_configuration`, elegível somente para Secretaria e Coordenação, com ações de leitura,
  criação e edição. Coordenação recebe essas ações por padrão; Secretaria somente por configuração
  explícita. Professor nunca herda o catálogo ao receber escrita na grade.
- Professor acessa somente turmas, alunos e registros atribuídos. Responsável acessa somente
  alunos vinculados e os dados derivados desses vínculos; a matriz não remove esses filtros.
- O escopo canônico do Responsável exige simultaneamente vínculo ativo e não excluído, guarda
  vigente, perfil de responsável ativo e não excluído, conta ativa e aluno ativo e não excluído.
  Atividades exigem ainda matrícula ativa na turma. Desvincular ou invalidar qualquer componente
  revoga imediatamente listas, fichas, mídia, frequência, atividades, Agenda e Financeiro,
  inclusive por URL conhecida.
- Na ficha de atividade, o Responsável recebe somente as linhas dos próprios filhos com matrícula
  ativa. Nota e observação só são expostas após o lançamento oficial; grupos, integrantes e nomes
  de colegas nunca são renderizados para esse papel.
- O dashboard familiar recalcula a cada requisição os totais, frequência, risco, atividades,
  eventos e comunicados dentro do mesmo escopo de guarda. Ele não reutiliza o cache agregado da
  escola, para que uma desvinculação produza revogação já na próxima requisição da mesma sessão.
- No calendário, o Responsável vê somente eventos marcados como públicos: eventos globais para
  famílias e eventos de turmas nas quais um filho sob guarda possua matrícula ativa. Eventos de
  professores, privados ou de outras turmas permanecem ausentes do mês, agenda e detalhe direto.
- A submissão de justificativa por Responsável limita o formulário e repete no service o vínculo
  ativo com o aluno, o perfil ativo do responsável e a guarda vigente. Identificadores de alunos
  fora desse escopo são recusados antes de qualquer escrita ou auditoria; administradores
  autorizados permanecem sujeitos apenas ao isolamento do tenant.
- Ausência de registro, módulo desconhecido, ação incompatível ou contrato de escopo ausente
  resulta em negação. A DEMO aplica ainda seu teto próprio de comandos.

### Logs e tokens

- Gunicorn registra somente status, duração e tamanho. Traefik usa allowlist de router, status
  e duração, sem caminhos, queries ou headers. Django sanitiza mensagens/exceções HTTP usando
  nome canônico da rota; endpoints desconhecidos usam `unresolved`.
- Páginas comuns usam `Referrer-Policy: same-origin`. Convites, recuperação de senha e verificação
  DEMO usam `strict-origin` e `Cache-Control: no-store`: o Referer contém somente a origem, nunca
  caminho/query/token. Essa política foi autorizada em 17/09/2026 para preservar o POST nativo e
  a proteção CSRF, inclusive sem JavaScript; `no-referrer` produz `Origin: null` nesses POSTs.
- O proxy preserva os cabeçalhos Django. O wrapper de cabeçalhos precede a resolução de tenant e
  aplica a política também a escolas indisponíveis e erros antecipados; respostas de erro ou
  redirecionamento sem rota identificável recebem `strict-origin`/`no-store`. Assets servidos com
  sucesso e revalidações HTTP 304 mantêm seu cache immutable. As URLs e a validação CSRF permanecem integrais.
- Spans HTTP próprios contêm somente rota, método e status, sem URLs ou eventos de exceção.
  O pacote de instrumentação Django foi removido; a configuração também impede instrumentação
  automática de Django/logging e exportação de logs OTEL.
- Escolas inativas ou excluídas recebem 404 antes de ativar schema/sessão. O catálogo público
  permanece acessível para reativação. Somente GET/HEAD exatos de `/health/` dispensam tenancy.
- Escopo docente centralizado exige conta/perfil, turma, matrícula e aluno ativos e não excluídos,
  data de matrícula vigente e atribuição por titularidade ou grade vigente. Somente a consulta
  de grade recebe referência histórica; ela não amplia acesso a fichas atuais. O picker global
  de responsáveis exige `guardians/edit`, a mesma capacidade do vínculo.
- Logs de aplicação incluem tenant, usuário e correlation ID por identificadores opacos.
  Mensagens não interpolam exceções nem PII.
- O `X-Correlation-ID` recebido por HTTP nunca é confiável: somente UUID válido é aceito e
  canonicalizado; entrada ausente, longa, malformada ou com caracteres de controle é substituída
  por UUID v4 antes de alcançar contexto, resposta, logs ou auditoria.
- Novos registros de auditoria redigem credenciais, contato, endereço, data de nascimento,
  documentos e textos livres potencialmente pessoais, incluindo motivos, justificativas,
  observações, feedback, mensagens, conteúdo, descrições e títulos. Status, identificadores
  opacos, datas operacionais e valores permanecem disponíveis; o controle vale prospectivamente,
  sem reescrever o histórico já persistido.
- Secrets e credenciais ACME existem apenas em secrets/variáveis de ambiente.
- O contexto de build Docker exclui `.env*`, repositório Git, ambientes virtuais, mídia, bancos
  locais, caches, cobertura, logs, staticfiles gerado e artefatos de navegador.

### Agenda, convites e PWA

- Publicações da Agenda são entregues somente após autenticação e nova validação do vínculo ativo
  de guarda; remover a guarda revoga o acesso mesmo para uma URL conhecida.
- Convites de responsáveis são assinados, expiram em sete dias e são consumidos na primeira
  ativação. O token viaja em query string, que é removida dos access logs, e nunca é incluído em
  logs estruturados.
- E-mails da Agenda carregam somente texto genérico e URL autenticada, sem nome do aluno ou
  conteúdo da publicação. Web Push está adiado e não possui endpoint, assinatura ou chave VAPID.
- O service worker armazena somente assets estáticos públicos e a página offline genérica. HTML
  autenticado, publicações, mídia e respostas HTTP da aplicação não entram no cache.

### Resend e webhooks de e-mail

- `RESEND_API_KEY` e `RESEND_WEBHOOK_SECRET` existem somente em variáveis de ambiente; escolas
  compartilham a chave da plataforma e nunca armazenam credenciais próprias.
- Cada escola informa um remetente cujo domínio foi verificado manualmente por SPF/DKIM na mesma
  conta Resend. Ausência de confirmação bloqueia o envio sem usar remetente de outro tenant.
- `/webhooks/resend/email/` aceita chamadas somente no domínio da plataforma e verifica a
  assinatura Svix sobre o corpo bruto. O `svix-id` é persistido para impedir replay/duplicidade.
- Tags contêm apenas schema, UUID do log e categoria. Payload bruto, endereço, assunto e conteúdo
  não são persistidos nem emitidos em logs estruturados.
- Eventos de abertura e clique não são assinados pelo produto. A abertura autenticada da Agenda
  permanece a fonte oficial de visualização.
- O SMTP e `EMAIL_BACKEND` permanecem restritos à recuperação de senha nativa do Django; os
  demais e-mails transacionais passam por `EmailChannel` e Resend.

## Matrículas e documentos privados

- Comandos do workflow de matrícula exigem ator autenticado; rotinas internas precisam declarar
  explicitamente `@system_command` e sempre recebem o schema do tenant.
- `reenrollment` e `document_requirements` são capacidades independentes, elegíveis somente para
  Secretaria e Coordenação. Preparar o lote exige Visualizar e confirmá-lo exige Cadastrar;
  listar, criar, editar e desativar requisitos exigem suas ações correspondentes. Requisitos
  documentais não são concedidos por padrão.
- Documentos de matrícula usam storage privado, validação de upload e download autenticado com
  política `VIEW`; a dispensa de requisito permanece fora da capacidade de configuração, é
  exclusiva do Administrador e exige motivo auditado.
- Lembretes são publicados somente após commit e passam por `MessageTransport`/`MessageLog`. O
  destinatário é revalidado imediatamente antes da entrega quanto a atividade, guarda e
  consentimento; retries e a reconciliação periódica tenant-scoped de claims abandonados
  reutilizam o mesmo `MessageLog`. A reconciliação republica somente logs pendentes e sincroniza
  logs terminais sem repetir o canal. O conteúdo externo é genérico e não inclui nome, matrícula,
  protocolo ou lista de documentos.
- Logs do workflow usam somente identificadores opacos, estados e contadores; nome, e-mail, CPF,
  telefone, endereço e conteúdo documental são proibidos.

### Uploads

- Avatares, fotos e logotipos: JPEG, PNG ou WebP estáticos, íntegros, até 5 MiB e 25 megapixels.
  Somente a versão WebP normalizada é armazenada, sem metadados pessoais; orientação, proporção
  e transparência são preservadas. Services e forms validam conteúdo real, sem confiar na extensão.
- Documentos: PDF, JPEG, PNG ou WebP válidos, até 10 MiB.
- Documentos escolares são entregues por download autenticado, como anexo e sem cache público.

---

## OWASP Top 10

O sistema deverá ser protegido contra todas as vulnerabilidades do **OWASP Top 10**:

1. Broken Access Control
2. Cryptographic Failures
3. Injection
4. Insecure Design
5. Security Misconfiguration
6. Vulnerable and Outdated Components
7. Identification and Authentication Failures
8. Software and Data Integrity Failures
9. Security Logging and Monitoring Failures
10. Server-Side Request Forgery
