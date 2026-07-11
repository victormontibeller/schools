# Segurança

## Princípio

O sistema deverá seguir a abordagem **Security First**. Toda nova funcionalidade deverá ser avaliada sob a ótica de segurança antes de ser implementada.

---

## Requisitos Obrigatórios

### Autenticação e Senhas

- O sistema deverá utilizar **Argon2** como algoritmo de hash de senhas.
- Sessões deverão utilizar o mecanismo nativo do Django para a interface web.
- JWT deverá ser utilizado apenas em APIs externas futuras.
- Política de senha forte deverá ser imposta em todos os formulários de criação e alteração.

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

### Acesso de suporte

- Exige operador público superuser ou permissão `tenancy.access_tenant`.
- Exige motivo, token assinado de uso único e expiração em 30 minutos.
- A sessão exibe banner permanente e registra `platform_actor_id` e `support_grant_id`.
- Usuários públicos comuns nunca recebem acesso cross-schema.

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
