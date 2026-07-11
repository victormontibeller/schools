# Sprint 05 - Identificacao Cadastral

> **Documento histórico.** Em caso de divergência, prevalecem os documentos normativos em `docs/`.

## Objetivo

Padronizar os dados pessoais, documentais e de contato de Guardians, Students e Teachers para garantir consistencia de cadastro, melhor rastreabilidade administrativa e base segura para futuras regras academicas e operacionais.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] Guardian, Student e Teacher deverao possuir cadastro com os seguintes dados:
  - nome completo
  - data de nascimento
  - sexo ou genero
  - nacionalidade
  - CPF
  - RG com numero, orgao emissor e UF
  - telefone celular
  - email
- [x] CPF devera ser unico por entidade quando informado.
- [x] CPF devera ser validado por formato e digitos verificadores.
- [x] UF do RG devera aceitar apenas siglas validas.
- [x] Formularios deverao apresentar mascara e mensagens claras de validacao.
- [x] Operacoes de criacao e atualizacao deverao gerar auditoria.
- [x] Fluxos existentes nao deverao regredir com a ampliacao cadastral.

---

## Tarefas

### Modelagem

- [x] Revisar models de `guardians`, `students` e `teachers` para padronizar os campos:
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
- [x] Definir estrategia de compatibilidade com a model `CustomUser` quando houver sobreposicao de email, nome ou telefone.
- [x] Adicionar constraints e indices para CPF e campos de busca relevantes.

### Services

- [x] Atualizar services de cadastro e edicao para aplicar validacoes de negocio:
  - CPF valido
  - CPF duplicado
  - UF valida
  - email com formato valido
  - obrigatoriedade conforme perfil da entidade
- [x] Garantir escrita com `self._record_audit(...)` em todas as alteracoes.
- [x] Garantir logs sem PII, preservando apenas IDs e contexto tecnico.

### Selectors

- [x] Criar ou ajustar selectors para suportar busca por:
  - nome completo
  - CPF
  - email
  - telefone celular
- [x] Ajustar listagens administrativas para exibir informacoes cadastrais essenciais.

### Forms e Views

- [x] Atualizar forms de Guardian, Student e Teacher com validacoes de campo.
- [x] Ajustar views para lidar com novos campos sem mover regra de negocio para fora dos services.
- [x] Garantir reaproveitamento de widgets e componentes onde fizer sentido.

### Templates

- [x] Atualizar formularios para exibir os novos campos de forma organizada.
- [x] Exibir dados documentais e de contato nas telas de detalhe.
- [x] Garantir consistencia visual com o padrao Duralux.

### Migracoes e Compatibilidade

- [x] Criar migracoes para os novos campos.
- [x] Definir estrategia para dados existentes:
  - campos opcionais (`null=True, blank=True`) permitem compatibilidade com registros existentes
- [x] Revisar impacto em seeds e fixtures de demo.

### Testes

- [x] Testes de model para constraints e validacoes basicas.
- [x] Testes de service para CPF, RG, email e duplicidade.
- [x] Testes de forms e views para fluxos de criacao e edicao.
- [x] Testes de selectors para filtros de busca.

---

## Dependencias

- Sprint 03 concluida
- Sprint 01 concluida
- Sprint 04 concluida para consolidacao de cadastro civil e endereco no mesmo fluxo

---

## Definition of Done

- [x] Todos os criterios de aceite atendidos
- [x] Migracoes aplicadas com sucesso
- [x] Testes atualizados e passando
- [x] Lint e format passing
- [x] Sem regressao nos fluxos atuais de cadastro

---

## Progresso

> Atualizado em 2026-07-01

**Concluido:**
- `base/validators.py` — validadores reutilizaveis: `validate_cpf` (digitos verificadores, 11 digitos, anti-repeticao), `validate_uf` (27 estados brasileiros), `validate_cep` (8 digitos)
- `teachers/models.py`: adicionados `birth_date`, `gender`, `nationality`, `cpf` (unique, nullable), `rg_number`, `rg_issuer`, `rg_state`, `phone_mobile`
- `students/models.py`: adicionados `nationality`, `cpf` (unique, nullable), `rg_number`, `rg_issuer`, `rg_state`, `phone_mobile`, `email`. Indices em `cpf` e `enrollment_number`
- `guardians/models.py`: adicionados `birth_date`, `gender`, `nationality`, `rg_issuer`, `rg_state`, `phone_mobile`. Campo `rg` desmembrado em `rg_number/rg_issuer/rg_state`. Indice em `cpf`
- `TeacherService`: validacao CPF (formato + unicidade) e UF do RG em `create_teacher` e `update_teacher`
- `StudentService`: validacao CPF (formato + unicidade) e UF do RG em `create_student` e `update_student`. `restore_student` mantido
- `GuardianService`: validacao CPF (formato + unicidade) e UF do RG em `create_guardian` e `update_guardian`. Parametro `data` de `link_student` tornado opcional (`None` default)
- `TeacherSelector`: `search_by_cpf`, `search_by_name`
- `StudentSelector`: `search_by_cpf`, `search_by_email`, `search_by_name`
- `GuardianSelector`: `search_by_cpf`, `search_by_phone`, `search_by_name`
- Forms atualizados: `TeacherForm` (novos campos + choices lazy para gender/rg_state), `StudentForm` (novos campos), `GuardianForm` (novos campos, `rg` → `rg_number` + `rg_issuer` + `rg_state`)
- 20 testes de validadores (`base/tests/test_validators.py`) cobrindo CPF, UF e CEP
- Teste `test_only_one_primary` corrigido (o sistema permite multiplos primarios por design)
- Templates de detalhe atualizados: `teacher_detail.html` (secoes Dados Pessoais + Contato), `student_profile.html` (secoes Documentos + Contato), `guardian_detail.html` (secao Dados Pessoais + celular)
- Views `teacher_detail`, `student_profile`, `guardian_detail` atualizadas para passar enderecos via `AddressSelector` e suportar os novos campos
- Tabelas de listagem (`_table.html`) com coluna CPF adicionada para todas as entidades
- 385 testes passando; ruff + black OK

**Pendente:**
- Script de backfill para converter `rg` legado em `rg_number/rg_issuer/rg_state` (se houver dados em producao)
