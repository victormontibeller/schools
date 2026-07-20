# Subagentes do School Manager

Este diretório define a equipe persistente de subagentes do projeto. O Codex carrega cada arquivo TOML como um tipo de agente disponível para delegação.

| Agente | Papel | Escrita |
|---|---|---|
| `school_explorer` | Explora arquitetura, documentação, dependências e reutilização | Não |
| `school_builder` | Implementa código e testes dentro do escopo atribuído | Sim |
| `school_guardian` | Audita segurança, tenancy e cobertura de testes | Não |
| `school_reviewer` | Revisa o diff final e a Definition of Done | Não |

## Regras de uso

- O agente principal mantém requisitos, decisões, integração e resposta final.
- Delegue automaticamente apenas tarefas grandes com frentes realmente independentes.
- Entre os subagentes, somente `school_builder` escreve. Enquanto ele estiver editando, o agente principal aguarda e inicia a integração depois da conclusão.
- Espere todos os agentes solicitados e consolide os resultados; não copie saídas intermediárias sem curadoria.
- Mantenha a profundidade padrão de um nível. Os subagentes não criam novos subagentes.
- A permissão ativa da tarefa principal pode restringir ainda mais o sandbox configurado no agente.

Depois de adicionar ou alterar esses arquivos, abra uma nova tarefa ou recarregue o Codex para garantir que a configuração seja reconhecida.

## Prompts prontos

### Desenvolver uma funcionalidade

```text
Implemente <funcionalidade>. Use school_explorer para mapear arquitetura, helpers e impactos e school_guardian para antecipar riscos de segurança, tenancy e testes. Espere ambos, consolide o escopo e delegue somente a implementação para school_builder. Ao final, use school_reviewer, espere sua revisão e entregue a validação consolidada.
```

### Diagnosticar um problema

```text
Diagnostique <problema> sem implementar a correção. Execute school_explorer e school_guardian em paralelo, espere os dois e apresente causa raiz, evidências, impacto e opções de correção.
```

### Revisar uma branch ou PR

```text
Revise esta branch em relação a <branch-base>. Execute school_guardian e school_reviewer em paralelo, espere os dois e consolide apenas achados acionáveis, ordenados por severidade e com referências aos arquivos.
```

### Analisar segurança

```text
Analise <fluxo ou diff> com school_guardian. Verifique autorização, tenant, transação, concorrência, auditoria, PII em logs, soft delete, efeitos após commit e cobertura de testes. Não altere arquivos. Espere o agente e resuma os riscos confirmados e residuais.
```
