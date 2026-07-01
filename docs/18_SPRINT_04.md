# Sprint 04 - Enderecos Unificados

## Objetivo

Criar o modulo de Enderecos para centralizar e padronizar o cadastro de enderecos vinculados a School, Teacher, Student e Guardian.

## Duracao Estimada

2 semanas

---

## Criterios de Aceite

- [ ] O sistema devera permitir cadastrar endereco para School, Teacher, Student e Guardian.
- [ ] O endereco devera conter os campos obrigatorios:
  - destinatario
  - logradouro
  - numero
  - complemento
  - bairro
  - CEP
  - municipio
  - estado
- [ ] O modulo devera suportar pelo menos um endereco por entidade.
- [ ] O cadastro devera validar formato de CEP e UF.
- [ ] Operacoes de criacao e atualizacao deverao gerar auditoria.
- [ ] As telas de cadastro existentes deverao permitir vincular/editar endereco sem quebrar fluxo atual.

---

## Tarefas

### Modelagem

- [ ] Criar app `addresses`.
- [ ] Criar model `Address` herdando de `BaseModel` com campos:
  - `recipient`
  - `street`
  - `number`
  - `complement`
  - `district`
  - `postal_code`
  - `city`
  - `state`
- [ ] Definir estrategia de vinculo entre endereco e entidade dona:
  - opcao A: um model de vinculo por entidade (`SchoolAddress`, `TeacherAddress`, `StudentAddress`, `GuardianAddress`)
  - opcao B: generic relation com `content_type` e `object_id`
- [ ] Definir indice/constraint para evitar duplicacao indevida de endereco por entidade.

### Services

- [ ] Criar `AddressService` com operacoes:
  - `create_address_for_school`
  - `create_address_for_teacher`
  - `create_address_for_student`
  - `create_address_for_guardian`
  - `update_address`
  - `deactivate_address` (soft delete)
- [ ] Aplicar validacoes de negocio:
  - CEP com 8 digitos
  - UF com 2 caracteres validos
  - campos obrigatorios preenchidos
- [ ] Garantir `self._record_audit(...)` em toda escrita.

### Selectors

- [ ] Criar `AddressSelector` para consultas read-only:
  - listar endereco por entidade
  - buscar endereco principal por entidade
  - listar enderecos com filtro por cidade/estado/CEP

### Views e Forms

- [ ] Criar formularios de endereco com validacao de campo.
- [ ] Integrar formularios de endereco nas telas de School, Teacher, Student e Guardian.
- [ ] Ajustar views para orquestrar AddressService e AddressSelector.

### Templates

- [ ] Criar partial reutilizavel de endereco para formularios.
- [ ] Exibir endereco formatado nas telas de detalhe.
- [ ] Manter padrao Duralux e fluxo HTMX quando aplicavel.

### Migracoes e Dados

- [ ] Criar migracoes do novo app.
- [ ] Criar script opcional para migrar dados de endereco existentes (se houver campos legados nas entidades).

### Testes

- [ ] Testes de model para constraints e validacoes basicas.
- [ ] Testes de service para regras de negocio e auditoria.
- [ ] Testes de selector para consultas e filtros.
- [ ] Testes de views/forms para fluxo completo de cadastro e edicao.

---

## Dependencias

- Sprints 03 concluidas (entidades Teacher, Student e Guardian disponiveis)
- Sprint 01 concluida (padroes BaseModel, BaseService, auditoria)
- Sprint 05 recomendada para padronizar identificacao e contato das entidades vinculadas

---

## Definition of Done

- [ ] Todos os criterios de aceite atendidos
- [ ] App `addresses` registrado no projeto
- [ ] Migracoes aplicadas com sucesso
- [ ] Testes do modulo passando
- [ ] Lint e format passing
- [ ] Sem regressao nos fluxos atuais de cadastro
