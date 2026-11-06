# Mapeamento READ-ONLY — grafo de estado interno do NFeEntradaConferenciaPanel

> Fase 2 · PR 5. Documento de orientação para a extração bloco-a-bloco (PRs 6+).
> **Nenhum arquivo de código foi alterado.** Fonte única de verdade: o disco.
> Arquivo mapeado: `frontend/src/components/fiscal/NFeEntradaConferenciaPanel.tsx`.

## 0. Divergências de disco vs. enunciado/Fase 0 (priorizo o disco)

- **Contagem de linhas:** o enunciado/Fase 0 diz **1943**; o disco (`wc -l`) diz **1953**. Diferença de +10 = hunks do PR 4 (import `UnifiedEntradaFeed`, comentário+swap do rail, `AuditoriaHistorico`/`ItemHistoricoAuditoria`). Toda linha citada abaixo é a **linha real no disco (HEAD 7672aa6)**.
- **Imports dos sub-componentes:** a Fase 0 citou `GerarContasPagarNfeEntradaModal :6, FornecedorEntradaAcoes :7, NFeEntradaFinanceiroAcoes :8, NFeEntradaReabrirModal :9, NFeGerarDevolucaoCompraModal :10`. No disco estão **deslocados em +1** porque o PR 4 inseriu `UnifiedEntradaFeed` na linha 6: `GerarContasPagar :7, FornecedorEntradaAcoes :8, NFeEntradaFinanceiroAcoes :9, NFeEntradaReabrirModal :10, NFeGerarDevolucaoCompraModal :11`. `EquivalenciaEntradaEditor` :70 (o bloco `import {...}` abre :69–76).
- **Os "5 blocos lógicos" canônicos NÃO correspondem 1:1 às regiões reais de JSX.** Na realidade do disco:
  - **equivalência existe em DUAS superfícies**: (a) `<details>` "Equivalências e Composições" (:832–963) — sugestões de agrupamento com confirmar/rejeitar; (b) **por item**, dentro da tabela (:1552–1584) via `EquivalenciaEntradaEditor`. Elas **não compartilham estado entre si** além do `dados`.
  - **estoque** está em TRÊS superfícies: gating derivado (:134–147), botão da barra (:1727–1741) + modal `<Modal>` (:1774–1882), e **colunas por item** na tabela (CorridaSplit :1456, estoque_barras :1594, quantidade_estoque_calculada :1585).
  - A **tabela de itens** (:1061–1664) é uma **região compartilhada** que hospeda correlação de produto (:1355–1437), equivalência por item (:1552), estoque por item (:1456/:1585), alocação de venda (:1439) e status/ignorado (:1633–1657). Ela **não é** um dos 5 blocos — é um *hub* onde equivalência e estoque se entrelaçam. Matriz ajustada para essa realidade, sem forçar os 5 canônicos.

---

## 1. Inventário de hooks (arquivo:linha da declaração)

Declaração única: `import { useCallback, useEffect, useMemo, useState }` (:1). Nenhum hook custom local (`use*`) definido no arquivo; `useNavigate` (:105) é do router.

| # | Identificador | Declaração | Natureza |
|---|---|---|---|
| H1 | `dados` / `setDados` | :107 | **CENTRAL** — a entidade inteira `NFeEntradaConferencia` |
| H2 | `pedidos` / `setPedidos` | :108 | compartilhado (header + tabela) |
| H3 | `produtoCache` / `setProdutoCache` (+alias `produtosMap` :132) | :109 | **compartilhado** (tabela, equivalência, estoque, pedido-labels) |
| H4 | `erro` / `setErro` | :110 | compartilhado (banner global :1055) |
| H5 | `avisoPedido` / `setAvisoPedido` | :111 | header (aviso de troca de pedido) |
| H6 | `busy` / `setBusy` | :112 | **compartilhado** (salvar/preparar/aplicar) |
| H7 | `resumoAberto` / `setResumoAberto` | :113 | local (card "Comparação com o pedido") |
| H8 | `resumoFiscalAberto` / `setResumoFiscalAberto` | :114 | local (card resumo fiscal) |
| H9 | `resumoElegibilidadeAberto` / `setResumoElegibilidadeAberto` | :115 | local (card elegibilidade) |
| H10 | `soPendencias` / `setSoPendencias` | :116 | local da tabela (filtro Todas/Só pendências) |
| H11 | `modoTecnico` / `setModoTecnico` | :117 | local da tabela (colunas técnicas) |
| H12 | `equivalenciasAberto` / `setEquivalenciasAberto` | :118 | **local do bloco equivalência-sugestões** (:835–836) |
| H13 | `eqBusy` / `setEqBusy` | :119 | **local do bloco equivalência-sugestões** (:897–940) |
| H14 | `modalAplicarOpen` / `setModalAplicarOpen` | :120 | **local do bloco estoque** (:312/:367/:1859) |
| H15 | `previewAplicar` / `setPreviewAplicar` | :121 | **local do bloco estoque** (:321–:1860) |
| H16 | `confirmarAlertasAplicar` / `set…` | :122 | **local do bloco estoque** (:314/:1828) |
| H17 | `obsAplicar` / `setObsAplicar` | :123 | **local do bloco estoque** (:315/:1851) |
| H18 | `modalAplicarErro` / `set…` | :124 | **local do bloco estoque** (:313–:1861) |
| H19 | `gerarCpOpen` / `setGerarCpOpen` | :125 | **local do bloco financeiro** (:619/:1885/:1887) |
| H20 | `reabrirOpen` / `setReabrirOpen` | :126 | **local do bloco reabertura** (:1756/:1898/:1900) |
| H21 | `showDevolucaoCompra` / `set…` | :127 | **local do bloco devolução** (:1746/:1913/:1916/:1918) |
| H22 | `sugestoesCorrelacaoIgnoradas` / `set…` | :128 | local da célula de correlação de produto (:1355/:1382) |
| H23 | `buscarProdutos` (useCallback) | :149 | estável, consumido pela tabela (`AsyncAutocomplete` :1419) |
| H24 | `hydrateProdutoCache` (useCallback) | :151 | **compartilhado** — escreve H3; chamado por load/salvar/preparar/aplicar/equiv-confirm/reabrir |
| H25 | `pedidoSelecionado` (useMemo) | :172 | derivado de H1+H2; consumido pela tabela (:1340) e `produtoIdDoItemPedido` |
| H26 | `progresso` (useMemo) | :177 | derivado de H1; consumido por header/tabela |
| H27 | `proximoPasso` (useMemo) | :178 | derivado de H1+H26; consumido pelo header (:498) |
| H28 | `itensVisiveis` (useMemo) | :179 | derivado de H1+H10; consumido pela tabela (:1143) |
| H29 | `useEffect(load)` | :197 | produz H1,H2,H3,H4,H5 via `load()` (:184–195) |

Derivados **sem** hook (só `const`, recomputados a cada render): `estoqueJaAplicado` :133, `podeAplicarEstoque` :134, `podeFinalizarConferencia` :143, `acaoOperacionalDisponivel` :145, `aplicarEstoqueHabilitado` :147, `pctProdutos` :425, `pendenciaFornecedor` :436, `itensSemVinculo` :437, `temPendenciaConferencia` :438. Estes leem H1/H26 e são consumidos por header, barra e estoque.

---

## 2. Matriz bloco × estado (consumo/produção, arquivo:linha por célula)

Legenda: **C** = consome (lê), **P** = produz/muta (chama setter/invalida). Linhas = evidência lida no disco.

| Estado | GERAL/cabeçalho | EQUIVALÊNCIA | ESTOQUE | FINANCEIRO | DEVOLUÇÃO | REABERTURA | Compartilhado? |
|---|---|---|---|---|---|---|---|
| **H1 dados** | C :504/562/577 · P :234/258/286/565 | C :832/840/850 · P :912/935 (via confirmar/rejeitar) | C :133–147/308/359 · P :319/362/407/412 | C :617/618 · *(P via load :1890)* | C :1915 (`itensConferencia`) · *(P via load :1922)* | *(P :1902)* | **SIM — espinha dorsal. Todos os blocos.** |
| **H3 produtoCache** | C :132→labels | P :211/222 · C via `produtosMap` :1558 | C :1617 (fator unidade) | — | — | P :1903 (hydrate) | **SIM** |
| **H4 erro** | P :186/276/309 · C :1055 | P :901/915/937 | P :383→(modalAplicarErro é H18 separado) | — | — | — | **SIM** |
| **H6 busy** | C :602/1707/1716 · P :275/316/353/396 | — | C :1732 · P :316/326/353/386 | — | C :1747 | C :1757 | **SIM** |
| **H24 hydrateProdutoCache** | chamado :194/287 | chamado :913 | chamado :363/408 | — | — | chamado :1903 | **SIM** |
| **H25 pedidoSelecionado** | — | — | — | — | — | — | tabela/header (C :1340) |
| **H12 equivalenciasAberto** | — | **C/P :835/836** | — | — | — | — | **LOCAL equiv-sugestões** |
| **H13 eqBusy** | — | **C/P :897/900/917/926/929/939** | — | — | — | — | **LOCAL equiv-sugestões** |
| **H14 modalAplicarOpen** | — | — | **C/P :312/367/1774/1859** | — | — | — | **LOCAL estoque** |
| **H15 previewAplicar** | — | — | **C/P :321/324/368/380/1774–1874/1860** | — | — | — | **LOCAL estoque** |
| **H16 confirmarAlertasAplicar** | — | — | **C/P :314/357/1827/1828/1874** | — | — | — | **LOCAL estoque** |
| **H17 obsAplicar** | — | — | **C/P :315/358/1850/1851** | — | — | — | **LOCAL estoque** |
| **H18 modalAplicarErro** | — | — | **C/P :313/323/354/381/383/1781/1861** | — | — | — | **LOCAL estoque** |
| **H19 gerarCpOpen** | — | — | — | **C/P :619/1885/1887** | — | — | **LOCAL financeiro** |
| **H20 reabrirOpen** | — | — | — | — | — | **C/P :1756/1898/1900** | **LOCAL reabertura** |
| **H21 showDevolucaoCompra** | — | — | — | — | **C/P :1746/1913/1916/1918** | — | **LOCAL devolução** |
| **H10 soPendencias** | — | — | — | — | — | — | tabela (C/P :1072–1115, H28) |
| **H11 modoTecnico** | — | — | — | — | — | — | tabela (C/P :1104–1285) |
| **H22 sugestoesCorrelacaoIgnoradas** | — | (correlação de produto) | — | — | — | — | local :1355/1382 |

**Leitura da matriz:** os 8 estados modal/flag-local (H12–H21) são **fechados dentro de um único bloco** — extração trivial. Os estados H1/H3/H4/H6/H24 são **transversais**: consumidos e produzidos por vários blocos — exigem lift (ficam no painel ou num provider) e injeção por prop nos blocos extraídos.

---

## 3. Callbacks que ATRAVESSAM blocos (maior risco)

| Handler | Declaração | Blocos que toca | Evidência do atravessamento | Risco na extração |
|---|---|---|---|---|
| **`load()`** | :184–195 | GERAL (produz H1/H2/H3) | chamado por :198 (efeito), :365 (estoque fallback), :1890 (**financeiro** onGenerated), :1922 (**devolução** onSuccess), :1442 (**alocação** onAtualizado) | **CRÍTICO.** Toda ação terminal de financeiro/devolução/alocação/recalcula via load, que **sobrescreve dados,pedidos,produtoCache**. Um bloco extraído não pode "chamar load" localmente — precisa receber um `onRecarregar`/store. |
| **`salvar()`** | :273–304 | GERAL + ESTOQUE (via persist) + FINANCEIRO (lê `financeiro.possui_pendencias_operacionais` :289) | setDados/H4/H5/H6; rótulo do botão depende de H1.financeiro (:1708) | **ALTO.** Salvar não é só header: alimenta o preview de estoque e o rótulo financeiro. |
| **`salvarSilencioso()`** | :330–349 | ESTOQUE → persist | chamado por `abrirModalAplicar` :318; **duplica** o payload de `salvar` (:278 vs :332) | **ALTO.** Acoplamento estoque→persistência oculto; dois payloads idênticos que divergem na mão. |
| **`abrirModalAplicar()`** | :306–328 | ESTOQUE (produz H14–H18,H1,H6,H4) | chama `salvarSilencioso` + `previewAplicarEstoque` + `setDados` | **ALTO.** Dispara escrita na espinha dorsal antes de abrir o modal. |
| **`confirmarAplicarEstoque()`** | :351–388 | ESTOQUE (H1 via :362 ou H1 via `load()` :365, H14–H18, H24) | `aplicarEstoque` + `setDados`/`load` + `notifyUpdated` | **ALTO.** Muta dados e notifica o pai. |
| **`preparar()`** | :390–423 | GERAL/ESTOQUE (salvar+prepararEstoque→H1 :407/412, H24, H5) | rótulo "Finalizar" da barra (:1715) | **ALTO.** Recalcula tudo. |
| **equiv confirmar/rejeitar** | inline :898–941 | EQUIVALÊNCIA→H1 (:912/935) + H24 (:913) + H4 | `confirmarEquivalencia`/`rejeitarEquivalencia` | **MÉDIO.** Escreve espinha + cache de produto. |
| **`updateItem()`** | :232–248 | TABELA → H1 (por linha) | produto (:1373/1405/1435), corridas (:1466/1486/1493), equivalência (:1569/1575), status (:1637), ignorado (:1654) | **CRÍTICO para tabela.** Muta `dados.itens` fatiado; é o único caminho de edição por linha. Bloco extraído da tabela **precisa** receber `updateItem` + `dados`. |
| **reabrir onSuccess** | inline :1901–1909 | REABERTURA→H1 (:1902) + H24 + notify + navigate condicional | `if (!embedded)` :1906 | **MÉDIO.** Reseta dados e depende do modo. |
| **`notifyUpdated()`** | :228–230 | todos→pai | chama `onUpdated?.()` | BAIXO, mas é contrato de saída por bloco. |

---

## 4. Contrato `embedded` (o que muda entre os 2 modos)

- **Branch de retorno:** :1931–1933 `if (embedded) return <div>{conteudo}</div>;` (cru, sem shell). Standalone: :1935–1952 `<FormShell … pipeline … rail={UnifiedEntradaFeed}>{conteudo}</FormShell>`.
- **`{conteudo}` é a MESMA árvore nos dois modos** (:449–1927). Nada no conteúdo é montado condicionalmente ao modo **exceto**:
  - `barra-grupo-navegacao` :1696–1704: `!embedded` → botão "Voltar" (`navigate`) ; `embedded && onClose` → botão "Fechar" (`onClose`).
  - **Financeiro** onGenerated :1892–1894: `if (titulo?.id && !embedded) navigate(...)` — **lê `embedded`**.
  - **Reabertura** onSuccess :1906–1908: `if (!embedded) navigate(...)` — **lê `embedded`**.
- **Nenhum HOOK é condicional ao modo**: todos os useState (:107–130), useMemo (:172–182) e o useEffect (:197) rodam igualmente em `embedded` true/false (o efeito nem referencia `embedded`). **Prova:** `embedded` aparece apenas em :101 (prop), :1696/1892/1906 (branches de JSX/handler) e :1931 (return). Não há `if (embedded) setState` nem memo dependente do modo.
- **Consequência para extração:** os blocos **financeiro** e **reabertura** (e o grupo de navegação) precisam receber `embedded` (ou um callback `onNavigate`/`onTerminal` já resolvido) — não podem assumir navegação. Os demais blocos (equivalência, estoque, devolução, tabela) são **agnósticos ao modo**.

---

## 5. Proteção do investimento da Fase 1

### 5a. Rail do UnifiedEntradaFeed NÃO é consumido pelo `{conteudo}`

**Confirmado com evidência (não assumido):**
- A única referência a `UnifiedEntradaFeed` no arquivo é o **prop `rail`** do FormShell (:1947). Não há `import` de estado do feed no corpo do componente, nem variável que o feed escreva e o conteúdo leia.
- O rail é **irmão** do conteúdo no FormShell: `rail={<UnifiedEntradaFeed …/>}` (:1946–1948) vs. children `{conteudo}` (:1950). Fluxo de dados é **unidirecional de baixo para cima**: o feed **lê** `dados?.id` (:1947, H1) e `nfId` (:1947, prop :106). O feed produz apenas **estado interno próprio** (os hooks `useFonteAuditada` do PR 4, em `UnifiedEntradaFeed.tsx`), que **não vaza** para o painel — nenhuma linha do conteúdo referencia retorno do feed.
- **Corolário de extração:** mover um bloco lógico de `{conteudo}` **não afeta o rail**, desde que o shell-pai mantenha `dados?.id` e `nfId` disponíveis para compor o prop `rail`. Ou seja: `dados.id` continua sendo responsabilidade do painel (H1 fica no topo), e o rail preserva seu contrato PR 4 sem mudança.

### 5b. Mapa bloco → teste que o exercita (17 testes no disco)

| Bloco / superfície | Teste(s) que exercitam (arquivo) | Cobertura |
|---|---|---|
| GERAL/cabeçalho (FormShell, pipeline, barra) | `formShell` "cabeçalho… só com título/pipeline/voltar", "barra… três grupos", "pipeline… três estágios", "CANCELADA…", "seta…Voltar…", "rótulo do salvar…pendências", "em PENDENTE/PREPARADA/CONFERIDA" (gate botões) | **coberto** |
| rail unificado (Fase 1 PR 4) | `formShell` "PR 4: o rail standalone é o feed unificado…" | **coberto** |
| GERAL embedded (div cru, "Fechar") | `formShell` "mantém os três grupos e o Fechar, sem FormShell nem pipeline"; `nfeEntradaReaberturaAcoes` "exibe a ação no resumo final da Central DF-e" | **coberto** |
| Banner de pendências | `formShell` "aparece com fornecedor não identificado…", "conta os itens sem vínculo…", "não aparece quando…completa" | **coberto** |
| **REABERTURA** | `nfeEntradaReaberturaAcoes.test.tsx` "exibe a ação na tela de conferência" (:60) + "exibe a ação no resumo final da Central DF-e" (:78); `formShell` "Reabrir… abre o modal" + "em CONFERIDA… reabertura aparecem" | **coberto (2 + gates)** |
| **ESTOQUE** | `formShell` só os **gates** ("em PREPARADA: aplicar estoque visível porém desabilitado"; "em CONFERIDA: aplicar estoque habilita e abre o preview"). O **conteúdo do modal** (:1774–1882) e `confirmarAplicarEstoque`/`salvarSilencioso` **NÃO têm teste de interação**. | **parcial** |
| **FINANCEIRO** | `formShell` valida o **rótulo do salvar** por `possui_pendencias_operacionais`; o `GerarContasPagarNfeEntradaModal` (:1884–1896) e seu `onGenerated`/`load`/`navigate` **NÃO têm teste**. | **parcial / sem teste do modal** |
| **EQUIVALÊNCIA (sugestões :832–963)** | **nenhum** teste renderiza/aciona confirmar/rejeitar. | **SEM TESTE** |
| **EQUIVALÊNCIA por item — `EquivalenciaEntradaEditor` (776 l., uso :1552–1584)** | **nenhum** teste do painel o exerce. | **SEM TESTE — maior risco** |
| **DEVOLUÇÃO — `NFeGerarDevolucaoCompraModal` (223 l., :1912–1924)** | `formShell` "em CONFERIDA… devolução… aparecem" só prova o **botão**; o fluxo `onSuccess`/`load` **não**. | **SEM TESTE do fluxo** |
| **TABELA de itens / `updateItem`** | `formShell` não interage com linhas (produto/corrida/ignorado). `AlocarEntradaParaVendaBlock` (431 l.), `CorridaSplitEditor` (180 l.) têm testes próprios fora deste painel. | **SEM teste de edição por linha aqui** |

**Marcados para "extrair por último / exigir teste novo antes":**
1. **Equivalência** (ambas as superfícies) — 0 teste no painel; `EquivalenciaEntradaEditor` tem 776 linhas.
2. **Financeiro — modal GerarContasPagar** (435 linhas) — só o botão/gate coberto.
3. **Devolução — NFeGerarDevolucaoCompraModal** (223 linhas) — só o botão coberto.
4. **Tabela `updateItem`** — coração de edição compartilhada, sem teste de linha.

---

## 6. Ordem de extração recomendada (do mais isolado ao mais acoplado)

**Criterial:** isolamento = número de estados H1/H3/H4/H6/H24 que o bloco toca + se possui callbacks transversos + se tem teste.

1. **PR 6 — Reabertura** (`reabrirOpen` H20 + `NFeEntradaReabrirModal` :1897–1910).
   *Mais isolado dos terminais:* 1 estado local (H20), um modal já testado (2 casos), único atravessamento é o `onSuccess` que faz `setDados`+`hydrate`+`navigate(condicional)`. Extração = mover H20 e o JSX; recebe `nfId`, `embedded`, `onRecarregar`/`onSucesso(conferencia)` como props.
2. **PR 7 — Devolução** (`showDevolucaoCompra` H21 + `NFeGerarDevolucaoCompraModal` :1912–1924).
   1 estado local (H21); consome `dados.itens` (:1915) somente para popular o modal; `onSuccess` só faz `load()`. **Risco:** sem teste de fluxo → **criar teste antes de extrair** (§5b).
3. **PR 8 — Financeiro** (`gerarCpOpen` H19 + `NFeEntradaFinanceiroAcoes` :615–620 + `GerarContasPagarNfeEntradaModal` :1884–1896).
   Estados locais H19; mas **lê `dados.status`/`dados.financeiro`** (:617–618) e **escreve** só via `load()` (:1890). Depende de H1 imutável → exige que o store `dados` já esteja disponível. Teste só cobre rótulo → **exigir teste do onGenerated/navegação**.
4. **PR 9 — Estoque (modal + gating)** (H14–H18, :306–388, :1774–1882).
   Estados H14–H18 são **localizados ao estoque** (bom), **mas** `abrirModalAplicar`/`confirmarAplicarEstoque` atravessam H1 (:319/362) e `load()` (:365) e **duplicam persistência** (`salvarSilencioso`). Precisa de `updateItem`/`dados`/`load` injetados. Testes cobrem só gates.
5. **PR 10 — Equivalência (sugestões)** (:832–963, H12/H13).
   H12/H13 localizados (bom), **porém** confirmar/rejeitar escreve H1 (:912/935) + H24 + H4, e **zero testes** cobrem a superfície. **Exigir teste novo antes.**
6. **PR 11 (por último) — Tabela de itens + `updateItem`** (:1061–1664, H10/H11/H22/H25).
   É o **hub** onde equivalência-por-item, estoque-por-item, correlação e status coabitam e todos fluem por **um único** `updateItem` (:232) sobre H1. Extrair a tabela = extrair `dados`, `updateItem`, `produtoCache`, `produtosMap`, `buscarProdutos`, `pedidoSelecionado` de uma vez. Sem teste de edição por linha. **Só depois que PRs 6–10 já tiraram os modais terminais.**

> Alternativa conservadora: fazer PR 6–8 (terminais) → inserir uma **camada de store** (useReducer/contexto `useConferenciaStore` com `dados`, `setDados`, `updateItem`, `load`, `busy`, `erro`, `produtoCache`) → então PRs 9–11 consomem o store. Isso resolve de uma vez os 6 estados da espinha dorsal (§7).

---

## 7. Estado a LIFT / passar como prop

**Deve permanecer no topo do painel (ou migrar para um store/contexto único)** porque é consumido/produzido por ≥2 blocos:
- **H1 `dados` / `setDados`** — espinha dorsal. Nenhum bloco pode possuí-lo.
- **H3 `produtoCache` / `produtosMap` / `setProdutoCache`** — alimentado por header (autocomplete), equivalência (fatores), estoque (unidade), reabertura (hydrate).
- **H4 `erro` / `setErro`** — banner global (:1055) escrito por GERAL + EQUIVALÊNCIA (+ antes ESTOQUE via :309).
- **H6 `busy` / `setBusy`** — gating de salvar/preparar/estoque e dos botões devolução/reabertura.
- **H24 `hydrateProdutoCache`** — helper compartilhado.
- **`load`** (:184) — o ponto de recarga total; precisa virar `recarregar` injetável.
- **`nfId`** (:106) e **`embedded`** (:101) e **`onUpdated`/`onClose`** (:102–103) — props de ambiente que todos os terminais usam.
- **`updateItem`** (:232) — se a tabela for extraída, é o callback-mãe; senão fica no topo.

**Ficam locais ao bloco extraído (não precisam subir):**
- EQUIVALÊNCIA-sugestões: **H12 `equivalenciasAberto`**, **H13 `eqBusy`** (só :832–963).
- ESTOQUE-modal: **H14 `modalAplicarOpen`**, **H15 `previewAplicar`**, **H16 `confirmarAlertasAplicar`**, **H17 `obsAplicar`**, **H18 `modalAplicarErro`** (só :306–388 + :1774–1882).
- FINANCEIRO: **H19 `gerarCpOpen`** (só :619 + :1884–1887).
- REABERTURA: **H20 `reabrirOpen`** (só :1756 + :1897–1900).
- DEVOLUÇÃO: **H21 `showDevolucaoCompra`** (só :1746 + :1912–1918).
- TABELA: **H10 `soPendencias`**, **H11 `modoTecnico`**, **H22 `sugestoesCorrelacaoIgnoradas`** (só :1061–1664).
- GERAL: **H2 `pedidos`** (pode acompanhar um futuro "bloco pedido/header"), **H5 `avisoPedido`** (header), **H7/H8/H9** (cards informativos locais), **H25/H26/H27/H28** (memos derivados — recalculáveis por quem consumir H1).

---

## 8. Riscos nomeados + incertezas

**Riscos nomeados**
- **R1 — `load()` como recarga total (CRÍTICO):** 5 chamadas de blocos distintos (:365 estoque, :1890 financeiro, :1922 devolução, :1442 alocação, :198 efeito). Cada uma sobrescreve H1/H2/H3. Bloco extraído que "chama load" vira dependente do store.
- **R2 — `updateItem` como único caminho de edição (CRÍTICO):** 9 chamadas (:225/1373/1405/1435/1466/1472/1486/1493/1569/1575/1637/1654) de produto/corrida/equivalência/status. A tabela é inseparável de H1.
- **R3 — persistência duplicada (ALTO):** `salvar` (:278 payload) e `salvarSilencioso` (:332 payload) constroem o mesmo corpo em dois lugares → divergência silenciosa ao extrair estoque.
- **R4 — bloco equivalência em duas superfícies (MÉDIO):** sugestões (:832–963) e por-item (:1552) compartilham só H1; extrair uma e deixar a outra cria "equivalência partida".
- **R5 — dependência de modo (MÉDIO):** financeiro e reabertura leem `embedded` (:1892/:1906). Extração precisa injetar o modo ou o efeito de navegação.
- **R6 — blocos sem teste (ALTO):** Equivalência (776 l. editor + sugestões), GerarContasPagar (435 l.), Devolução (223 l.), tabela `updateItem` — ver §5b. **Exigir teste novo antes de extrair cada um.**

**Incertezas declaradas (não omitidas)**
- Não abri o **conteúdo** dos 6 sub-componentes importados (`EquivalenciaEntradaEditor`, `GerarContasPagarNfeEntradaModal`, `NFeGerarDevolucaoCompraModal`, `NFeEntradaReabrirModal`, `FornecedorEntradaAcoes`, `NFeEntradaFinanceiroAcoes`) — este PR mapeia o **estado do PAINEL**. O estado interno de cada sub-componente é fronteira fechada (eles recebem props e disparam callbacks); para extração fina dentro deles seria outro mapeamento.
- Não executei as suítes nem `tsc` (PR é read-only; não há alteração a validar). Os 17 testes são contados por `it(` no disco, não executados aqui.
- `notifyUpdated` (:228) propaga `onUpdated` ao pai (usado em :296/375/415/1891/1905). Tratei como contrato de saída, não como estado; se houver listener externo que grave em H1, isso não foi observado dentro deste arquivo.
- Não confirmei se `AlocarEntradaParaVendaBlock` (:1439) é considerado "bloco lógico" da Fase 0 — **não está** nos 5 citados, mas vive dentro da região de itens e chama `load()` (:1442); incluí nos callbacks transversais (R1) por segurança.
- Derivados sem hook (:133–147, :425, :436–438) recomputam a cada render; **não** precisam de lift, mas qualquer bloco extraído que dependa deles precisa de `dados` (+ `progresso`) em escopo.

---

## 9. Caminho do documento + estado do repositório

- Documento: `docs/mapeamento-estado-interno-conferencia.md` (convenção kebab-case `mapeamento-*` já usada por `docs/mapeamento-ecossistema-nfe-cte-entrada.md`).
- **Nenhum arquivo de código alterado** — todos os gates de §0–§8 foram por leitura/grep/`wc` no disco.
