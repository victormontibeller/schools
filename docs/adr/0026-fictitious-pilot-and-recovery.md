# ADR-0026 — Homologação fictícia, portabilidade e recuperação

- Estado: aceito em 25/10/2026 para pré-produção; não autoriza dados reais.
- Contexto: não há cliente nem credenciais operacionais. O piloto precisa de jornadas verificáveis,
  recuperação de arquivos e banco, portabilidade autorizada e comunicação recuperável.

## Decisão

`FICTITIOUS_MODE` exige DEBUG, ambiente não produtivo, PostgreSQL de nome `schools_pilot_*`
num host loopback, diretório privado em `/tmp`, mídia isolada, domínios `*.localhost` reservados,
schemas `piloto`/`piloto_comparacao` e destinatários `example.test`. A configuração é recusada
fora dessas condições. A UI identifica a ficção inclusive antes do login e desabilita a toolbar.
O transporte local grava arquivos 0600, com identidade estável; não verifica ficticiamente Resend,
não envia pela internet e não substitui RabbitMQ por Redis. O dreno explícito da outbox é exclusivo
deste modo. Recuperação usa seu canal SMTP separado, capturado localmente durante o exercício.

Todos os convites agora persistem uma intenção na outbox antes da fila. Emissão/nonce define
identidade e validade; o endereço, remetente e corpo ficam estáveis durante retentativas técnicas.
O vencimento externo é a data real da emissão, não sete dias após uma entrega atrasada. O token
fica em campo técnico redigido na auditoria, invisível no admin e no painel de entregas. Guarda,
perfil, escola e emissão vigentes são exigidos na emissão, no worker e na ativação. Reenvio não
resolve divergência de identidade silenciosamente: corrigir pelo comando autorizado de conta,
que atualiza atomicamente o contato vinculado, revoga o token e exige nova emissão.

Exportação usa allowlist explícita de dados de negócio e mídia, incluindo exclusão lógica,
revisões, ciência e financeiro histórico completo. Não inclui credenciais, sessões, tokens,
payloads de transporte ou configurações secretas. ADMIN do próprio tenant é a capacidade;
operador público não recebe impersonação. A execução não admite transação externa. Staging
privado é compensado sem depender de consultas ao banco; publicação recusa sobrescrita. A
auditoria registra **solicitação de exportação**, e a conclusão só é informada após o pacote ser
publicado. Namespaces, raiz resolvida e componentes sem symlink são obrigatórios para mídia.

Backup consistente deste procedimento requer quiescência declarada e verificada. Inclui dump
completo (public e todos os tenants) e toda mídia pública/privada, manifesto UTC e SHA-256.
Restauração só cria banco e pasta novos; nunca remove destino existente. Extração rejeita paths
externos, duplicados e links. Um restore bem-sucedido não autoriza reabertura: reconciliar o intervalo
perdido, principalmente guarda, contas, permissões e pagamentos, e reconstruir cache isolado.

## Consequências e limites

Um ensaio local demonstra mecanismo, ponto recuperado, duração e integridade naquela execução;
não comprova RPO contínuo de uma hora nem RTO produtivo de quatro horas. Agendamento, retenção,
criptografia, cópia externa, contatos humanos, Swarm, TLS, broker real e provedores continuam gates
externos. Antes de qualquer carga real, outro ADR encerra a política de migrations iniciais e
registra plano de preservação/compatibilidade. Esta homologação continua descartável e fictícia.
