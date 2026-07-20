# Padrões de Interface

> **Fonte de verdade de frontend.** Em caso de divergência, este documento prevalece sobre Sprints, exemplos históricos e instruções resumidas para agentes.

## Princípios e stack

- Django Templates renderiza a tela inicial; HTMX atualiza somente o menor fragmento necessário.
- O tema é Duralux sobre Bootstrap 5. Assets são locais via `{% static %}`; não usar Bootstrap por CDN.
- Usar Feather Icons e evitar JavaScript customizado complexo. Alpine.js só pode controlar estado local.
- Telas autenticadas herdam de `base.html`; formulários herdam de `form_base.html`, `person_form_base.html` ou `entity_form_base.html` conforme o caso. Páginas públicas podem seguir a exceção standalone definida abaixo.
- `page_shell_base.html` é o shell obrigatório de páginas operacionais com grade primária;
  `list_page_base.html` é o shell obrigatório das listagens. Eles fornecem breadcrumb e cabeçalho
  aderentes, margens, card vertical e a divisão entre conteúdo fixo e região rolável.
- Os tokens canônicos são: cabeçalho global de 80px, cabeçalho da página de 65px, margens
  laterais de 30px no desktop e 20px no mobile, e recuo interno de registros de 30px à esquerda
  e 15px à direita.

## Páginas públicas e landing pages

- Landing pages públicas podem usar layout standalone quando a navegação, a hierarquia e o objetivo de conversão forem diferentes da aplicação autenticada.
- Bootstrap, Feather Icons, estilos e scripts continuam sendo assets locais via `{% static %}`; não adicionar CDN, rastreadores ou bibliotecas de animação apenas para efeitos visuais.
- A página deve manter HTML semântico, um único `h1`, skip link, foco visível, navegação real por `href` e controles com nome e relacionamentos ARIA adequados.
- Animações devem reforçar hierarquia e feedback, ocorrer uma única vez quando possível e respeitar `prefers-reduced-motion`. Não usar scroll-jacking, parallax agressivo, contadores artificiais ou movimento indispensável à compreensão.
- Mockups e indicadores demonstrativos precisam ser identificados como exemplos visuais; não podem ser apresentados como métricas comerciais, prova social ou garantia de resultado.
- Conteúdo comercial anuncia somente integrações, canais, importações e níveis de serviço realmente disponíveis. O CTA principal deve apontar para um fluxo público existente e manter fallback sem JavaScript.

## Tema claro e escuro

- O alternador global de tema fica no cabeçalho, antes do menu de usuário e ao lado das notificações quando elas existirem.
- Usar `app-skin-dark`, tema nativo do Duralux; não criar temas paralelos por página.
- A preferência é local ao navegador e deve ser aplicada antes dos estilos para evitar piscada. Botões apenas com ícone exigem `aria-label` que descreva a próxima ação.

## Navegação lateral

- No contexto escolar, **Visão geral** permanece como acesso direto e os demais destinos são agrupados por departamento: Acadêmico, Secretaria, Coordenação e Administração.
- Para funcionários, a taxonomia canônica é:
  - **Acadêmico:** Turmas, Disciplinas, Grade Horária, Atividades, Frequência e Agenda;
  - **Secretaria:** Professores, Alunos, Responsáveis, Matrículas, Salas e Itens da Agenda;
  - **Coordenação:** Calendário, Feriados, Anos Letivos e Comunicados;
  - **Financeiro:** Visão Financeira, Modelos, Contratos, Cobranças, Baixas e Conciliações,
    Lembretes, Competência e Caixa e Inadimplência;
  - **Administração:** Unidades, Escola, Usuários e Acessos.
- Professores usam os grupos **Rotina Docente** e **Planejamento**. Responsáveis usam somente
  **Acompanhamento**. Permissões auxiliares de módulo não devem criar links fora da taxonomia do
  papel.
- Alunos e Responsáveis são destinos separados; os vínculos continuam editáveis nas fichas.
- Os departamentos usam o accordion nativo do Duralux. Somente o grupo da rota atual inicia expandido e apenas um grupo permanece aberto por vez.
- Listagens, cadastros, edições e fichas destacam o item principal de sua família de rotas; grupos sem nenhum item autorizado não são renderizados.
- A composição do menu reutiliza as políticas de `core.permissions`; templates não duplicam regras de acesso.
- **Acessos** é exclusiva do Administrador e exibe uma matriz completa: módulos nas linhas e
  Secretaria, Coordenação, Professor, Financeiro e Responsável nas colunas. Cada célula elegível
  usa um dropdown múltiplo com Visualizar, Cadastrar, Editar e Desativar; a seleção aparece como
  `V`, `C`, `E`, `D`. Administrador não aparece e combinações incompatíveis exibem `—`.
  Os escopos de Professor e Responsável permanecem obrigatórios, mas não são exibidos como
  legendas na matriz nem podem ser configurados nessa tela.
- **Calendário**, **Feriados** e **Anos Letivos** são capacidades independentes. Feriados e Anos
  Letivos aceitam somente Visualizar, Cadastrar e Editar para Secretaria, Coordenação e Financeiro;
  Professor e Responsável exibem `—`. A leitura de feriados dentro do calendário continua
  subordinada apenas ao acesso ao Calendário.
- Os oito processos financeiros são capacidades independentes. Visão Financeira, Competência e
  Caixa e Inadimplência oferecem somente Visualizar; Lembretes oferece Visualizar e Editar; os
  demais oferecem Visualizar, Cadastrar e Editar. Secretaria e Coordenação não recebem defaults,
  Professor exibe `—` e Responsável pode receber somente Visualizar em Visão Financeira e
  Cobranças, sem acesso padrão.
- A matriz possui um único botão **Salvar acessos**. Cabeçalho e primeira coluna permanecem fixos,
  com rolagem horizontal em telas estreitas; dropdowns precisam ser operáveis por teclado.
- A busca da matriz usa o visual padrão de listagem, mas filtra módulos e departamentos localmente,
  sem HTMX, para preservar todas as alterações ainda não salvas. Os dropdowns exibem somente as
  opções; o contexto completo da célula permanece disponível apenas para tecnologias assistivas.
- Controles de criar, editar e desativar só são renderizados quando a mesma capacidade exigida
  pela rota estiver ativa. Ocultar o controle não substitui a validação no middleware e service.
- Controles de expansão usam botão, foco visível, `aria-expanded` e `aria-controls`. A preferência de abertura não é persistida.
- Quando o conteúdo excede a altura disponível, a rolagem permanece interna e acessível por mouse, trackpad, toque e teclado, mas o trilho visual do scrollbar não é exibido.
- Links do menu escolar usam navegação progressiva: mantêm menu e cabeçalho no DOM, substituem somente `#app-main` e atualizam o estado ativo do menu por metadados do novo conteúdo. URL, título e histórico são preservados; o `href` real é obrigatório como fallback.
- Links internos do conteúdo, formulários, ações destrutivas e o menu da plataforma não participam da navegação parcial global.

## Listagens

- Herdar de `list_page_base.html`. Título, breadcrumb, contador, busca, botão `+ NOVO`, card,
  área rolável e paginação são fornecidos pelo shell; blocos existem apenas para conteúdo de
  domínio e extensões registradas, como as abas de Cobranças.
- Registrar cada listagem no catálogo tipado `core.ui_catalog.LIST_PAGE_CATALOG`, indexado pelo
  nome da rota. Título, rota de criação, alvo HTMX, busca e rótulo do contador não podem ser
  duplicados em templates.
- O card sempre exibe **Lista de &lt;domínio&gt;**.
- Toda lista usa região `table-responsive sm-scroll-region`, `tabindex="0"`, nome acessível,
  foco visível, `sm-sticky-table sm-sticky-table--first-column`, `{% empty %}` e paginação HTMX
  centralizada. Mouse, trackpad, toque e teclado devem operar a mesma região.
- A primeira coluna identifica o registro e é o link para ficha/detalhe; sem ficha, aponta para a tela operacional principal.
- Colunas ordenáveis usam `resolve_listing_state`, `build_sorting` e links HTMX. Busca, ordenação, filtros e página devem ser preservados na query string.
- Não criar coluna **Ações** apenas para repetir Ver ou Editar. Ações administrativas ficam na ficha; ações operacionais (aprovar, preencher chamada, lançar nota) ficam no contexto do fluxo.
- O documento não rola nem cria overflow horizontal em listagens e grades primárias. Cabeçalho,
  filtros, contexto e rodapé permanecem fora da rolagem; somente `.sm-scroll-region` ocupa o
  espaço restante e altera `scrollTop`. Cabeçalho da tabela e primeira coluna permanecem fixos.

```html
<a href="?{{ sorting.name.query }}" class="sm-sort-link{% if sorting.name.active %} is-active{% endif %}"
   hx-get="?{{ sorting.name.query }}" hx-target="#resource-table" hx-swap="innerHTML">
    Nome
</a>
```

## Fichas e edição

- Fichas usam `row g-3 align-items-start`, com `col-12 col-xl-5` para informações e `col-12 col-xl-7` para relações/endereço.
- O card de informações agrupa os dados principais. Endereços e relações de domínio ficam em cards próprios.
- Editar fica no cabeçalho do card e substitui apenas o componente com `hx-target="#card-id"` e `hx-swap="outerHTML"`.
- Valores sem dado exibem `—`.
- Ações de perfil, como Alterar senha, ficam no card correspondente, não no cabeçalho geral da página.

## Formulários

- Formulários de cadastro e edição usam a mesma largura/posição da ficha e grade compacta `row g-2`.
- Em turmas, `Série` é um seletor estático dependente de `Etapa de Ensino`; não existe cadastro
  separado de séries, e a validação no service permanece obrigatória sem JavaScript.
- Campos usam `partials/form_field.html`; erros e asteriscos de obrigatoriedade são exibidos pelo partial.
- Forms com upload definem `enctype="multipart/form-data"` e, em HTMX, `hx-encoding="multipart/form-data"`.
- Avatar, foto e logotipo são o objeto editável do topo do formulário: imagem/monograma dentro de um `<label>` associado ao input oculto (`sm-profile-avatar-input`). Não exibir um controle “Choose file” no corpo do formulário.
- Pessoas usam `person_form_base.html`; entidades administrativas usam `entity_form_base.html` e o partial de organização quando há logotipo.

## Pessoas, usuários e organizações

- Perfis de pessoa reúnem identidade, dados pessoais, documentos e contato em um card; apenas endereço e relações são separados.
- Usuários seguem o mesmo padrão de perfil, incluindo avatar editável no topo.
- **Unidades** é a nomenclatura da entidade `BusinessUnit`; não usar “Empresas” na interface atual. Escola é a configuração do tenant e permanece distinta de Unidades.
- Unidade e Escola exibem e editam o logotipo no topo do card de informações.
- Matrículas de professor e aluno são informativas e somente leitura; o sistema as gera ao salvar.
- Responsáveis editam seus vínculos com alunos no card lateral da mesma tela de edição.
- Grades de notas e frequência pré-carregam os alunos e deixam editáveis apenas os dados do
  lançamento.
- A Agenda pré-carrega todas as crianças ativas em uma listagem canônica dentro de um único card.
  Turma e data usam controles pequenos no cabeçalho da lista e são aplicadas explicitamente pelo
  botão **Carregar**. O cabeçalho da página, os filtros, a identificação da turma e o rodapé ficam
  fora da rolagem; somente a grade rola. A primeira coluna liga ao histórico do aluno e permanece
  fixa, e a identificação da turma usa o mesmo recuo esquerdo de 30px da Central de Acessos.
- Cada item ativo e aplicável ao turno ocupa uma coluna com dropdown de escolha
  única, seguindo a densidade da Central de Acessos. Observações usam um dropdown próprio com
  textarea de seis linhas e largura de até 520px, limitada ao viewport, sem aumentar a altura da
  linha. O painel exibe **Melhorar com IA — em breve** desabilitado enquanto não houver integração.
  Erros aparecem na própria célula e alterações não salvas são indicadas na situação do aluno.
- Há um único botão **Salvar Agenda** no rodapé, que envia a turma inteira atomicamente. Professores
  usam **Enviar para revisão**; coordenação e administração usam **Publicar** ou **Devolver para
  correção** com motivo. Conteúdo em revisão ou publicado é somente leitura, mas seus dropdowns
  continuam inspecionáveis por teclado.
- Administração e coordenação recebem notificação com link direto e veem no dashboard as dez
  pendências mais recentes. A folha destaca a próxima etapa e mantém Publicar/Devolver no topo.
- Revisores veem um resumo agregado de entrega por revisão; endereços dos responsáveis nunca são
  exibidos nessa área.
- O histórico do responsável mostra somente snapshots publicados do aluno para o qual mantém
  guarda. A ficha agrupa o `answers_snapshot` por seção, registra a visualização automaticamente
  por POST com CSRF e não contém campo ou botão para responder, reagir ou confirmar.
- A instalação PWA e a ativação de notificações Push são opcionais. O estado offline mostra apenas
  uma página genérica e não sugere que a Agenda possa ser consultada sem conexão.
- A seção Alimentação inicia com Café da manhã, Almoço e Café da tarde conforme o turno e inclui
  a opção Não estava presente. Itens de Alimentação aparecem antes de Como foi o dia. A grade usa
  cabeçalho e primeira coluna fixos e concentra sua rolagem
  vertical e horizontal no card, sem criar overflow horizontal no documento. Seus menus são
  anexados temporariamente ao `body` e posicionados pelo Popper com estratégia fixa, `flip` e
  `preventOverflow`; ao fechar, retornam à célula de origem. A inicialização é repetida após HTMX.
- **Itens da Agenda** segue a listagem e ficha canônicas e permite cadastrar itens nas seções
  Como foi o dia e Alimentação. Itens novos começam inativos; a ficha cadastra suas opções antes
  da ativação. Nome/rótulo, seção, turnos, ordem, obrigatoriedade e disponibilidade ficam
  explícitos. A edição do item
  substitui somente o card de informações e opções são criadas ou editadas no próprio card.
- A Agenda oferece somente itens disponíveis para novas escolhas. Uma resposta já salva continua
  visível quando seu item, turno ou opção se torna indisponível, mas não pode ser escolhida por outro
  registro. A capacidade `diary_configuration`, com ações Visualizar, Cadastrar e Editar, é
  independente de `student_diary`, usada para preencher, revisar e publicar a Agenda.

## Financeiro

- Dashboard, relatórios e fichas usam `page_shell_base.html`; modelos, contratos, cobranças,
  conciliações e lembretes são listagens registradas no catálogo canônico.
- As fichas de modelo e contrato usam a grade 5/7. A edição do contrato em rascunho substitui
  somente o card de informações; contrato ativo é alterado somente pelo fluxo de aditivo.
- Listagens preservam busca, filtros, ordenação e paginação na query string. Tabelas mantêm
  cabeçalho e primeira coluna fixos e restringem a rolagem a `.sm-scroll-region`.
- A primeira coluna contém o link principal. Não repetir Ver/Editar em Ações. Cobranças combinam
  badges de quitação — não paga, parcial ou paga — e temporalidade — a vencer, vence hoje ou
  vencida.
- A baixa permite selecionar o aluno, editar a distribuição entre cobranças abertas e revisar os
  encargos; a confirmação ocorre na fila de conciliação. Recibo e extrato abrem PDFs server-side.
- Relatórios sempre exibem período e base de cálculo. Competência e caixa são cards separados;
  inadimplência oferece drill-down e CSV.
- Todos os CTAs respeitam `can_access_url` ou a ação equivalente. A visão do Responsável omite
  notas, referência manual, conciliação e auditoria e limita dados aos alunos sob guarda ativa.
- Para funcionários, Financeiro permanece como departamento. Para Responsáveis habilitados,
  Visão Financeira e Cobranças aparecem separadamente dentro de Acompanhamento.
- Atalhos, indicadores e links entre processos usam a capacidade da rota de destino. A permissão
  de Visão Financeira não concede acesso implícito a cadastros, conciliação, lembretes ou
  relatórios.
- O fluxo mantém fallback sem JavaScript, mensagens Django centralizadas, foco visível, teclado,
  tema escuro e geometrias verificadas em 1280x720, 1280x480 e 390x844.

## HTMX, acessibilidade e feedback

- Busca: `hx-trigger="keyup changed delay:300ms, search"`.
- Paginação e ordenação: `hx-target` aponta para a tabela/fragmento e preserva a query string.
- Botões exclusivamente com ícone exigem `aria-label`; imagens exigem `alt`; navegação de página exige `aria-label`.
- `base.html` renderiza mensagens Django. Views usam `messages.success()` e `messages.error()` sem duplicar alertas nos templates.

## CSS, contrato e regressão visual

- `design_system/refs/duralux/css/school-manager.css` é a única fonte do CSS customizado. O
  diretório é publicado por `STATICFILES_DIRS`; é proibida uma cópia em `static/css`.
- `base.html` referencia o asset com `{% static %}` sem versão manual. Desenvolvimento tolera a
  URL simples e produção usa o nome com hash de conteúdo gerado pelo manifesto não estrito.
- `python scripts/check_ui_contracts.py` bloqueia listagens e grades fora dos shells, composição
  manual de `page-header`/`main-content`, regiões sem acessibilidade ou coluna fixa, rotas de
  catálogo inválidas e exceções não registradas.
- O marcador `ui` executa no Chromium, em job próprio, asserções geométricas nos viewports
  1280x720, 1280x480 e 390x844. Screenshots e traces são diagnósticos de falha, não baselines
  pixel a pixel.

## Referências

- Regras de arquivos de template: `.github/instructions/templates.instructions.md`.
- Arquitetura de camadas: `docs/02_ARCHITECTURE.md` e `docs/03_ENGINEERING_RULES.md`.
- Regras de dados, segurança e multi-tenancy: `docs/05_DATABASE.md`, `docs/04_SECURITY.md` e `docs/06_MULTI_TENANT.md`.
