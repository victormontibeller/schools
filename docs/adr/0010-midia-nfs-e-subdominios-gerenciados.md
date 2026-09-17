# ADR-0010 — Mídia NFS e subdomínios gerenciados

## Status

Aceito em 2026-07-13. Infraestrutura implementada; rollout depende de staging.

## Contexto

Réplicas Swarm não podem depender de disco local para uploads. A resolução de tenants precisa de
uma base de hosts previsível e de TLS wildcard sem distribuir mídia privada pelo proxy.

## Decisão

- Usar `media/` local no desenvolvimento e o mesmo NFSv4 em `/app/media` no web e nos workers.
- Expor somente `media/public/` por Nginx somente-leitura; ali ficam logos institucionais com
  cache longo e nomes imutáveis.
- Manter `media/private/` sem URL pública. Fotos são entregues inline por endpoints autenticados;
  documentos e justificativas são anexos com `private, no-store` e `nosniff`.
- Usar `PLATFORM_DOMAIN` e `TENANT_BASE_DOMAIN`, limitando tenants a um subdomínio gerenciado.
- Emitir wildcard via ACME DNS-01 e guardar a credencial como Docker secret.
- Fixar imagens por digest e exigir a imagem da aplicação também por digest.

## Consequências

Deploy multi-node depende da disponibilidade, backup e permissões do NFS. Domínios customizados
ficam fora desta etapa. A migração e o rollback seguem `docs/36_PRODUCTION_RUNBOOK.md`.

## Adendo — imagens canônicas (2026-09-16)

Avatares e fotos são gravados somente como WebP de até 512 px no maior lado (qualidade 85);
logotipos usam até 1024 px e WebP sem perdas. Não guardamos o original. O processamento preserva
proporção e transparência, corrige orientação EXIF, converte perfis ICC válidos para sRGB e remove
metadados. JPEG, PNG e WebP devem ser íntegros, estáticos, ter até 5 MiB e 25 megapixels.
Documentos de matrícula e frequência conservam seus próprios contratos e não são otimizados.

O caminho canônico é `<namespace>/<categoria>/optimized/v1/<UUID>.webp`. O namespace corresponde
ao schema até 28 caracteres; acima disso usa `~s` e os primeiros 26 caracteres hexadecimais do
SHA-256 do schema. O prefixo `~` não é um identificador de schema válido, evitando colisão com
schemas literais. A plataforma usa `public`. Isso mantém os campos atuais de 100 caracteres sem
alterar models ou migrations. A divisão pública/privada e o NFS permanecem inalterados.

Cada comando registra arquivos novos antes da escrita e compensa suas falhas, inclusive comandos
aninhados e falhas na saída da transação. A compensação consulta referências antes de excluir;
falhas de consulta ou storage retêm o arquivo e geram log técnico sem PII. Exclusão de substituídos
ocorre após commit e respeita referências inclusive inativas. Não existe atomicidade distribuída
entre banco e disco: rollback de uma transação externa ou crash pode deixar órfãos, recuperados
pela reconciliação explícita após 24 horas.

A manutenção CLI é uma operação de infraestrutura. Conversões de registros geram AuditLog
transacional; a remoção de um arquivo órfão sem entidade é a exceção específica: gera evento
`orphan_image_removed` com schema, alias de storage e identificador hash opaco, sem caminho,
conteúdo ou PII. Não se cria nem simula uma exclusão de entidade para representar esse evento.
A reconciliação limita-se aos nomes gerados (UUID de imagem ou UUID WebP em `optimized/v1`),
recusa symlinks, revalida referências globalmente e falha fechada se um schema não for consultável.
O prefixo antigo `platform` não é reconciliado pela plataforma quando existir um tenant homônimo.

Quando existe tenant `platform`, nomes anteriores sem `optimized/v1` nesse prefixo são
ambíguos e ficam retidos também na reconciliação do tenant.
