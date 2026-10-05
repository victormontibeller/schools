# Revisão de segurança, integridade e performance

Revisão iniciada em 16/09/2026 e concluída em 17/09/2026. Base revisada: `ba0ea64`. Repositório limpo no início da revisão.

## Decisão recomendada

Priorizar uma entrega de estabilização antes de ampliar as funcionalidades afetadas. Não liberar uso com dados reais antes de corrigir as falhas de autorização, os três problemas de integridade financeira e as falhas de implantação identificadas. Trabalho independente de produto pode continuar, mas os gates de segurança e produção permanecem pendentes.

P1 significa alta prioridade, com correção antes do uso real do fluxo afetado. P2 significa correção planejada na próxima rodada; os itens de performance dependem do volume, sem medição de latência em produção. Não foi demonstrado incidente em produção nem comprometimento entre escolas.

## Achados prioritários

### S1 — P1: Professor acessa ficha de aluno fora de seu vínculo

- Evidência: `core/middleware.py:285`, `students/views.py:145` e `students/views.py:164`.
- O middleware confere `student_id`, mas as rotas da ficha e do componente de responsáveis usam `pk`. A consulta posterior não reaplica a autorização por objeto.
- Reprodução em SQLite exclusivamente em memória: `teacher_can_access_student=False`; GET da ficha respondeu 200 e incluiu o nome do aluno; GET do componente de responsáveis também respondeu 200.
- Impacto: exposição de dados de aluno e família a professor da mesma escola sem vínculo autorizado. Não se trata de reprodução de acesso entre tenants.
- Correção: aplicar o escopo canônico em todas as rotas e selectors de detalhe, incluindo fragmentos HTMX; testar URL conhecida com aluno sem vínculo.

### S2 — P1: Credenciais de ativação e recuperação aparecem em access logs

- Evidência: `Dockerfile:46`, `accounts/urls.py:16`, `accounts/urls.py:56`, `core/middleware.py:79`.
- Gunicorn registra o caminho da requisição e o Referer. Convites de professor e recuperação de senha transportam tokens no caminho; remover somente a query string não os protege. Para páginas que mantêm tokens na query, o Referer de requisições da mesma origem também precisa ser tratado.
- Impacto: quem acessa os logs pode receber credenciais ainda válidas para ativar conta ou definir senha.
- Correção: redigir caminhos sensíveis e Referer na configuração efetiva de logs; usar `no-referrer` nas páginas com tokens; verificar saída real de Gunicorn e proxy.
- Validação: leitura da configuração e das rotas. Nenhum token real foi coletado e nenhum log de produção foi consultado.

### I1 — P1: Materialização após aditivo duplica parcelas anteriores

- Evidência: `financeiro/services/contracts.py:202` e `:260`; entrada HTTP em `financeiro/contract_views.py:201`.
- A deduplicação considera somente a revisão atual do contrato. O aditivo mantém as competências anteriores na revisão antiga, que a materialização não reconhece.
- Reprodução: contrato com 12 parcelas e aditivo em julho; nova materialização cria seis parcelas adicionais, passando de 12 para 18 cobranças ativas.
- Correção: resolver a revisão vigente de cada competência e manter idempotência também entre revisões; proteger parcelas anteriores, quitadas e canceladas. Cobrir materialização individual e por turma.

### I2 — P1: Estorno após renegociação não recompõe o saldo exigível

- Evidência: `financeiro/services/payments.py:253`; cancelamento da original em `financeiro/services/billings.py:115`.
- O estorno reduz o valor pago da cobrança original já cancelada pela renegociação, sem ajustar suas substitutas.
- Reprodução: principal R$100, pagamento R$40, renegociação de R$60, estorno do pagamento; a cobrança ativa permanece em R$60. O valor estornado fica na original cancelada e não volta ao saldo exigível. No ensaio, a original cancelada ficou com R$102, incluindo multa de R$2.
- Correção: tratar a cadeia de renegociação atomicamente ou bloquear explicitamente esse estorno até existir uma regra segura. Validar também estornos parciais e concorrência no PostgreSQL.

### I3 — P1: Aditivo futuro altera encargos de parcelas antigas

- Evidência: `financeiro/services/billings.py:177` e `:194`; alteração imediata dos termos em `financeiro/services/amendments.py:80`.
- Multa e juros são calculados pelas taxas atuais do contrato, apesar de a cobrança pertencer a uma revisão anterior.
- Reprodução: parcela de janeiro de R$100 com multa de 2%; aditivo futuro de julho muda para 10%; apuração em junho cobra R$10, quando deveria preservar R$2.
- Correção: calcular encargos com os termos da revisão que originou cada título, preservando a vigência das alterações.

### O1 — P1 antes de implantação: Healthcheck é incompatível com a stack

- Evidência: `Dockerfile:48`, `docker-stack.yml:53`, `docker-stack.yml:91` e `docker-stack.yml:105`.
- A sonda consulta `http://127.0.0.1:8000/health/`, mas o perfil de produção permite apenas os domínios configurados. O middleware de tenant precede a view de saúde.
- Reprodução isolada usando as configurações de produção e o middleware instalado: a sonda com Host `127.0.0.1:8000` retorna 404, antes de consultar o banco.
- Worker e Beat usam a mesma imagem e herdam a mesma sonda HTTP, embora não iniciem servidor na porta 8000.
- Consequência inferida da configuração: tarefas saudáveis podem ser marcadas como defeituosas e substituídas pelo Swarm. Esse comportamento do orquestrador está documentado em [Docker — How services work](https://docs.docker.com/engine/swarm/how-swarm-mode-works/services/). Não houve execução de Swarm nesta revisão.
- Correção: sondas próprias para web, worker e agendador; considerar host, HTTPS, tenancy e dependências de cada processo.

### O2 — P1 antes de implantação: Não há entrega de arquivos estáticos na stack

- Evidência: `Dockerfile:39` e `:46`, `core/urls.py:68`, `docker/nginx/media.conf:5`, `docker-stack.yml:118`.
- O build executa `collectstatic`, mas Gunicorn atende apenas a aplicação Django. Não há WhiteNoise, rota Django de estáticos em produção, nem configuração de Nginx/CDN que sirva `/static/`; o Nginx versionado atende somente mídia pública.
- Consequência: na stack entregue pelo repositório, CSS e JavaScript não possuem servidor de entrega. A resolução isolada de `/static/css/school-manager.css` com configuração de produção resultou em 404. Gerar o manifesto não valida o acesso HTTP aos arquivos.
- Correção: configurar entrega explícita de `STATIC_ROOT`, mantendo hashes e cache, e testar os assets pelo endereço externo da stack.
- Referência: [Django — Deploying static files](https://docs.djangoproject.com/en/5.2/howto/static-files/deployment/). Uma infraestrutura externa não versionada poderia suprir a lacuna, mas não foi informada nem verificada.

## Dependências

O comando `pip-audit -r requirements.lock --no-deps --disable-pip --progress-spinner off --timeout 15` consultou a base pública com sucesso e encontrou 12 avisos em três pacotes. A primeira tentativa falhou por DNS do sandbox; a repetição com acesso de rede autorizado terminou com código 1 devido aos achados.

| Pacote | Versão fixada | Avisos | Versão mínima indicada para os avisos encontrados |
| --- | --- | ---: | --- |
| Django | 5.2.16 | 1 | 5.2.17 |
| pypdf | 6.14.2 | 6 | 6.16.1 |
| sqlparse | 0.5.5 | 5 | 0.6.0 |

Identificadores retornados: Django `PYSEC-2026-3717`; pypdf `PYSEC-2026-3655`, `3656`, `3912`, `3910`, `3911`, `3913`; sqlparse `PYSEC-2026-3698`, `3697`, `3699`, `3696`, `3923` (todos com prefixo `PYSEC-2026-`).

Esses avisos não representam 12 explorações comprovadas no produto. A falha de Django refere-se ao GeoDjango, cujo uso não foi encontrado; algumas falhas do pypdf dependem de extração de texto ou leitura de outlines, também não identificadas no runtime da aplicação. Entretanto, o projeto processa PDFs enviados por usuários com `PdfReader` em `base/upload_validators.py:52`, e o gate de dependências já falha. Atualizar versões e regenerar os dois locks com hashes antes de liberar, seguido dos testes de regressão.

Fontes primárias: [Django 5.2.17](https://docs.djangoproject.com/en/5.2/releases/5.2.17/), [pypdf — processamento ineficiente de entradas](https://github.com/py-pdf/pypdf/security/advisories/GHSA-fc8x-2rww-xw9m), [pypdf — consumo de recursos em outlines](https://github.com/py-pdf/pypdf/security/advisories/GHSA-23w6-3w8w-8484).

## Próxima rodada: segurança e comportamento funcional

### S3 — P2: Escola desativada continua resolvendo requisições

`tenancy/services.py:112` altera `School.is_active`, preservando o domínio. O middleware nativo registrado em `core/settings.py:122` consulta o domínio e o tenant sem filtrar a atividade da escola; `core/middleware.py:48` apenas propaga contexto. Não foi encontrado bloqueio equivalente na autenticação ou nas permissões. Revalidar a atividade do tenant antes das views e testar sessão existente e novo login em PostgreSQL. Achado por inspeção; não houve reprodução com schemas reais.

### S4 — P2: Grade antiga continua concedendo visibilidade na lista de alunos

`students/selectors.py:45` e `:67` autorizam professor por joins de grade que não filtram atividade, exclusão lógica ou vigência. O manager do modelo relacionado não impõe esses filtros automaticamente ao join. O helper canônico em `core/access_selectors.py:98` já considera esses requisitos. Reutilizar esse escopo e testar horários desativados, excluídos, expirados e futuros.

### I4 — P2: Renegociação de cobrança avulsa gera erro 500

`financeiro/services/billings.py:121` define `number=None` quando não há contrato; `:128` executa `number + index`. Reprodução com o serviço real resultou em `TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'`. Preservar a numeração nula das cobranças avulsas; confirmar rollback e resposta de validação apropriada.

## Performance e capacidade

### F1 — P2: Resumo de frequência executa consultas por aluno

`attendance/selectors.py:73` executa uma contagem total e até três contagens por status para cada matrícula. São até `1 + 4N` consultas: 121 para uma turma de 30 alunos com registros. `dashboard/selectors.py:147` repete esse resumo por turma. Substituir por agregação em lote e adicionar teste de orçamento de queries. A quantidade é derivada da estrutura do código; não é benchmark de latência.

### F2 — P2: Relatório de inadimplência sem paginação

`financeiro/report_selectors.py:85` agrega todo o histórico vencido e `:124` converte tudo em lista. `financeiro/report_views.py:52` usa o conjunto tanto no HTML quanto no CSV, que começa depois da materialização. Paginar o HTML e gerar exportações por chunks, streaming ou tarefa assíncrona. O risco de memória e timeout cresce com o número de grupos; não houve teste de carga.

### Melhorias posteriores

- `notifications/tasks.py:118`: notificação para todos os usuários carrega todos os UUIDs antes de dividir em lotes; usar iterator e buffers limitados, preservando auditoria.
- `dashboard/selectors.py:272`: mediana do tempo de publicação materializa o histórico de publicações. Definir janela coerente ou agregação apropriada no banco, sem introduzir SQL direto proibido pelo projeto.
- `docker-stack.yml:119`: imagem de mídia `nginx:1.27-alpine` não está fixada por digest, ao contrário da regra de supply chain do projeto.

## Validação

| Verificação | Resultado |
| --- | --- |
| `ruff check .` | Passou |
| `black --check .` | Passou; 494 arquivos sem alterações necessárias |
| Contratos de importação | Zero violações |
| Contratos de comandos de service | Zero violações |
| Contratos de UI | Passou |
| Contratos de migrations pré-produção | Passou; 28 migrations |
| `check --deploy --fail-level WARNING`, com configuração sintética de produção | Passou |
| Suíte SQLite, excluindo marcadores `tenant` e `ui` | 1.431 testes passaram; 58 desmarcados; 383,41 segundos |
| Cobertura geral | 89,01%; gate de 85% passou |
| Cobertura agregada dos fluxos críticos, com o mesmo filtro do CI | 91,02%; gate de 90% passou |
| Auditoria das dependências fixadas | Falhou: 12 avisos em três pacotes |
| Healthcheck com Host configurado na imagem | 404 reproduzido |
| Resolução de `/static/css/school-manager.css` em configuração de produção | 404 reproduzido |

A aprovação dos testes existentes não cobre as combinações que reproduziram os defeitos. A cobertura dos fluxos críticos acima é agregada conforme o CI, não uma garantia de 90% para cada arquivo ou cenário individual.

Reproduções adicionais: S1 e I1–I4 foram confirmados com dados sintéticos em SQLite exclusivamente em memória. O healthcheck web retornou 404 sob o Host configurado na sonda. As reproduções não usaram dados reais nem alteraram banco de desenvolvimento.

Limites: não foi executada a suíte PostgreSQL, concorrência real, teste de carga, browser, build de imagem, Swarm, Gitleaks ou Trivy. Docker e utilitários PostgreSQL não estavam disponíveis no PATH. O ambiente virtual local utiliza Python 3.14.5, enquanto o alvo de CI/Docker é 3.13. A revisão não certifica ausência de outras vulnerabilidades.

## Ordem sugerida de correção

1. Fechar escopo de alunos e exposição de tokens; cobrir regressões HTTP/HTMX e logs.
2. Corrigir invariantes financeiras com os quatro cenários reproduzidos e testes de concorrência PostgreSQL.
3. Atualizar dependências e locks; corrigir entrega de estáticos e sondas antes do staging.
4. Corrigir revogação de escola/grade e consultas de frequência; paginar relatórios.
5. Reexecutar os gates do projeto e smoke tests da stack com duas réplicas antes de decidir pela liberação.

Churn desta revisão: produto 0; testes permanentes 0; migrations 0; documentação 1 arquivo novo. Nenhum caminho legado removido e nenhuma correção aplicada ao produto.

## Implementação de estabilização — 17/09/2026

Os achados acima descrevem a base auditada; esta seção registra a correção no worktree, sem
reclassificar a auditoria original como validação de produção.

- S1/S4: escopo docente canônico aplicado a turma, matrícula, aluno, grade e consumidores de
  listagem; URLs `pk`, componentes e endereços genéricos revalidam o proprietário. Services de
  aluno/endereço repetem a proteção antes de escrita/auditoria. Picker global de responsáveis
  exige a capacidade de vínculo `guardians/edit`.
- S2/S3: escola inativa/excluída é recusada antes do schema/sessão; logs HTTP usam somente rota
  canônica/status/duração, sem path, query, Referer ou exceção bruta. O handler500 também foi
  corrigido. Spans HTTP próprios substituem a instrumentação Django automática; páginas de token
  recebem no-store. A política no-referrer global introduzida nesta etapa causou a regressão CSRF
  descrita no fechamento abaixo; ela foi posteriormente corrigida com autorização do usuário,
  conforme a finalização de Referer/CSRF registrada ao fim deste relatório.
- I1–I4: materialização unificada sob lock e deduplicação entre revisões; aditivos com vigência
  não decrescente, sem alterar renegociações; snapshots de taxas por cobrança; renegociação avulsa
  sem numeração; estorno recompõe componentes por ajuste ligado à alocação e reduz pagos da
  original sem reativá-la. Supressão por aditivo é identificada por FK e pode ser reexpandida;
  cancelamentos manuais não são recriados. Extratos não somam saldo cancelado como exigível.
- O1/O2: liveness exata preserva JSON canônico sem acessar banco; sonda Celery dirigida ao próprio
  worker carrega secrets pelo entrypoint; Beat grava agenda em /tmp e reinicia em falha. WhiteNoise
  publica somente estáticos com hash/compressão. Nginx foi fixado por digest do registry oficial.
- Dependências: Django5.2.17, pypdf6.16.1, sqlparse0.6.0 e WhiteNoise6.12.0; ambos os locks
  regenerados e instalados com hashes em ambiente temporário Python3.13.14.
- Performance: resumos de frequência multi-turmas em duas queries, paginação20/máximo100,
  CSV completo tenant-scoped em blocos500, notificações ALL em buffers500 e mediana obtida
  pelos valores centrais ordenados no ORM.

Evidências locais da implementação: 48 regressões iniciais passaram; uma rodada de378 testes
focados teve377 sucessos e uma falha de representação tuple/list no batch de notificações,
posteriormente corrigida e revalidada. Rodada final dos cenários de segurança, endereços,
financeiro e notificações:81 testes passaram. Testes incluem exportação real de spans pelo
entrypoint opentelemetry-instrument, logs formatados, GET do CSS coletado com hash e bloqueio
à mídia privada. Os testes PostgreSQL de concorrência e revogação real foram adicionados e
foram posteriormente executados na integração, conforme o fechamento abaixo.

Grafo inicial regenerado no perfil completo:30 migrations, sendo28 estruturais initial=True
e os dois seeds autorizados. Migrations check não detectou alterações; a consistência com
banco existente não foi verificada nessa execução, pois o sandbox negou conexão ao PostgreSQL.
Nenhum banco de desenvolvimento/demo foi resetado durante a implementação inicial. O reset
autorizado foi posteriormente executado e validado pela integração, conforme o fechamento abaixo.

O checkpoint inicial ainda não incluía suíte completa, PostgreSQL, Chromium e scans. Os resultados
e pendências atuais estão consolidados no fechamento abaixo; essa lista inicial não representa
o estado atual da integração.

Caminhos substituídos removidos: cálculo de encargos via contrato mutável; deduplicação exclusiva
por revisão atual; materialização paralela por turma; joins docentes sem validade; carregamento
integral de inadimplência/destinatários/tempos de publicação; access log com path/Referer; sonda
HTTP herdada por workers. URLs públicas foram preservadas, sem aliases de compatibilidade.

Verificações finais adicionais:44 testes HTTP/segurança/handler de exceção passaram e20 testes
financeiros passaram, incluindo vencimento HTTP futuro preservado e passado recusado. Ruff,
Black e os quatro checkers passaram; o check de migrations encerrou sem alterações detectadas.
Os testes PostgreSQL adicionados cobrem também disputa entre aditivo e confirmação de pagamento.

Churn da implementação antes da integração (sem contar a auditoria preexistente): produto41
arquivos (+691/-287); testes10 (+1071/-23); migrations28 (+324/-162); documentos canônicos7
(+73/-6), além desta seção acrescida ao relatório original. Números não incluem alterações
posteriores da integração nem representam cobertura de validação operacional.

### Complemento da integração: cursor, imagens e testes visuais

- O CSV deixou de executar consultas paginadas por OFFSET: agora mantém uma única consulta/cursor,
  lê blocos de 500 sob contexto explícito do tenant e fecha o cursor no mesmo contexto. A regressão
  de 501 grupos confirma que quitar um grupo já emitido não omite o último; a variante PostgreSQL
  confirma o pagamento em outra conexão.
- Compose utiliza o mesmo digest imutável do Nginx da stack. `reset_dev.sh` aceita `PYTHON_BIN`
  explícito, mantendo o padrão `.venv/bin/python`; não houve reset neste lote.
- O manifesto coletado revelou que `live_server` intercepta estáticos pelos finders antes do
  WhiteNoise. Os testes UI agora usam storage fonte explícito, sem alterar produção. A regressão
  de desenvolvimento declara DEBUG=True; os testes de produção continuam exigindo hash e HTTP200.
- CSV e estáticos: oito testes passaram em Python3.13.14. Ruff, Black, quatro checkers,
  `git diff --check` e sintaxe do script de reset passaram. PostgreSQL e suíte Chromium completa
  foram posteriormente executados; os resultados constam no fechamento abaixo.
- O novo smoke Chromium também identificou a data sugerida da recomposição em formato localizado,
  inválido para `input type=date`; o widget agora renderiza ISO, preservando a sugestão de hoje.


## Fechamento da integração — 17/09/2026

**Estado final:** as correções de Referer/CSRF e de cache 304 passaram nas suítes locais completas,
PostgreSQL e Chromium. Não há autorização pendente nem regressão funcional conhecida nos testes
executados. A validação operacional da imagem Linux e da stack permanece pendente, incluindo a
combinação OpenTelemetry/Gunicorn; não houve implantação em produção ou aprovação dessa stack.
Os checkpoints abaixo preservam a sequência de falhas encontradas, correções e resultados finais.

### Evidências executadas

| Verificação | Resultado da integração |
| --- | --- |
| Runtime | Python 3.13.14; ambiente temporário isolado, sem substituir a `.venv` original |
| PostgreSQL 18.4 isolado, rodada final | 38 passaram em 309,97 segundos, incluindo headers da escola inativa, isolamento/revogação, concorrência financeira e streaming de 501 grupos com pagamento em outra conexão |
| Chromium antes da correção de Referer | 27 passaram; 2 falharam no POST de estorno, com e sem JavaScript, por `Origin: null`/CSRF; regressão corrigida posteriormente |
| Chromium, rodada final | 33 passaram em 123,43 segundos; nenhum teste falhou |
| Suíte completa anterior | 1.492 passaram; cobertura geral 89,23%; cobertura crítica agregada 91,07% |
| Suíte completa após coleta de estáticos | 1.489 passaram, 4 falharam e 67 desmarcados; cobertura geral 89,24%; as quatro falhas eram expectativas de URLs sem hash, incompatíveis com o manifesto presente |
| Suíte intermediária, após correção das asserções | 1.493 passaram; 67 desmarcados; 224,65 segundos; cobertura geral 89,24% e crítica agregada 91,64%; gates de 85% e 90% aprovados |
| Suíte completa final, após Referer/limpeza | 1.503 passaram; 71 desmarcados; 264,08 segundos; cobertura geral 89,34% e crítica agregada 92,12%; gates de 85% e 90% aprovados |
| `pip-audit`, repetido após os locks finais | Zero vulnerabilidades reportadas |
| Gitleaks 8.30.1 | Zero achados no histórico de 38 commits; nova execução no worktree final também sem achados |
| Trivy 0.74, filesystem final | Zero achados de vulnerabilidade, segredo ou configuração incorreta HIGH/CRITICAL; não substitui scan da imagem |
| `check --deploy` | Passou |
| `collectstatic` e Gunicorn direto com dois workers, perfil produção | CSS com hash retornou 200 e 304 com o mesmo Cache-Control immutable; JavaScript coletado havia retornado 200 no smoke anterior |
| Headers no Gunicorn direto | Login 200/same-origin; convite inválido 200/strict-origin/no-store; URL desconhecida e mídia privada 404/strict-origin/no-store |
| `opentelemetry-instrument gunicorn` no macOS | Tentativa falhou no fork com erro Objective-C em `NSCharacterSet initialize`; proteção do SO preservada. Não comprovado estável nesse runtime |
| Logs reais e liveness | Marcador sintético ausente dos logs; `/health/` retornou HTTP 200 sem banco disponível |
| Docker CLI 29.8.1, `stack config` | Configuração efetiva validada; destino da sonda worker preserva `$HOSTNAME` corretamente |
| Reset dev/demo autorizado | Executado com `scripts/reset_dev.sh` e `PYTHON_BIN` apontando para Python 3.13; PostgreSQL local na porta 5432; schemas public e demo recriados e semeados |
| Consistência após reset | `makemigrations --check` e `migrate_schemas --check` passaram |
| Qualidade estrutural final | Ruff, Black (503 arquivos), quatro checkers, check deploy, stack config pelo CLI, checks de migrations e `git diff --check` passaram |

O diretório `staticfiles/`, produzido por `collectstatic`, está no `.gitignore`; seus mais de 600
artefatos gerados não fazem parte do produto versionado nem dos números de churn abaixo.

### Diagnóstico de Referer/CSRF e autorização

O browser confirmou que um POST nativo sob `Referrer-Policy: no-referrer` envia `Origin: null`.
O Django rejeita corretamente esse valor; a proteção CSRF não foi desativada nem contornada.
Esse comportamento está definido no [WHATWG Fetch, append a request Origin header](https://fetch.spec.whatwg.org/#append-a-request-origin-header).
A data sugerida do ajuste, antes localizada e inválida para `input type=date`, já foi corrigida
para ISO; paginação e entrega de estáticos funcionam no browser.

A proposta apresentada foi usar `same-origin` nas páginas comuns e `strict-origin` nas páginas com
tokens, mantendo `no-store` e preservando os cabeçalhos Django no proxy. Assim, um Referer de
página com token conteria somente a origem, nunca seu caminho ou query string, sem invalidar o
POST nativo. Isso altera o requisito literal de `no-referrer` em páginas com tokens; a alternativa
é manter essa política e adotar um fluxo de sessão com redirecionamento para URL sem token.
O usuário autorizou essa proposta explicitamente: “Pode sim. Removeu códigos obsoletos?”. A
finalização abaixo registra a implementação e sua validação; não se adotou redirecionamento novo.

A revisão automática de aprovação rejeitou a tentativa de alterar as políticas Django/Traefik,
por considerá-la uma redução de proteção sem autorização explícita. A tentativa foi interrompida;
nenhuma alteração de política foi aplicada até a autorização explícita posterior do usuário.
Após essa autorização, o ajuste foi implementado e validado. A evidência do diff mostra
que a base original usava `strict-origin-when-cross-origin` no Django e
`no-referrer-when-downgrade` no proxy; o `no-referrer` global foi introduzido nesta estabilização.
Esse contexto fundamentou a proposta; a autorização posterior está registrada acima.

### Validações ainda pendentes

- Executar build da imagem, Trivy sobre a imagem e smoke da stack com duas réplicas, worker e
  Beat. O Docker CLI está disponível, mas não há daemon Docker neste ambiente; configurações
  renderizadas e Gunicorn local não comprovam estabilidade desses processos na stack.
- Validar a combinação `opentelemetry-instrument gunicorn` dentro da imagem Linux. No macOS,
  a tentativa encontrou crash Objective-C relacionado a `NSCharacterSet initialize` após fork.
  A proteção do sistema operacional não foi desabilitada; o processo foi encerrado e o smoke HTTP
  foi executado com Gunicorn direto. O teste isolado do entrypoint OpenTelemetry permanece
  aprovado, mas não comprova a estabilidade da combinação com workers Gunicorn.

### Churn acumulado revisável

Contagem do worktree em relação à base auditada, incluindo arquivos novos e excluindo artefatos
gerados. A auditoria original preexistente foi preservada e excluída da contagem de linhas novas;
contabilizam-se somente os complementos deste relatório.

| Categoria | Arquivos | Linhas adicionadas | Linhas removidas |
| --- | ---: | ---: | ---: |
| Produto e configuração | 43 | 713 | 351 |
| Testes e fixtures | 17 | 1441 | 30 |
| Migrations iniciais | 28 | 324 | 162 |
| Documentação | 8 | 372 | 6 |

Não houve migrations adicionais neste fechamento documental. Além dos caminhos listados na
implementação, foi removida a leitura do CSV por consultas OFFSET entre blocos. Não há aliases
de compatibilidade introduzidos; a política de Referer foi corrigida após autorização explícita.


### Ajuste dos testes ao manifesto coletado

A rodada completa anterior à correção das asserções terminou com quatro falhas nos testes de
grade, chamada, Agenda e landing. Os templates emitiam corretamente URLs
com hash, mas as asserções exigiam o nome sem hash. Os quatro testes agora comparam a URL
resolvida pelo helper `static` do storage atual; a landing continua exigindo todos os assets
locais e verifica sua existência no storage coletado ou nos finders. Nenhuma configuração global
de DEBUG/storage, código de produto ou política de Referer foi alterada neste ajuste.

Validação focada com `staticfiles/staticfiles.json` presente: os quatro testes passaram em Python
3.13.14, em 18,79 segundos (`/tmp/schools-manifest-assertions.log`). Ruff, Black e
`git diff --check` passaram.

A repetição completa final, após esse ajuste, passou: 1.493 testes, 67 desmarcados, 224,65 segundos.
Cobertura geral de 89,24% e crítica agregada de 91,64%; ambos os gates (85%/90%) passaram.
Evidências finais: `/tmp/schools-integration-full-final.log` e
`/tmp/schools-integration-critical-final.log`. A suíte completa não está mais pendente.
Nesse checkpoint documental o aceite permanecia bloqueado por Referer/CSRF e pelas verificações
de contêineres que exigem daemon Docker. A política foi posteriormente autorizada e corrigida;
o resultado está registrado a seguir.


## Finalização autorizada de Referer/CSRF e remoção de resíduos

A autorização explícita do usuário permitiu aplicar `same-origin` nas páginas comuns e
`strict-origin` nas páginas de convite, recuperação e verificação DEMO. Páginas sensíveis mantêm
`no-store`, as URLs existentes e a proteção CSRF integral. Foi removido o override `referrerPolicy`
do Traefik para preservar os cabeçalhos definidos pelo Django.

O wrapper de cabeçalhos agora precede a resolução de tenant e o redirecionamento HTTPS. Se uma
resposta antecipada ainda não tem `resolver_match`, ele identifica apenas o nome da rota, sem
consultar banco ou executar a view. Erros/redirecionamentos sem rota conhecida recebem
`strict-origin`/`no-store`; arquivos estáticos entregues com sucesso preservam cache immutable.
A regressão PostgreSQL de escola inativa também verifica os headers de token e URL desconhecida.

**Bloqueio CSRF resolvido nos testes reais:** seis casos Chromium passaram em 32,63 segundos:
convites de professor e responsável, recuperação de senha e DEMO sem JavaScript, mais os dois
estornos com JavaScript ligado/desligado. Senhas, ativação e ajuste financeiro persistiram.
Os POSTs de páginas sensíveis enviaram `Origin` correto e Referer somente com a origem; nenhum
token apareceu nos Referers capturados, inclusive após redirecionamento. DEMO preserva seu fluxo
canônico de confirmação GET seguido de login POST, pois não possui formulário POST com token.
Referências normais entre assets locais e da página final sem token permanecem permitidas.

Validação deste lote: 113 testes focados passaram; o teste do entrypoint OpenTelemetry real foi
reexecutado e passou após desinstalar a instrumentação Django do runtime temporário. O teste
negativo confirma que POST sem CSRF continua recebendo 403. Os dois locks foram regenerados com
hashes, sem atualização ampla; `pip check` não encontrou dependências quebradas. Evidências:
`/tmp/schools-referrer-focused.log`, `/tmp/schools-referrer-ui.log` e
`/tmp/schools-otel-without-django-instrumentor.log`.

Foram acrescentados 13 casos de regressão neste lote: oito de headers/CSRF, um de header DEMO e
quatro Chromium de tokens. Também foram ampliadas a regressão PostgreSQL existente e a verificação
dos dois estornos que antes falhavam. Os gates completos foram posteriormente reexecutados e
passaram, conforme a tabela final e os logs abaixo.

Remoções delimitadas aos arquivos e caminhos afetados:

- Helpers financeiros sem consumidores `_normalize_month` e `_installment_for_month`.
- Duas definições concorrentes de `_add_months` em contratos/cobranças, substituídas por uma única
  implementação em `FinanceRulesMixin`, usada também pelos aditivos; o comportamento foi preservado.
- Requisito direto `opentelemetry-instrumentation-django` e transitivas órfãs
  `opentelemetry-instrumentation-wsgi` e `opentelemetry-util-http` dos dois locks. Spans HTTP próprios
  e o entrypoint `opentelemetry-instrument` continuam funcionais; a configuração impeditiva de
  auto-instrumentação sensível permanece como controle de segurança.
- Política global `no-referrer`, override de Referer no proxy e asserção antiga incompatível com
  POST nativo; substituídos pela política autorizada e testes de browser.

Não foram removidos fallbacks canônicos de acessibilidade, HTMX, cache ou broker. Nenhuma rota,
alias de compatibilidade ou migration evolutiva foi introduzida nesta finalização. A ausência de
daemon Docker ainda impede build/scan da imagem e validação da stack com duas réplicas,
worker e Beat; isso segue pendente e não foi convertido em aprovação operacional.

Ruff, Black (503 arquivos), quatro checkers e `git diff --check` passaram neste último lote.


A revisão final de cache encontrou que uma resposta WhiteNoise HTTP 304, sem rota Django,
recebia `no-store` indevidamente. O fallback desconhecido agora exclui somente 304; rotas de
token identificadas mantêm `strict-origin`/`no-store` em qualquer status. A regressão envolve
os dois middlewares, consulta o CSS com hash e revalida seu ETag: HTTP 200 e 304 preservam o
mesmo Cache-Control immutable. Dez testes focados passaram em 34,82 segundos, além de Ruff,
Black e diff check (`/tmp/schools-static-304.log`).


## Evidências consolidadas após a última correção

- Suíte completa final: 1.503 testes aprovados e 71 desmarcados, em 264,08 segundos; cobertura
  geral de 89,34% e crítica agregada de 92,12%, ambas acima dos gates. Logs:
  `/tmp/schools-referrer-full-final.log` e `/tmp/schools-referrer-critical.log`.
- PostgreSQL: 38 testes aprovados em 309,97 segundos, incluindo headers em tenant inativo.
  Evidência: `/tmp/schools-referrer-tenant.log`.
- Chromium: 33 testes aprovados em 123,43 segundos. Evidência:
  `/tmp/schools-referrer-ui-integration.log`.
- Auditorias repetidas após os locks finais: pip-audit sem vulnerabilidades, Gitleaks sem achados
  no worktree e Trivy filesystem sem achados HIGH/CRITICAL de vulnerabilidades, secrets ou
  configuração. Checks estruturais e de configuração também passaram.
- O smoke Gunicorn direto, com dois workers e perfil de produção, confirmou hash/cache 200/304,
  headers diferenciados, bloqueio de mídia privada e ausência do marcador sintético nos logs.
  A tentativa instrumentada no macOS falhou pelo problema de fork Objective-C descrito acima;
  não se desabilitou a proteção do SO e não se atribui esse smoke direto ao entrypoint instrumentado.
- Servidores temporários foram encerrados. Dev/demo permaneceram intactos após o reset autorizado
  anterior; nenhuma implantação de produção foi executada.

A limpeza de código obsoleto foi executada: helpers mortos e duplicação financeira, instrumentação
Django/WSGI substituída e sua dependência órfã, consultas OFFSET do CSV, configuração global de
Referer substituída e sonda HTTP compartilhada deixaram o caminho ativo. As remoções específicas
estão listadas neste relatório; fallbacks canônicos de acessibilidade e resiliência foram preservados.
Restam as verificações operacionais que exigem daemon Docker e a imagem Linux, explicitadas acima.
