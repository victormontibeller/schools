# ADR-0020 — Workflow canônico de matrículas

## Contexto

O vínculo acadêmico podia ser criado diretamente pela ficha da turma e coexistia com uma
solicitação incompleta da Secretaria. A reserva de vagas era inferida, uploads não chegavam ao
service e rematrícula reutilizava a turma anterior sem decisão pedagógica explícita.

## Decisão

`enrollments` passa a ser a única fronteira de produto para criar, transferir ou cancelar
`classes.Enrollment`. A solicitação usa cinco tipos e nove estados, histórico append-only,
protocolo anual tenant-scoped e versão esperada em cada comando. Aprovação persiste a reserva;
capacidade indisponível leva à lista de espera sem promoção automática.

O vínculo final guarda `academic_year` e possui unicidade condicional por aluno/ano enquanto
ativo. A abertura materializa o snapshot dos requisitos documentais. Itens obrigatórios bloqueiam
somente a efetivação e podem ser dispensados exclusivamente por Administrador, com motivo.

Rematrícula recebe mapeamento aluno–turma confirmado em lote atômico. Lembretes passam pelo
`MessageTransport`, são publicados após commit com schema explícito e contêm texto externo
genérico, somente por e-mail e para destinatários com guarda/consentimento revalidados na entrega.
Retries e recuperação de claims abandonados preservam a identidade do `MessageLog`. A cada cinco
minutos, um dispatcher do Celery Beat agenda reconciliação isolada por tenant: lembretes ainda
`PENDING` e sem log são reenfileirados, logs pendentes são republicados com a mesma chave
idempotente e logs já enviados ou falhos encerram o lembrete sem uma nova chamada ao canal.

Rematrícula em lote usa a capacidade independente `reenrollment`: Visualizar prepara o lote e
Cadastrar confirma a escrita. Requisitos futuros usam `document_requirements`, com Visualizar,
Cadastrar, Editar e Desativar. Ambas são delegáveis somente a Secretaria e Coordenação;
Secretaria recebe rematrícula por padrão, enquanto requisitos documentais não possuem default.
A capacidade de configuração não delega a dispensa de um item materializado, que continua
exclusiva do Administrador.

## Consequências

- `classes` preserva o modelo de leitura e expõe somente uma porta interna para o workflow.
- Saem rotas, views, comandos e testes de matrícula direta, revisão separada e rematrícula antiga.
- O POST da rota de preparação de rematrícula sai; a confirmação possui endpoint próprio para que
  leitura e escrita sejam autorizadas por ações diferentes.
- A Central de Acessos passa a exibir Rematrícula em lote e Requisitos documentais como linhas
  independentes, sem alteração de schema nem sobrescrita de escolhas existentes no bootstrap.
- O grafo inicial de `classes` e `enrollments` é regenerado e dev/demo exigem reset integral.
- Família/público, WhatsApp e promoção automática da espera permanecem fora do escopo.
