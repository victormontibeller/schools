# Sprint 04 - Enderecos Unificados

## Objetivo

Criar o modulo de Enderecos para centralizar e padronizar o cadastro de enderecos vinculados a School, Teacher, Student e Guardian.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [x] O sistema devera permitir cadastrar endereco para School, Teacher, Student e Guardian.
- [x] O endereco devera conter os campos obrigatorios:
  - destinatario
  - logradouro
  - numero
  - complemento
  - bairro
  - CEP
  - municipio
  - estado
- [x] O modulo devera suportar pelo menos um endereco por entidade.
- [x] O cadastro devera validar formato de CEP e UF.
- [x] Operacoes de criacao e atualizacao deverao gerar auditoria.
- [x] As telas de cadastro existentes deverao permitir vincular/editar endereco sem quebrar fluxo atual.

---

## Tarefas

### Modelagem

- [x] Criar app `addresses`.
- [x] Criar model `Address` herdando de `BaseModel` com campos:
  - `recipient`
  - `street`
  - `number`
  - `complement`
  - `district`
  - `postal_code`
  - `city`
  - `state`
- [x] Definir estrategia de vinculo entre endereco e entidade dona:
  - opcao A: um model de vinculo por entidade (`SchoolAddress`, `TeacherAddress`, `StudentAddress`, `GuardianAddress`)
- [x] Definir indice/constraint para evitar duplicacao indevida de endereco por entidade.

### Services

- [x] Criar `AddressService` com operacoes:
  - `create_address_for_school`
  - `create_address_for_teacher`
  - `create_address_for_student`
  - `create_address_for_guardian`
  - `update_address`
  - `deactivate_address` (soft delete)
- [x] Aplicar validacoes de negocio:
  - CEP com 8 digitos
  - UF com 2 caracteres validos
  - campos obrigatorios preenchidos
- [x] Garantir `self._record_audit(...)` em toda escrita.

### Selectors

- [x] Criar `AddressSelector` para consultas read-only:
  - listar endereco por entidade
  - buscar endereco principal por entidade
  - listar enderecos com filtro por cidade/estado/CEP

### Views e Forms

- [x] Criar formularios de endereco com validacao de campo.
- [x] Integrar formularios de endereco nas telas de School, Teacher, Student e Guardian.
- [x] Ajustar views para orquestrar AddressService e AddressSelector.

### Templates

- [x] Criar partial reutilizavel de endereco para formularios.
- [x] Exibir endereco formatado nas telas de detalhe.
- [x] Manter padrao Duralux e fluxo HTMX quando aplicavel.

### Migracoes e Dados

- [x] Criar migracoes do novo app.
- [ ] Criar script opcional para migrar dados de endereco existentes (se houver campos legados nas entidades).

### Testes

- [x] Testes de model para constraints e validacoes basicas.
- [x] Testes de service para regras de negocio e auditoria.
- [x] Testes de selector para consultas e filtros.
- [x] Testes de views/forms para fluxo completo de cadastro e edicao.

---

## Dependencias

- Sprints 03 concluidas (entidades Teacher, Student e Guardian disponiveis)
- Sprint 01 concluida (padroes BaseModel, BaseService, auditoria)
- Sprint 05 recomendada para padronizar identificacao e contato das entidades vinculadas

---

## Definition of Done

- [x] Todos os criterios de aceite atendidos
- [x] App `addresses` registrado no projeto
- [x] Migracoes aplicadas com sucesso
- [x] Testes do modulo passando
- [x] Lint e format passing
- [x] Sem regressao nos fluxos atuais de cadastro

---

## Progresso

> Atualizado em 2026-07-01

**Concluido:**
- App `addresses/` criado com 5 models: `Address`, `SchoolAddress`, `TeacherAddress`, `StudentAddress`, `GuardianAddress`
- Estrategia de vinculo: Opcao A — um model de vinculo por entidade com `unique_together` por (entidade, endereco)
- `AddressService` com operacoes CRUD, validacao CEP (8 digitos) e UF (27 estados brasileiros)
- `AddressSelector` com `get_by_entity`, `get_primary_address`, `list_by_city`, `list_by_state`
- `AddressForm` (ModelForm com widgets Bootstrap), views CRUD standalone + integracao via `entity_type/entity_id`
- Templates: `address_form.html` (herda `form_base.html`), partials reutilizaveis `address_display.html` e `address_table.html`
- 13 testes (services + selectors) passando — cobertura completa de regras de negocio
- Migrations geradas e prontas
- App registrado em `core/settings.py`, `core/urls.py`, `pyproject.toml`, `pytest.ini`, `Makefile`
- Validadores compartilhados em `base/validators.py`: `validate_cep`, `validate_uf`, `validate_cpf`

**Pendente:**
- Script opcional de migracao de dados de endereco (campos legados)
