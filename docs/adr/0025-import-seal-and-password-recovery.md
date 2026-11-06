# ADR-0025 — Selo da importação e recuperação auditada de acesso

- Status: aceito para implementação pré-produção
- Data: 2026-10-25

## Importação e concorrência

Aluno, responsável e vínculo recebem `origin_import_batch` imutável e não editável. Somente o
argumento interno da importação atribui a proveniência; CSVs e formulários não aceitam esse campo.
O lote nasce no início da transação. O manifesto registra exclusivamente objetos criados.

Estados: `IMPORTED` (reversível), `SEALED` (uso operacional) e `REVERTED` (desfeito). O contrato
`students.contracts.ImportUsageService.seal_for_use` consulta inclusive objetos desativados,
trava os lotes em ordem de UUID antes das raízes e revalida o estado depois da espera. Uso de uma
instância antiga nunca restaura nem utiliza um cadastro revertido. A criação da dependência e o
selo pertencem à mesma transação: uma falha posterior desfaz ambos. Objetos sem proveniência e
lotes já selados não adquirem lock de lote nem lock administrativo global.

Reversão trava o lote antes das raízes, exige `IMPORTED`, verifica versões e todas as referências
externas, e desativa o manifesto integralmente. Não há exclusão física. O lock ADMIN deixou de
ser uma falsa barreira da importação; invariantes administrativas de outros domínios continuam
usando seu próprio lock.

`import_school_data --restore <UUID>` recupera explicitamente um lote `REVERTED`: exige capacidades
de edição dos dois domínios, verifica o manifesto pós-reversão, ausência de dependências e
proveniência, restaura os mesmos IDs e marca `SEALED`. Depois a equipe usa a edição normal para
corrigir dados. Não duplica CPF/e-mail, não reenvia convites e não reabre a reversão. CSV nunca
reativa registros silenciosamente. Falha de auditoria reverte toda a recuperação. A unicidade condicional de CPF ativo no banco
fecha a corrida entre recuperar e criar um responsável substituto; colisões viram erro de negócio
sem expor CPF ou detalhes do banco. Endereços de e-mail compartilhados não ganham constraint nova.

### Inventário dos produtores de referências

| Raiz/referência | Barreira canônica |
|---|---|
| Student/Guardian/StudentGuardian: edição, desativação, vínculo | Selo antes da escrita; vínculo considera ambos os lotes |
| Conta familiar, convite e ativação | Selo do responsável antes do lock de perfil/conta |
| EnrollmentApplication, Enrollment, rematrícula/transferência | Selo antes do lock Student; rematrícula sela o conjunto em ordem |
| StudentDocument e requisitos documentais | Application já selou a raiz na criação; documentos dependem dela |
| StudentFinancialContract e BillingEntry avulsa | Selo antes da criação; parcelas/baixas dependem do contrato/título |
| CollectionReminder | Título já selado; responsável com conta ativada passou pelo convite |
| AttendanceJustification e AttendanceEntry | Selo antes da justificativa/materialização; chamada usa matrículas ativas |
| ActivitySubmission e ActivityGroupMember | Criação da atividade sela alunos; sincronização/grupos dependem de Enrollment |
| DailyDiary e DiaryPublishedEntry | Selo antes do sheet; publicação depende do diário existente |
| DiaryViewReceipt | Perfil familiar convidado e entradas já materializadas |
| ServiceRequest | Selo antes do lock administrativo e da criação do protocolo |
| StudentAddress e GuardianAddress | Selo antes de criar endereço/vínculo |
| Announcement e AnnouncementRecipient | Selo do contexto individual e dos responsáveis resolvidos antes dos FKs |

Comunicados travam seu agregado de autoria antes do selo; nenhum caminho de reversão trava esse
agregado. O selo sempre precede locks/escritas das raízes importadas e de seus novos FKs. Rotinas
que materializam filhos de matrícula/contrato já existente não repetem locks de lotes selados.

## Recuperação de senha

Mantemos rotas, CSRF, validade, formulário, SMTP e formato dos tokens do Django. O gerador inclui
o schema na assinatura: um token emitido em uma escola não é aceito em outra. A confirmação
chama `PasswordRecoveryService`, que verifica escola, conta ativa, senha utilizável, token e
validação de senha sob lock da conta. O próprio comando faz essas verificações, sem depender da
view. Senha e hash são redigidos na auditoria. O transporte SMTP captura falhas sem traceback/mensagem
externa, que poderiam conter destinatário e token. Falha de auditoria mantém senha/token anteriores.
A plataforma pública recupera somente contas de operador; não há impersonação de escola.

Limites HTTP compartilhados no Redis `authentication`, sem fallback permissivo:

- solicitação de reset: 10/IP/hora e 3/destinatário/hora, separados por escola;
- confirmação de reset/convite: 30/IP/15 minutos;
- reenvio autenticado de convite: 20/IP/hora e 3/destinatário/hora.

Cada chave usa HMAC-SHA256 de escola, finalidade e dimensão. E-mail, IP e token não são gravados
em chaves nem logs. Contadores usam ADD/INCR atômicos com expiração; tentativas recusadas contam.
Conta existente, inexistente e inativa recebem a mesma resposta. Excesso retorna 429 com
`Retry-After`; indisponibilidade do cache retorna 503/60 segundos sem enviar e-mail. Apenas o
proxy explicitamente confiável pode fornecer o IP encaminhado. Testes rápidos usam LocMem,
sem substituir a prova concorrente Redis do perfil de integração. Ativação e recuperação não
consultam a preferência por alertas escolares.

### Recuperação extraordinária

O administrador titular ou substituto abre ocorrência com protocolo no suporte designado.
Suporte confere identidade por contato institucional previamente registrado e confirma a
solicitação com o outro administrador quando disponível. Registra aprovador, evidência da
verificação, escola e referência da conta, sem senha/documento pessoal no log. Prioriza reenvio
ou recuperação normal. Se ambos perderam acesso, dois operadores autorizados conferem a
identidade da instituição antes de uma intervenção técnica auditada e de um ensaio de login pelo
próprio titular. O procedimento nunca entrega senha ao suporte, usa bootstrap novamente sobre
escola já inicializada ou autentica o operador como usuário escolar. Titulares reais, canal de
suporte e evidência operacional serão definidos antes da primeira carga real.

## Dependências e distribuição

Atualizações de segurança são seletivas nos arquivos de entrada e nos dois locks com hashes.
A imagem Python 3.13 usa digest oficial multiarch renovado. `pip` é removido do venv após instalar
o lock e do Python global da imagem final: o runtime não instala pacotes. Isso remove seus
vendorizados sem apagar bibliotecas da aplicação. Scan da base não substitui build/scan da
imagem final; a validação Docker permanece um gate quando não há daemon disponível.

Esta decisão não encerra a política pré-produção nem autoriza carga de dados reais.
