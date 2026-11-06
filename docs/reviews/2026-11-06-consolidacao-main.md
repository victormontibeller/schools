# Consolidação do piloto na main — 06/11/2026

Publicação do trabalho acumulado do piloto de Educação Infantil que ainda estava na árvore
local, tomando `b4773eb` como base. O escopo funcional e os gates de operação real permanecem
documentados em `docs/37_PILOT_IMPLEMENTATION.md`.

## Ajustes desta revisão

- Recuperação de comunicações isola falhas por escola, comunicado, entrega e atendimento.
  Uma falha individual permite continuar os demais itens. Logs registram apenas identificadores
  opacos, schema e classe da exceção, sem mensagem da exceção ou traceback.
- Sete regressões cobrem continuidade, restauração do contexto e ausência de dados privados nos
  logs. A revisão independente confirmou o encerramento do achado.
- `pypdf` atualizado para 6.21.4 e `msgpack` para 1.2.3 após avisos do `pip-audit`.
- `pip-tools` atualizado para 7.6.2 para corrigir incompatibilidade do 7.5.2 com `pip` 26.2.2.
  Os dois locks foram regenerados com hashes, usando Python 3.13.

## Validação local

Foi usado ambiente temporário Python 3.13 instalado exclusivamente do lock de desenvolvimento.
A `.venv` existente usava Python 3.14 e Black 24; a validação canônica usou Black 26.10.1.
Caches Python foram direcionados a `/private/tmp` para evitar esperas por arquivos do OneDrive.

| Verificação | Resultado |
|---|---|
| Suíte geral SQLite | 1.614 aprovados; 104 testes de outros perfis desmarcados |
| Cobertura global | 86,79%; mínimo 85% |
| Cobertura dos fluxos críticos do CI | 90,25%; mínimo 90% |
| Chromium | 45 aprovados |
| Uploads de PDF, recibos e extratos com `pypdf` 6.21.4 | 55 aprovados |
| Ruff e Black | Aprovados |
| Contratos de imports, services e UI | Aprovados |
| Grafo de pré-produção | 31 migrations permitidas |
| `makemigrations --check --dry-run` | Sem drift |
| `check --deploy --fail-level WARNING` | Sem problemas |
| `collectstatic` temporário | Manifesto e CSS com hash conferidos |
| `pip-audit` do lock completo de desenvolvimento | Sem vulnerabilidades conhecidas |
| `pip check` após instalar o lock final | Sem incompatibilidades |
| Revisão independente e `git diff --check` | Sem pendências identificadas |

A suíte geral foi executada antes da instalação da correção pontual do `pypdf`; os testes de
upload de arquivos, recibos e extratos foram repetidos após essa atualização. PostgreSQL/Redis,
Gitleaks, Trivy e implantação não foram reexecutados nesta consolidação. A evidência histórica
de 25/10 e os gates ainda externos estão no documento 37; esta publicação não declara entrada
em produção nem executa reset dos ambientes dev/demo.

## Churn do lote consolidado

Contagem de arquivos em relação a `b4773eb`, incluindo este relatório. Produto inclui
configuração, infraestrutura e dependências; testes incluem fixtures e configuração do pytest.

| Categoria | Arquivos |
|---|---:|
| Produto e configuração | 193 |
| Testes | 65 |
| Migrations | 30 |
| Documentação | 18 |
| Total | 306 |

Os caminhos legados removidos pelo lote do piloto são:

- `enrollments/tasks.py` e `enrollments/tests/test_tasks.py`;
- `guardians/tasks.py` e `guardians/tests/test_tasks.py`;
- `students/tasks.py` e `students/tests/test_tasks.py`;
- `notifications/tests/test_calendar_on_commit.py`;
- `notifications/tests/test_celery_tasks.py`.

Os consumidores dos módulos removidos foram conferidos na revisão. A correção de recuperação
desta revisão usa o fluxo canônico existente e não adiciona migrations.

## Histórico Git

Foi criado e verificado um bundle completo antes da limpeza das branches, preservado localmente
em `.git/schools-branches-20261106.bundle`. A limpeza abrange as dez branches antigas do
Dependabot e a branch do Copilot, cujo único commit exclusivo era vazio. O objetivo da publicação
é manter apenas `main` nos heads locais e remotos, sem reescrever o histórico da `main`.

## Acompanhamento do CI — imagem Docker

O primeiro CI de `440ca09` identificou a CVE-2026-109518 nos pacotes Debian `apt` e
`libapt-pkg7.0` 3.0.3 da imagem final. O scan dos arquivos e dependências Python passou; o scan
da imagem bloqueou a publicação por duas ocorrências HIGH da mesma vulnerabilidade.

Os estágios builder e runtime agora atualizam explicitamente esses pacotes antes das demais
dependências. O bootstrap usa `Acquire::Retries=0`, mitigação documentada para a versão antiga,
e instala a correção disponível em `trixie-security` (3.0.4 ou posterior). Referência:
[Debian Security Tracker](https://security-tracker.debian.org/tracker/CVE-2026-109518).
O digest base e os critérios bloqueantes do Trivy são preservados; a verificação da imagem
corrigida ocorre no build e scan reais do CI.

Churn deste ajuste: um arquivo de infraestrutura (`Dockerfile`, quatro linhas adicionadas),
um documento atualizado, zero arquivos de testes ou migrations e nenhum caminho legado removido.

## Acompanhamento do CI — interpretador do teste de reset

A suíte SQLite remota encontrou uma dependência indevida da fixture em `./.venv/bin/python`:
esse caminho existe no desenvolvimento local, mas o runner instala dependências no Python de
`actions/setup-python`. O teste agora informa `PYTHON_BIN=sys.executable`, usando a opção já
suportada pelo script. A asserção de recusa de host remoto e a prova de que `psql` não foi chamado
continuam sendo verificadas. O script de reset não foi executado contra bancos locais/reais.

Churn deste ajuste: um arquivo de teste com duas linhas adicionadas e este documento; zero
alterações de produto ou migrations e nenhum caminho legado removido.
