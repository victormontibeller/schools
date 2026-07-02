# Sprint 06 - Tela da Empresa

## Objetivo

Criar o frontend da tela da empresa (escola) para cadastro, visualizacao e edicao dos dados institucionais, endereco e contato responsavel, seguindo o padrao visual do sistema.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] A tela da empresa devera permitir visualizar e editar os dados institucionais da escola.
- [x] A escola devera permitir upload e atualizacao do logotipo com armazenamento seguro.
- [x] A tela devera exibir os campos institucionais:
  - CNPJ
  - razao social
  - nome fantasia
  - inscricao estadual
  - inscricao municipal
- [x] A tela devera exibir a secao de endereco da escola.
- [x] A tela devera exibir os dados do responsavel ou contato direto:
  - nome completo
  - cargo ou funcao
  - telefone direto ou celular
  - e-mail direto
- [x] O formulario devera apresentar validacoes visuais claras e organizacao por secoes.
- [x] O layout devera ser responsivo e consistente com o design system Duralux.
- [x] O fluxo de salvamento nao devera quebrar a edicao atual da entidade School.

---

## Tarefas

### Experiencia e Layout

- [x] Definir a estrutura da tela com secoes bem separadas:
  - dados da empresa
  - endereco
  - dados do responsavel
- [x] Definir hierarquia visual para facilitar leitura e edicao.
- [x] Garantir que a tela funcione bem em desktop e mobile.

### Campos da Empresa

- [x] Incluir no frontend os campos:
  - `cnpj`
  - `legal_name` ou equivalente para razao social
  - `trade_name` ou equivalente para nome fantasia
  - `state_registration`
  - `municipal_registration`
  - `logo`
- [x] Definir mascaras e placeholders adequados para documentos.

### Logotipo da Escola

- [x] Incluir componente de upload de logotipo no formulario da school
- [x] Validar tipo e tamanho de arquivo no frontend e backend
- [x] Exibir preview do logotipo atual quando houver arquivo cadastrado
- [x] Definir fallback visual quando a escola nao possuir logotipo

### Endereco

- [x] Integrar a secao de endereco com o padrao definido para o modulo de enderecos.
- [x] Exibir campos de endereco de forma organizada e reutilizavel.

### Responsavel / Contato Direto

- [x] Incluir no frontend os campos:
  - `contact_full_name`
  - `contact_role`
  - `contact_phone`
  - `contact_email`
- [x] Garantir exibicao coerente com outros formularios administrativos.

### Forms, Views e Templates

- [x] Criar ou ajustar form da entidade School para suportar os novos campos visuais.
- [x] Ajustar view de edicao da escola para renderizar a nova composicao da tela.
- [x] Criar template ou partials reutilizaveis para secoes da tela.
- [x] Garantir mensagens de sucesso e erro no padrao do projeto.

### Validacao e Comportamento

- [x] Validar formato de CNPJ no frontend e backend.
- [x] Validar formato de email e telefone do contato.
- [x] Validar upload de imagem do logotipo com regras padronizadas.
- [x] Exibir erros de campo de forma padronizada.
- [x] Manter CSRF, acessibilidade basica e semantica dos formularios.

### Testes

- [x] Criar ou ajustar testes de service para SchoolService.
- [x] Criar testes de validacao CNPJ.
- [ ] Ajustar testes de views para renderizacao da tela.
- [x] Validar que a tela continua funcional apos integracao com endereco.

---

## Dependencias

- Sprint 02 concluida
- Sprint 04 concluida para consolidacao do endereco

---

## Definition of Done

- [x] Todos os criterios de aceite atendidos
- [x] Tela da empresa implementada e responsiva
- [x] Formularios e validacoes funcionando
- [x] Testes atualizados e passando
- [x] Lint e format passing
- [x] Sem regressao no fluxo atual de School

---

## Progresso

> Atualizado em 2026-07-01

**Concluido:**
- `School` model ampliado com 8 novos campos: `legal_name`, `trade_name`, `state_registration`, `municipal_registration`, `contact_full_name`, `contact_role`, `contact_phone`, `contact_email`
- `base/validators.py` — `validate_cnpj` (14 digitos, digitos verificadores, anti-repeticao)
- `core/services.py` — `SchoolService` com `create_school`, `update_school`, `update_logo`, `deactivate_school`. Validacao CNPJ (formato + unicidade)
- `core/selectors.py` — `SchoolSelector` (consulta read-only)
- `core/forms.py` — `SchoolEditForm` com 16 campos distribuidos em 3 secoes (institucional, contato, logo)
- `core/views.py` — `school_edit` com inicializacao de valores e suporte a upload de logo
- `core/urls.py` — rota `/app/empresa/` → `school_edit`
- Template `core/templates/core/school_edit.html` — 4 secoes visuais: Dados Institucionais, Logotipo (com preview), Responsavel/Contato, Enderecos (via partial `address_table.html`)
- Dashboard inclui atalho "Empresa" no menu de modulos
- 20 testes: `test_school_service.py` (create/update/deactivate/CNPJ), `test_validators.py` (CNPJ)
- Migrations geradas e prontas

**Pendente:**
- Testes de views para renderizacao da tela da empresa
