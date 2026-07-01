# Sprint 05 - Identificacao Cadastral

## Objetivo

Padronizar os dados pessoais, documentais e de contato de Guardians, Students e Teachers para garantir consistencia de cadastro, melhor rastreabilidade administrativa e base segura para futuras regras academicas e operacionais.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] Guardian, Student e Teacher deverao possuir cadastro com os seguintes dados:
  - nome completo
  - data de nascimento
  - sexo ou genero
  - nacionalidade
  - CPF
  - RG com numero, orgao emissor e UF
  - telefone celular
  - email
- [ ] CPF devera ser unico por entidade quando informado.
- [ ] CPF devera ser validado por formato e digitos verificadores.
- [ ] UF do RG devera aceitar apenas siglas validas.
- [ ] Formularios deverao apresentar mascara e mensagens claras de validacao.
- [ ] Operacoes de criacao e atualizacao deverao gerar auditoria.
- [ ] Fluxos existentes nao deverao regredir com a ampliacao cadastral.

---

## Tarefas

### Modelagem

- [ ] Revisar models de `guardians`, `students` e `teachers` para padronizar os campos:
  - `full_name` ou estrategia equivalente consistente por modulo
  - `birth_date`
  - `gender`
  - `nationality`
  - `cpf`
  - `rg_number`
  - `rg_issuer`
  - `rg_state`
  - `phone_mobile`
  - `email`
- [ ] Definir estrategia de compatibilidade com a model `CustomUser` quando houver sobreposicao de email, nome ou telefone.
- [ ] Adicionar constraints e indices para CPF e campos de busca relevantes.

### Services

- [ ] Atualizar services de cadastro e edicao para aplicar validacoes de negocio:
  - CPF valido
  - CPF duplicado
  - UF valida
  - email com formato valido
  - obrigatoriedade conforme perfil da entidade
- [ ] Garantir escrita com `self._record_audit(...)` em todas as alteracoes.
- [ ] Garantir logs sem PII, preservando apenas IDs e contexto tecnico.

### Selectors

- [ ] Criar ou ajustar selectors para suportar busca por:
  - nome completo
  - CPF
  - email
  - telefone celular
- [ ] Ajustar listagens administrativas para exibir informacoes cadastrais essenciais.

### Forms e Views

- [ ] Atualizar forms de Guardian, Student e Teacher com validacoes de campo.
- [ ] Ajustar views para lidar com novos campos sem mover regra de negocio para fora dos services.
- [ ] Garantir reaproveitamento de widgets e componentes onde fizer sentido.

### Templates

- [ ] Atualizar formularios para exibir os novos campos de forma organizada.
- [ ] Exibir dados documentais e de contato nas telas de detalhe.
- [ ] Garantir consistencia visual com o padrao Duralux.

### Migracoes e Compatibilidade

- [ ] Criar migracoes para os novos campos.
- [ ] Definir estrategia para dados existentes:
  - backfill quando houver fonte confiavel
  - campos opcionais temporarios quando necessario
- [ ] Revisar impacto em seeds e fixtures de demo.

### Testes

- [ ] Testes de model para constraints e validacoes basicas.
- [ ] Testes de service para CPF, RG, email e duplicidade.
- [ ] Testes de forms e views para fluxos de criacao e edicao.
- [ ] Testes de selectors para filtros de busca.

---

## Dependencias

- Sprint 03 concluida
- Sprint 01 concluida
- Sprint 04 recomendada quando houver necessidade de consolidar cadastro civil e endereco no mesmo fluxo

---

## Definition of Done

- [ ] Todos os criterios de aceite atendidos
- [ ] Migracoes aplicadas com sucesso
- [ ] Testes atualizados e passando
- [ ] Lint e format passing
- [ ] Sem regressao nos fluxos atuais de cadastro