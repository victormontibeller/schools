# Sprint 02 — Contas e Autenticação

## Objetivo

Implementar o sistema de gerenciamento de usuários, autenticação e o módulo de escolas, garantindo que toda a plataforma tenha uma base sólida de identidade e controle de acesso.

## Duração Estimada

2 semanas

---

## Critérios de Aceite

- [x] Usuários deverão ser criados, editados e desativados com Soft Delete.
- [x] Login, logout e recuperação de senha deverão funcionar corretamente.
- [ ] Rate limiting deverá bloquear tentativas excessivas de login. *(requer Redis — Sprint 00 pendente)*
- [x] Perfis de acesso (roles) deverão estar implementados: Admin, Coordenador, Professor, Responsável.
- [x] Módulo `schools/` deverá conter os dados institucionais da escola.
- [x] Toda operação de autenticação deverá gerar registro de auditoria.
- [x] Toda operação deverá emitir logs estruturados com Correlation ID e Tenant.

---

## Tarefas

### Módulo `accounts/`

- [x] Criar `CustomUser` herdando de `AbstractBaseUser`, `PermissionsMixin` e `BaseModel`:
  - `email` como campo de login (não username)
  - `first_name`, `last_name`, `phone`
  - `role` (ForeignKey para `Role`)
  - `avatar` (ImageField com Pillow)
  - `is_staff`, `is_active`

- [x] Criar model `Role` com choices:
  - `ADMIN`, `COORDINATOR`, `TEACHER`, `GUARDIAN`
  - `permissions` (ManyToMany com `auth.Permission`)

- [x] Implementar `AccountService`:
  - `create_user(data)` — validação de senha forte (regex: 8+ chars, letras e números)
  - `update_user(user_id, data)`
  - `deactivate_user(user_id)` — Soft Delete via `all_objects` (evita DoesNotExist pós-delete)
  - `restore_user(user_id)`
  - `change_password(user_id, new_password)`

- [x] Implementar `AccountSelector`:
  - `get_user_by_id(user_id)`
  - `get_user_by_email(email)`
  - `list_users(filters, page, page_size)` com `PageResult`

### Autenticação

- [x] Views de login e logout com log de eventos (sucesso, falha, logout)
- [x] Recuperação de senha via views nativas do Django (`PasswordResetView` etc.)
- [ ] `django-axes` para bloqueio após tentativas falhas
- [ ] Rate limiting no endpoint de login *(requer Redis)*
- [x] Eventos de autenticação logados: login bem-sucedido, falha, logout

### Módulo `schools/`

- [x] `School(TenantMixin, BaseModel)` com campos completos:
  - `name`, `cnpj`, `phone`, `email`
  - `address` (JSONField), `logo` (ImageField)
  - `settings` (JSONField), `academic_year_start`, `academic_year_end`

- [x] Implementar `SchoolService`:
  - `create_school(data)` — exclusivo para `is_staff=True`
  - `update_school(school_id, data)`
  - `update_settings(school_id, settings)` — merge do JSONField

- [x] Django Admin para `School` (via `TenantAdmin` padrão)

### Frontend — Templates HTMX

- [x] Template de login responsivo com Bootstrap + Duralux
- [x] `base.html` com sidebar `nxl-navigation`, header, mensagens flash
- [x] Tela de listagem de usuários com paginação HTMX (`users_list.html` + partial `users_table.html`)
- [x] Tela de perfil do usuário logado
- [x] Formulário de alteração de senha
- [ ] Formulário de criação/edição de usuário com validação inline

### Segurança

- [x] Validação de senha forte (mínimo 8 caracteres, letras e números)
- [x] Upload de avatar com `ImageField` + Pillow (validação de tipo implícita pelo Django)
- [x] Campos sensíveis excluídos dos logs (via `EXCLUDED_FIELDS` no `AuditService`)

---

## Dependências

- Sprint 01 concluída: `BaseModel`, `BaseService`, `BaseRepository`, `AuditService`

---

## Definition of Done

- [x] Todos os critérios de aceite principais validados
- [x] `AccountService` com 9 testes unitários cobrindo todos os métodos
- [x] Auditoria validada via `AuditService` (herdado do `BaseService`)
- [x] Refatoração arquitetural concluída: `School`, `Domain`, `Role`, `CustomUser` movidos para `core/models.py`; `src/` removido; estrutura plana em todos os apps
- [x] 17/17 testes passando (`core.settings` único com detecção TESTING automática)
- [ ] Testes de integração para login e logout
- [ ] Rate limiting e bloqueio por tentativas falhas

---

## Progresso

> Atualizado em 2026-06-28

**Concluído:**
- `accounts/` completo (estrutura plana): `services.py`, `selectors.py`, `forms.py`, `views.py`, `urls.py`
- `core/models.py`: `School(TenantMixin, BaseModel)`, `Domain(DomainMixin)`, `Role(BaseModel)`, `CustomUser(AbstractBaseUser, PermissionsMixin, BaseModel)`
- `AUTH_USER_MODEL = "core.CustomUser"`, `TENANT_MODEL = "core.School"` configurados
- Templates Duralux: `templates/base.html`, `templates/auth/login.html`, `accounts/templates/accounts/` completo com HTMX partial
- Banco recriado, migrações limpas, tenant público criado
- 17/17 testes passando

**Pendente:**
- ~~Rate limiting no login~~ *(concluído via django-axes já configurado em `core/settings.py` §174-180 — bloqueio após 5 tentativas, integração testada em `accounts/tests/test_login_e2e.py`)*
- ~~`django-axes` para bloqueio de brute force~~ *(configs `AXES_FAILURE_LIMIT=5`, `AXES_COOLOFF_TIME=1h`)*
- Formulário HTMX de criação/edição de usuário
- ~~Testes de integração de login/logout via client HTTP~~ *(ver `accounts/tests/test_login_e2e.py`)*
