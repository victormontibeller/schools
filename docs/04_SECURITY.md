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
- Professor acessa somente turmas, alunos e registros atribuídos. Responsável acessa somente
  alunos vinculados e os dados derivados desses vínculos; a matriz não remove esses filtros.
- Ausência de registro, módulo desconhecido, ação incompatível ou contrato de escopo ausente
  resulta em negação. A DEMO aplica ainda seu teto próprio de comandos.

### Logs e tokens

- Gunicorn registra o caminho sem query string e o Traefik descarta query parameters do
  access log.
- Logs de aplicação incluem tenant, usuário e correlation ID por identificadores opacos.
  Mensagens não interpolam exceções nem PII.
- Secrets e credenciais ACME existem apenas em secrets/variáveis de ambiente.

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

### Uploads

- Imagens: JPEG, PNG ou WebP válidos, até 5 MiB.
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
