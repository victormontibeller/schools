# Sprint 06 - Tela da Empresa

## Objetivo

Criar o frontend da tela da empresa (escola) para cadastro, visualizacao e edicao dos dados institucionais, endereco e contato responsavel, seguindo o padrao visual do sistema.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] A tela da empresa devera permitir visualizar e editar os dados institucionais da escola.
- [ ] A escola devera permitir upload e atualizacao do logotipo com armazenamento seguro.
- [ ] A tela devera exibir os campos institucionais:
  - CNPJ
  - razao social
  - nome fantasia
  - inscricao estadual
  - inscricao municipal
- [ ] A tela devera exibir a secao de endereco da escola.
- [ ] A tela devera exibir os dados do responsavel ou contato direto:
  - nome completo
  - cargo ou funcao
  - telefone direto ou celular
  - e-mail direto
- [ ] O formulario devera apresentar validacoes visuais claras e organizacao por secoes.
- [ ] O layout devera ser responsivo e consistente com o design system Duralux.
- [ ] O fluxo de salvamento nao devera quebrar a edicao atual da entidade School.

---

## Tarefas

### Experiencia e Layout

- [ ] Definir a estrutura da tela com secoes bem separadas:
  - dados da empresa
  - endereco
  - dados do responsavel
- [ ] Definir hierarquia visual para facilitar leitura e edicao.
- [ ] Garantir que a tela funcione bem em desktop e mobile.

### Campos da Empresa

- [ ] Incluir no frontend os campos:
  - `cnpj`
  - `legal_name` ou equivalente para razao social
  - `trade_name` ou equivalente para nome fantasia
  - `state_registration`
  - `municipal_registration`
  - `logo`
- [ ] Definir mascaras e placeholders adequados para documentos.

### Logotipo da Escola

- [ ] Incluir componente de upload de logotipo no formulario da school
- [ ] Validar tipo e tamanho de arquivo no frontend e backend
- [ ] Exibir preview do logotipo atual quando houver arquivo cadastrado
- [ ] Definir fallback visual quando a escola nao possuir logotipo

### Endereco

- [ ] Integrar a secao de endereco com o padrao definido para o modulo de enderecos.
- [ ] Exibir campos de endereco de forma organizada e reutilizavel.
- [ ] Preparar compatibilidade com a Sprint 04 quando o modulo de enderecos for implementado.

### Responsavel / Contato Direto

- [ ] Incluir no frontend os campos:
  - `contact_full_name`
  - `contact_role`
  - `contact_phone`
  - `contact_email`
- [ ] Garantir exibicao coerente com outros formularios administrativos.

### Forms, Views e Templates

- [ ] Criar ou ajustar form da entidade School para suportar os novos campos visuais.
- [ ] Ajustar view de edicao da escola para renderizar a nova composicao da tela.
- [ ] Criar template ou partials reutilizaveis para secoes da tela.
- [ ] Garantir mensagens de sucesso e erro no padrao do projeto.

### Validacao e Comportamento

- [ ] Validar formato de CNPJ no frontend e backend.
- [ ] Validar formato de email e telefone do contato.
- [ ] Validar upload de imagem do logotipo com regras padronizadas.
- [ ] Exibir erros de campo de forma padronizada.
- [ ] Manter CSRF, acessibilidade basica e semantica dos formularios.

### Testes

- [ ] Criar ou ajustar testes de views para renderizacao da tela.
- [ ] Criar testes de forms para validacao dos campos institucionais e de contato.
- [ ] Validar que a tela continua funcional apos integracao com endereco.

---

## Dependencias

- Sprint 02 concluida
- Sprint 04 recomendada para consolidacao do endereco
- Sprint 14 recomendada para padronizacao ampla de UX

---

## Definition of Done

- [ ] Todos os criterios de aceite atendidos
- [ ] Tela da empresa implementada e responsiva
- [ ] Formularios e validacoes funcionando
- [ ] Testes atualizados e passando
- [ ] Lint e format passing
- [ ] Sem regressao no fluxo atual de School