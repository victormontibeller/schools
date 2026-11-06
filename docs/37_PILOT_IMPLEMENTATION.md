# Implementação do piloto — acompanhamento e implantação assistida

Esta página registra a entrega por etapas. Ela não declara a escola pronta para operação real.
Homologação prevista: **Escola Piloto Ipê**, schema `piloto`, domínio `piloto.localhost`, pessoas e
endereços `example.test` fictícios, transporte de e-mail simulado/local.

## Etapa 1 — identidade, integridade e carga

Implementados: bootstrap auditado pela plataforma, habilitação de Agenda pela edição da escola,
convites administrativos, nonce de sete dias compartilhado com os convites docentes/familiares,
proteção do último administrador, preservação do papel principal, versões da chamada, escopo
ativo docente e relatório de risco, cronologia financeira e recebimento por competência.
Atalhos da home consultam a mesma política de permissões das rotas.

O cadastro da criança continua sem conta no piloto. Responsáveis com guarda têm sua identidade
ativada depois da conferência. Pessoa apenas autorizada à retirada permanece contato sem conta.
O operador público prepara a escola e o primeiro acesso, sem impersonação. O administrador
ativado convida substituto, Secretaria, Coordenação e Financeiro em **Usuários → Novo**.

Convite pendente mostra emissão e vencimento na ficha do usuário. Reenviar invalida o link
anterior; trocar o e-mail exige nova emissão. Conta já ativada usa recuperação de senha. A
ativação não inscreve a pessoa em alertas e os alertas não condicionam o acesso. O fluxo de
convite depende de processamento e homologação do provedor; e-mail agendado não significa
entregue. Falhas operacionais devem ser acompanhadas nos registros de transporte.

## Importação assistida

Usar os cabeçalhos UTF-8 em `docs/import_templates/`. CSV usa vírgula, datas `AAAA-MM-DD`,
CPF válido quando informado e identificadores de origem estáveis. `relationship_type` segue os códigos de
parentesco (`MAE`, `PAI`, `LEGAL`, `OUTRO` etc.). `is_primary`, `has_custody` e `can_pickup`
aceitam somente `0` ou `1`; responsável principal exige guarda confirmada. Os campos de pessoa
obrigatórios seguem o cadastro canônico atual. Limite: 5 MB e 10000 linhas por arquivo.

Executar no ambiente configurado com um ator ativo do próprio tenant, autorizado para alunos e
responsáveis. A saída contém contagens e referência do lote, sem reproduzir dados pessoais:

```sh
python manage.py import_school_data --schema piloto --actor UUID_DO_ADMIN \
  --source-key piloto-carga-01 --students /carga/students.csv \
  --guardians /carga/guardians.csv --links /carga/links.csv
```

O padrão é prévia sem escrita. Corrigir todas as linhas apontadas e repetir. Depois da conferência,
usando os mesmos argumentos, acrescentar `--apply`. Guardar o UUID retornado e reconciliar:
quantidade de alunos, responsáveis e vínculos; cada criança com guarda documentada; responsável
principal correto; autorização de retirada distinta da guarda. A carga não cria nem presume
matrículas: configurar ano/turmas/professores e efetivar solicitações no workflow de matrícula.
Somente após a conferência integral emitir convites às famílias.

Mesmo identificador e arquivos retornam o lote existente sem duplicar registros. Alterar conteúdo
exige nova prévia com novo identificador e reconciliação dos conflitos; nunca reescrever CPF
existente ou restaurar automaticamente cadastro desativado. Falha durante escrita/auditoria
reverte toda a transação e permite corrigir e tentar novamente.

Antes de qualquer uso operacional, um lote intacto pode ser desfeito:

```sh
python manage.py import_school_data --schema piloto --actor UUID_DO_ADMIN --revert UUID_DO_LOTE
```

A reversão é lógica, atômica e auditada. Qualquer edição, matrícula, conta, vínculo externo,
chamada, Agenda, contrato ou outro registro dependente impede a reversão. Após uso, aplicar
correções nos services/telas do domínio, preservando a história. Não reaplicar lote desfeito.

## Integração final e liberação real

As etapas abaixo registram a homologação dirigida, atualização de dependências e o ensaio fictício.
A suíte, a cobertura e os ensaios locais estão consolidados ao final desta página. Permanecem os
gates externos, incluindo treinamento real, marco anterior à carga real e acompanhamento de
quatro semanas.

O grafo inicial intermediário foi regenerado pelo Django, preservando os seeds de localidades e
Agenda. Testes da etapa 2 já usam migrations reais. Nenhum banco ou arquivo preexistente foi
resetado; os testes PostgreSQL recriam somente o banco temporário isolado. O grafo foi novamente regenerado com os models de atendimento (31 migrations), antes da consolidação final.

## Etapa 2 — central de comunicados e recuperação

Implementados: autoria Admin/Coordenação, rascunhos versionados, prévia de destinatários,
publicação/agendamento/cancelamento, correções com histórico, anexos privados, audiência vigente,
visualização autenticada e ciência explícita por revisão. Secretaria, Financeiro, docentes e
famílias consultam os comunicados efetivamente destinados às suas contas.

Operação: **Comunicados → Novo comunicado → Salvar → Conferir prévia/anexos → Publicar agora**
ou informar data/hora e **Agendar publicação**. Para corrigir, abrir uma correção na ficha, editar
e publicar; a revisão anterior permanece disponível. A família usa **Estou ciente** quando
solicitado; notificações lidas não substituem essa ação.

A ficha apresenta estados individuais de sistema/e-mail, visualização e ciência. Falhas não
impedem os demais destinatários. Corrigir endereço, configuração do remetente ou elegibilidade
antes de **Criar novo envio após corrigir a causa**. A ação cria geração auditada, sem alterar o
log anterior; retry técnico automático preserva a identidade e o payload originais. Preferência
desabilitada exige escolha da própria pessoa, nunca alteração pela equipe para forçar envio.

O worker precisa de contexto de tenant; Beat executa `notifications.recover_communications` a
cada minuto. Monitorar worker, Beat e intenções vencidas. Publicado, aceito pelo provedor,
entregue, visualizado e ciente são estados distintos. Mensagens externas da central e da Agenda
são genéricas, sem dados da criança. Consulte ADR-0023 para limites de idempotência e configuração.

## Evidência da etapa 1 (2026-10-25)

Runtime isolado Python 3.13.14/Django 5.2.17 em `/tmp/schools-pilot-venv`, sem alterar bancos
existentes. Rodada integrada: `pytest --nomigrations -q accounts/tests students/tests
attendance/tests financeiro/tests guardians/tests tenancy/tests core/tests dashboard/tests
--ignore=financeiro/tests/test_migrations.py --disable-warnings`: **700 passaram, 65 excluídos
pelos marcadores padrão de tenant/UI**. Após ajustes finais, 27 testes focados passaram; as
últimas regressões de entrega com URL docente real e de autorização da reversão passaram em
rodadas próprias (8 contas e 7 importação). Ruff, Black e verificadores de contratos de imports,
services e UI passaram. PostgreSQL/bootstrap cross-schema, corrida do último administrador,
navegador e cobertura global ainda precisam da consolidação final do grafo.

A corrida entre reversão de lote e criação simultânea de matrícula/vínculo exige validação e
alinhamento de locks no PostgreSQL: o lock administrativo do importador não serializa todos os
services que criam dependências. A conferência de manifesto e os locks dos objetos não substituem
essa prova. Reversão concorrente permanece pendência de segurança antes do piloto real.

## Evidência da etapa 2 (2026-10-25)

Grafo real, sem `--nomigrations`: `pytest -q notifications/tests student_diary/tests
dashboard/tests core/tests/test_ui_contracts.py --disable-warnings` passou **213 testes**, com
3 cenários PostgreSQL excluídos pelo marcador padrão. A rodada PostgreSQL isolada
`DJANGO_ENV=test_pg pytest -m tenant -q notifications/tests/test_outbox_tenant.py
accounts/tests/test_pilot_tenant.py` passou **5 testes**: claim com joins anuláveis, claim
concorrente com único vencedor, webhook duplicado concorrente, preservação do último admin e
bootstrap sem FK/sessão do operador público dentro do tenant.

`pytest -m ui -q notifications/tests/test_announcement_ui.py --browser chromium` passou **6
jornadas** (1280×720, 1280×480, 390×844; JavaScript ligado/desligado). Autoria, publicação,
listagem sem overflow e ciência familiar foram executadas no navegador, com provedores simulados.
O primeiro ensaio PostgreSQL falhou na preparação de domínio fictício com underscore; o fixture
foi corrigido e passou a garantir limpeza do schema também quando a preparação falha. O primeiro
ensaio Chromium usou rótulo sem considerar a marca de campo obrigatório; o seletor foi corrigido.
Essas falhas de teste não foram omitidas nem usadas para desativar cenários.

Ruff, Black, verificadores de importação/services/UI/pré-produção e `makemigrations --check
--dry-run` passaram. Essa evidência é da etapa: não substitui suíte/cobertura global, validação
final dos outros domínios, ensaio de recuperação banco+mídia nem homologação de provedor real.

Após o fechamento, `pytest -q notifications/tests/test_announcement_authoring.py
notifications/tests/test_outbox_recovery.py` passou **21 testes**, incluindo os ajustes finais de
objeto inexistente, anexo de outro rascunho e redação de auditoria. A revisão dirigida do guardião
encerrou os achados de outbox sem novas observações; foi somente leitura, separada das execuções
registradas acima.


## Etapa 3 — solicitações e matriz de avisos

Implementados os setores privados, vínculos de atendentes, calendário administrativo, prazo de
primeira resposta, reabertura, transferência e mensagens/anexos imutáveis. Administração configura
**Atendimento → Solicitações → Configurar atendimento**, informa contato imediato, dias e
fechamentos e habilita os setores com responsáveis ativos. Secretaria, Coordenação e Financeiro
acompanham a lista do próprio setor; a família abre pelo mesmo menu e vê apenas suas conversas.
A ficha explicita a próxima ação: equipe analisando, aguardando a família, resolvida ou cancelada.
O histórico mostra os nomes dos eventos e estados, sem códigos internos.

Mudança de estado não cumpre a primeira resposta: enviar mensagem humana pública. Para transferir,
Administração escolhe um setor habilitado; o prazo permanece. Para continuar após resolução, o
autor usa **Reabrir e iniciar novo prazo**. Contactar a escola pelo contato imediato quando não
for possível esperar. Não habilitar setor sem cobertura de equipe e substituto operacional.

Atividade consultável e calendário público avisam as famílias com guarda e matrícula vigentes;
matrícula efetivada/pendência documental avisam o principal; baixa/estorno/lembrete exigem acesso
financeiro. O aviso documental direciona ao atendimento da Secretaria, preservando o fluxo
escolar de entrega de documentos. **Atendimento → Entregas** permite acompanhamento e novo envio
individual após corrigir a causa, dentro das capacidades de cada domínio. Falha do e-mail não
remove a atualização do sistema.

A ADR-0024 documenta a atomicidade dos produtores, interseção guarda/turma, projeção dos lembretes
e o clean break dos workers anteriores. Convites/recuperação de acesso continuam separados da
preferência de alertas. Esta etapa não executou envio real nem declara prontidão operacional.

## Evidência da etapa 3 (2026-10-25)

Com migrations reais, `pytest -q accounts core notifications service_requests enrollments
financeiro activities academic_calendar guardians student_diary dashboard -m 'not tenant and not
ui'` passou **938 testes**; 91 cenários dos outros marcadores foram excluídos nessa rodada.
A primeira rodada teve 16 falhas de consumidores/testes antigos (taxonomia, comunicado antigo,
Beat substituído e gateway sem escola); após o clean break, os 78 testes diretamente afetados
passaram e a rodada integrada acima também passou. Não foram excluídas regressões de segurança.

`DJANGO_ENV=test_pg pytest -m tenant -q service_requests/tests/test_tenant.py` passou **4 testes**
em schemas isolados: último atendente em corrida de desativação, respostas concorrentes com
versão obsoleta, consulta de protocolo de outro tenant e reenvio de convite com papel anulável.
`pytest -q base/tests/test_events.py` passou **55 testes**, incluindo propagação obrigatória de
falha antes dos observadores opcionais. A matriz teve mais **22 testes focados verdes** com o
atendimento, incluindo rollback financeiro quando o outbox falha, irmãos sem filho elegível,
CLASS sem turma, reprocessamento pelo Financeiro sem edição de comunicados e perda de acesso
financeiro antes do worker.

`pytest -q service_requests/tests -m 'not tenant and not ui' --cov=service_requests
--cov-report=term-missing --cov-fail-under=85` passou **15 testes**, com **90,29% de cobertura** do
novo app. Essa medição localizada não substitui o gate de cobertura global/áreas críticas.
Ruff, Black, verificadores de services/imports/UI/pré-produção e `makemigrations --check --dry-run`
passaram. O grafo tem 31 migrations iniciais/seeds autorizados; nenhum banco preexistente foi
resetado. Provedores externos foram simulados, sem envio real.


`pytest -m ui -q service_requests/tests/test_ui.py` passou **6 jornadas** no Chromium: 1280×720,
1280×480 e 390×844, com JavaScript ligado/desligado. Criar com PNG sintético, baixar anexo privado,
responder, resolver e reabrir foram exercitados pelo navegador. O formulário inicial recebeu
`multipart/form-data` após a verificação identificar a ausência desse atributo.

Os ensaios iniciais não foram verdes: a troca de cookies entre personas e polling no live_server
SQLite produziu perda de sessão; depois, a rolagem suave deixava o botão em movimento ao iniciar
o clique sem JavaScript. A fixture final usa sessões/contextos independentes, mantém o isolamento
canônico do polling de notificações e observa scrollY e retângulo estáveis em três leituras,
sem animações em execução, antes do clique normal. Não há clique forçado, espera de navegação
suprimida ou aumento de timeout. A observação usa polling externo, pois temporizadores da página
não são confiáveis no contexto com scripts desabilitados. Os testes HTTP de privacidade/arquivos
permanecem reais; esse isolamento do polling no SQLite não equivale a uma homologação concorrente
de sessões/inbox no servidor PostgreSQL de produção.

A revisão dirigida do guardião encerrou três achados de integração: atomicidade obrigatória da
intenção, interseção guarda/matrícula do mesmo filho e calendário CLASS sem turma. Permanecem os
gates da etapa operacional, especialmente corrida de reversão da carga, dependências, cobertura
global, recuperação, worker/broker e provedores reais. Os resultados acima são da escola fictícia.

## Etapa 4A — integridade da carga, acesso e dependências

A proveniência da carga agora acompanha aluno, responsável e vínculo. O primeiro uso operacional
sela o lote atomicamente, antes dos locks das raízes. Reversão só aceita lote ainda não usado;
instâncias antigas não permitem usar registros revertidos. A recuperação explícita
`import_school_data --schema <escola> --actor <UUID> --restore <lote>` restaura o manifesto inteiro,
com os mesmos IDs, e deixa o lote selado para edição auditada. CPF ativo de responsável tem
constraint no banco, inclusive na disputa entre restauração e cadastro substituto. Inventário de
produtores e ordem dos locks estão na ADR-0025.

Educação Infantil não exige inventar contato digital, CPF, RG ou tipo sanguíneo da criança.
Nome, sobrenome e nascimento identificam o cadastro; documentos pendentes seguem a Secretaria.
CSV mantém `source_id` obrigatório e independente de CPF/e-mail. CPF informado é validado;
valores vazios não são duplicatas. Crianças não recebem conta nem preferências de alertas no
cadastro. E-mail da pessoa responsável/autorizada à retirada também pode estar ausente; o convite
exige endereço e nunca é disparado pela carga. Guarda e retirada continuam independentes.

Recuperação preserva CSRF, protocolo e SMTP Django, mas confirma a senha em comando auditado,
com token vinculado ao schema e revalidado sob lock. Limites compartilhados usam HMAC/Redis,
resposta genérica e `Retry-After`; indisponibilidade do cache impede envio. Falha SMTP é registrada
por código técnico fixo, sem exceção bruta que possa conter destinatário ou token. Recuperação
extraordinária exige prova de identidade institucional e ocorrência, conforme ADR-0025.

Locks foram atualizados seletivamente para as versões corrigidas de Pillow, pypdf, certifi,
urllib3, OpenTelemetry e ferramentas de desenvolvimento. A instalação por hashes usa somente o
runtime temporário da tarefa. O Dockerfile usa digest renovado e remove pip dos dois ambientes de
runtime após instalação. Build/scan da imagem final ainda depende de Docker e não é comprovado
pela verificação de dependências Python ou da imagem base.

As evidências deste lote estão abaixo. Nenhuma carga real, envio externo ou entrada em produção
é autorizada por esta etapa.

### Evidência de validação da etapa 4A

- PostgreSQL + Redis reais isolados: **11 testes aprovados**, incluindo as duas ordens de
  undo×matrícula/vínculo/contrato, restauração×CPF substituto, rollback, consumo concorrente do
  reset e limite Redis entre conexões. Log: `/tmp/pilot-stage4-security-pg.log`.
- Cadastro infantil, importação/reversão/restauração, responsáveis e recuperação: **100 testes
  aprovados**, incluindo carga sem e-mail/documentos da criança e undo→restore dos mesmos IDs.
- Pillow/pypdf/tracing e mídia: **142 testes aprovados** no runtime atualizado.
- Chromium sem JavaScript: **3 jornadas aprovadas** (convite docente, familiar e reset), com
  CSRF/Referer e senha final conferidos. O comando usa o perfil UI do Makefile, não um ajuste de
  configuração de produção.
- Produtores: **589 aprovados e 1 falha** na primeira rodada. A falha era o contrato de erro de
  aluno inexistente na justificativa; corrigida e revalidada pelos **53 testes de frequência**.
  O teste não foi removido nem enfraquecido. Gate global permanece na etapa 4B.
- `pip check`: sem incompatibilidades. `pip-audit`: **0 avisos conhecidos** nos 73 pacotes do lock
  de produção e nos 133 do lock de desenvolvimento, em 2026-10-25. Instalação por hashes limitada
  a `/tmp/schools-pilot-venv`; `.venv` existente preservada.
- Ruff, Black 26.10.1, contratos de importação/services/UI, grafo pré-produção (31 migrations) e
  `makemigrations --check --dry-run` aprovados. Black renovado reformata três arquivos de testes
  preexistentes, além da formatação de testes novos; não há mudança visual correspondente.

O reset PostgreSQL ocorreu somente nos bancos/schemas de testes temporários. A aplicação no
ambiente fictício e sua reconstrução continuam na etapa operacional. Sem envio SMTP/Resend real,
sem cliente/dados reais, sem build/scan Docker final e sem declaração de prontidão produtiva.

## Etapa 4B — operação e escola fictícia (25–26/10/2026)

Entregues modo fictício restrito, escola completa reproduzível, capturas privadas de convites e
reset, convites na outbox durável, exportação autorizada com allowlist/histórico/mídia,
backup/restauração em destinos novos, monitor independente e runbook de saída/transição.
A revisão final acrescentou autorização vigente após lock administrativo, revogação docente nas
capacidades, separação create/edit de comunicados, capacidade completa do atendente e links
financeiros compatíveis com cobranças. Calendário global elimina contexto de turma residual.
Primeira baixa lançada após apuração usa a data efetiva sem encargos indevidos; histórico de
baixas confirmadas/estornadas continua imutável e exige reconciliação assistida quando retroativo.

### Evidência local e localização

Somente dados fictícios em `/tmp/schools-pilot-local-20261025` (0700). Ambiente/credenciais em
`environment.sh` e `access.json` (0600); não publicar seus conteúdos. Banco novo
`schools_pilot_fictitious_20261025`, origem http://piloto.localhost:18080/ e comparação
http://piloto-comparacao.localhost:18080/. O banco temporário anterior `schools_pilot_dev` foi
preservado: revisão automática recusou sua recriação e a alternativa de banco novo foi adotada.

Backup `backups/recovery-exercise.zip`, ponto UTC `2026-10-26T01:34:49.050777+00:00`;
restauração `schools_pilot_restored_20261025` e pasta `restored/`, servidor local 18081,
Redis DB2 separado da origem DB0. Idade do ponto no ensaio: **2,65 segundos**; restauração:
**2,18 segundos**. Dump e arquivo de mídia passaram checksums; fingerprints dos **68 modelos de
negócio nos dois tenants** coincidiram; ADMIN e responsável acessaram conteúdo e mídia privados no
destino. Provas `restored/restore-proof.json` e `restored/business-proof.json` mantêm
`reopening_authorized=false`: não substituem reconciliação nem SLA contínuo.

`browser-proof.json` registra login/navegação sem JavaScript por perfil, recuperação pelo SMTP
capturado, privacidade de solicitação e isolamento. Ativação já consumida não é repetida; nova
execução distingue ativação histórica de ativação executada na própria rodada. `exports/` contém
pacotes privados dos dois tenants. `alert-received.json` registra recebimento **local automatizado**
com referência opaca, não atendimento humano. `suspension-proof.json` registra bloqueio de escola
e convite pendente preservando a outra escola; a comparação é reativada ao terminar.

Para parar apenas os servidores do ensaio, enviar SIGTERM aos PIDs em `server.pid` e
`restored/server.pid`. PostgreSQL 55439 e Redis 56379 são instâncias isoladas preparadas pelo
operador deste exercício e não devem ser confundidas com serviços existentes. Os arquivos
privados de `/tmp` são evidência temporária; transferi-los para cofre autorizado antes de expirar.

### Gates ainda externos

Docker/Swarm e imagem final, TLS público, RabbitMQ/worker/Beat reais, Resend verificado e SMTP
real, cópia externa criptografada/retida, agendamento de backup consistente, escalonamento humano,
titulares/substitutos reais, treinamento com cliente e quatro semanas de uso não foram simulados
como concluídos. Ruff/Black/checkers e testes dirigidos acompanham a entrega; suíte global,
cobertura e integração final são registrados separadamente pelo agente principal. Ainda não há
ADR de entrada real; a política de migrations iniciais permanece válida só para pré-produção.

## Consolidação final — 25/10/2026

O escopo de produto foi implementado e homologado com dados fictícios. Não há achados abertos
nas revisões independentes de produto e de segurança/operação. Isso não libera dados reais:
os gates externos acima continuam obrigatórios.

| Verificação | Resultado final |
|---|---|
| Suíte geral SQLite, com migrations reais | 1.607 aprovados; 394,71 segundos |
| Cobertura global | 86,75% (mínimo 85%) |
| Grupo crítico do CI, incluindo atendimento | 90,25% (mínimo 90%) |
| PostgreSQL 18.4 e Redis isolados | 59 aprovados; 1.093,98 segundos |
| Chromium, incluindo jornadas com/sem JavaScript | 45 aprovados; 260,52 segundos |
| Ruff, Black e contratos de imports/services/UI | Aprovados |
| Grafo pré-produção e ausência de drift de models | 31 migrations permitidas; sem alterações pendentes |
| `check --deploy --fail-level WARNING` | Sem avisos/erros |
| `collectstatic` em diretório temporário | Manifesto e `css/school-manager.72c0817ed0e8.css` conferidos |
| Gitleaks, histórico e arquivos atuais | Sem segredos detectados |
| Trivy, arquivos atuais | Sem HIGH/CRITICAL corrigíveis; sem segredos/falhas de configuração detectados |
| Locks Python e `pip check` | Sem vulnerabilidades conhecidas/incompatibilidades na validação deste lote |

A primeira rodada geral terminou com 1.596 aprovações e nove falhas em fixtures/expectativas
anteriores: docentes sem perfil persistido e vínculo de turma em audiência global. Os testes
foram atualizados para o contrato vigente, preservando as assertivas; 141 regressões dirigidas
passaram antes da repetição integral verde. O primeiro recorte crítico mediu 89,83%. Duas jornadas
HTTP reais acrescentaram cobertura de reenvio/consumo de convite, senha fraca e duplicidade de
conta inativa sem efeitos colaterais. Nenhum limite de cobertura foi reduzido, teste desativado
ou service substituído por mock para obter aprovação. Um literal de senha exclusivamente de
teste foi substituído por geração aleatória após sinalização do scanner.

Logs finais: `/tmp/schools-pilot-final-sqlite-verified.log`,
`/tmp/schools-pilot-final-critical-coverage.log`, `/tmp/schools-pilot-final-postgres.log`,
`/tmp/schools-pilot-final-ui.log`, `/tmp/schools-pilot-final-production.log`,
`/tmp/schools-pilot-final-gitleaks.json` e `/tmp/schools-pilot-final-trivy.json`.
Essas evidências são temporárias; os comandos canônicos permanecem no CI, Makefile e runbook.
O Trivy local examinou dependências/segredos e Dockerfile; não comprova compose/Traefik,
build/scan da imagem final, Linux/Swarm, TLS, duas réplicas ou provedor externo.

### Churn e remoção dos caminhos substituídos

| Categoria | Arquivos alterados/adicionados/removidos |
|---|---:|
| Produto e infraestrutura | 193 |
| Testes e configuração de testes | 64 |
| Migrations | 30 |
| Documentação, ADRs e modelos de importação | 17 |

Foram removidos `students/tasks.py`, `guardians/tasks.py`, `enrollments/tasks.py` e seus testes
exclusivos, além dos testes das tasks antigas de comunicados (`test_calendar_on_commit.py` e
`test_celery_tasks.py`). Convites/comunicados/lembretes usam a outbox canônica; a carga parcial por
linha foi substituída pelo lote assistido. Foram retirados a audiência infantil `STUDENTS`, os
workers antigos de e-mail da Agenda e o placeholder Basic Auth de métricas. Os fallbacks atuais
sem JavaScript, de cache/broker e de gateway foram preservados. O runbook documenta os canais
fictícios, as dependências operacionais e as jornadas de cada perfil.

### Validação dirigida do fechamento

- 77 regressões finais aprovadas; mais 11 de convite familiar, incluindo correção de identidade.
- PostgreSQL real: 4 cenários de exportação isolada/financeiro histórico, bootstrap e reenvio.
- Lote operacional anterior: 263 testes aprovados; estes números são rodadas distintas e não
  devem ser somados como cobertura única. Log final em `/tmp/pilot-stage4b-closed-regressions.log`.
- Ruff, Black (596 arquivos), contratos de services/import/UI e pré-produção (31 migrations)
  aprovados. Grafo aplicado ao banco fictício novo, sem migrations evolutivas nesta etapa.
- Dependências: auditorias alinhadas com zero avisos (73 pacotes produção, 133 desenvolvimento)
  na etapa 4A. A integração repete gates globais e scanners quando necessário.
