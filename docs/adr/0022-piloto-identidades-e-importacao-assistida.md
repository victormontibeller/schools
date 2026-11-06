# ADR-0022 — Identidades e importação assistida do piloto

- Status: aceito para implementação pré-produção
- Data: 2026-10-25
- Escopo: implantação, equipe e correções de integridade

## Contexto

O piloto de Educação Infantil precisa começar sem contas infantis, sem senhas compartilhadas e
sem dependência de `seed_dev`. A primeira homologação usará exclusivamente escola e pessoas
fictícias. Ainda não há autorização de entrada de dados reais em produção.

## Decisão

O operador público provisiona o primeiro administrador após configurar domínio e remetente
verificado. A operação mantém o ator público na auditoria pública. No schema escolar o executor
interno não carrega a FK desse operador, e os eventos continuam correlacionados pelo contexto
operacional. O operador não assume a sessão do administrador. O bootstrap é único; reenvio só é
permitido enquanto a mesma identidade continuar pendente e não houver equipe adicional.

Contas administrativas são criadas inativas e recebem convite válido por sete dias. A emissão
rotaciona um nonce persistido; consumo é único, protegido por lock. Alterar o e-mail invalida a
emissão anterior. O worker revalida nonce, prazo, schema, identidade e escola antes da entrega.
Convites não dependem da preferência de alertas. Administradores pendentes não podem ser
ativados pelo formulário de edição. Desativação e troca de papel preservam o último administrador
ativo com senha utilizável; um lock estável no papel ADMIN serializa essas alterações. Perfis de
professor e responsável não podem ser convertidos para outro papel pela edição genérica.

Importações passam a usar três CSVs vinculados por identificadores de origem explícitos. A carga
é integral e transacional: conflito em qualquer linha impede toda a carga. Um identificador de
lote e hash dos arquivos tornam a reaplicação idempotente; reutilizar o identificador com outro
conteúdo é recusado. Conflitos com cadastros existentes exigem reconciliação; não há atualização
silenciosa de dados preexistentes. O manifesto registra somente objetos criados, IDs e versões.
A reversão exige versões intactas, ausência de contas e ausência de dependências externas ao
lote; aplica exclusão lógica integral e auditada. Não há restauração automática de lote desfeito.

A carga não cria matrículas, acessos ou convites. Matrículas seguem exclusivamente o workflow
canônico de solicitações. Guarda e retirada exigem 0/1 explícitos no arquivo de vínculos; o lote
não presume consentimento para alertas. Após conferência pela escola, os convites são emitidos
pelo fluxo próprio de responsáveis.

A primeira baixa registrada após apuração segue a decisão consolidada na ADR-0018: quando não
há alocações confirmadas ou estornadas nem componentes pagos, os encargos são reapurados pela
data efetiva na mesma transação da confirmação. Pagamento pontual não recebe juros indevidos.
Retroatividade que reescreveria baixas ou recibos históricos continua recusada. Recebimentos
confirmados permanecem na competência de origem após renegociação, respeitando o escopo de
alunos, sem ressuscitar principal cancelado.
A chamada em lote exige a versão que o usuário visualizou para cada aluno e reverte integralmente
se qualquer entrada tiver sido alterada.

## Consequências e fronteiras

A antiga task `students.import_students_csv` (commits por linha, sem lote) foi removida com seus
testes exclusivos. O comando `import_school_data` é o ponto operacional canônico.
A desativação pelo Django Admin foi fechada para identidades, evitando contorno dos services.

Esta ADR **não encerra** a política da ADR-0019. Novos campos e o modelo de lote foram incorporados
à regeneração intermediária do grafo inicial na etapa 2. A primeira rodada SQLite usou
`--nomigrations`; os testes seguintes usam o grafo real. O grafo foi novamente regenerado com os
models do atendimento e consolidado em 31 migrations iniciais/seeds permitidos.
Antes da primeira carga real será necessária uma ADR de entrada em produção, com o grafo final,
procedimento de backup/restauração e estratégia de evolução definidos. Dados reais, ativação de
cliente, recuperação em produção e quatro semanas de acompanhamento continuam pendentes.
