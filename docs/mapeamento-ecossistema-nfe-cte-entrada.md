# Mapeamento Ecossistema NF-e/CT-e Entrada

Levantamento READ-ONLY de 2026-11-04. Nenhum arquivo existente foi alterado; nenhum commit foi feito. Este documento é o único arquivo novo.

## Resumo Executivo

O ecossistema de entrada tem 5 rotas dedicadas (`nfe-entrada`, `nfe-entrada-historica-importada`, `nfe-entrada/:id/conferencia`, `cte-entrada`, `cte-historico-importado`) mais a `central-dfe` como consumidora transversal. Só a conferência (`NFeEntradaConferenciaPanel`) segue o padrão Odoo com FormShell + Pipeline; as outras 4 telas usam `PageHeader` antigo, sem FormShell, sem Pipeline e sem Chatter. O backend concentra toda a escrita de conferência, financeiro, estoque e devolução em `@action` de dois viewsets `ReadOnlyModelViewSet`, com permissão `IsAuthenticated` e quase nenhuma auditoria (`registrar_nfe_entrada` só em CREATE/UPDATE da `NFeEntrada` operacional; a cadeia de conferência não registra nada). O modelo `CTeEntrada` nativo está órfão: sem caminho de escrita em produção, serializer importado e nunca usado. Nota: o contexto citava `NFeEntradaConferenciaPanel` com 1816 linhas — no disco são 1943 (verificado com `wc -l`); e `ESCOPOS_HISTORICO` não existe no backend, vive no frontend em `Chatter.tsx:39-51`.

Verificação: host local (工作tree git limpo antes e depois). Container NÃO foi checado — se o container espelha o branch `main`, os números valem; não confirmei isso.

## 1. Inventário de Telas

| Rota (App.tsx) | Componente principal | Tipo | Linhas | FormShell | Pipeline | Chatter |
|---|---|---|---|---|---|---|
| `/nfe-entrada` (:181) | `pages/NFeEntrada.tsx` — lista **Entrada Própria** (não é fornecedor importado) | Página dedicada + 2 drawers (`NFeEntradaDetalheDrawer` :709, `NFeEntradaRevisaoDrawer` :715) | 720 | Não (PageHeader :275) | Não | Não |
| `/nfe-entrada-historica-importada` (:187) | `pages/NFeHistoricaEntradaImportada.tsx` — NF-e de fornecedor importada (a tela central do redesenho) | Página dedicada | 629 | Não (PageHeader :243) | Não | Não |
| `/nfe-entrada/:id/conferencia` (:188) | `pages/NFeEntradaConferencia.tsx` (11 l., wrapper) → `components/fiscal/NFeEntradaConferenciaPanel.tsx` | Página dedicada (FormShell) OU embutida em sheet (`embedded=true`) | 11 + 1943 | **Sim** (painel :5, :1935) | **Sim** (:1938, `somenteLeitura: true`) | Não |
| `/cte-entrada` (:190) | `pages/CTeEntrada.tsx` — lista `CTeHistoricoImportado` via serializer operacional | Página dedicada + `CTeHistoricoDetalheModal` (:159) | 169 | Não (PageHeader :46) | Não | Não |
| `/cte-historico-importado` (:191) | `pages/CTeHistoricoImportado.tsx` | Página dedicada + `CTeHistoricoDetalheModal` (:665) | 683 | Não (PageHeader :307) | Não | Não |
| `/central-dfe` (:185) | `pages/CentralDfe.tsx` | Página + Modal CT-e (:1416) + Sheet `CentralDfeWorkspaceSheet` (:1424) que embute o painel de conferência | 1461 + 507 | Não na página; painel embutido roda `embedded` (sem shell) | idem | Não |

Adjacentes fora do escopo de entrada: `/nfe-historica-importada` (saída de terceiros), `/nfe-saida`, `/nfe-sefaz`, `/visao-gerencial-nfe-historica` (todas App.tsx:182-189).

A trava da Sprint 3.18-4 está documentada em `pages/NFeEntrada.listaSemShell.test.tsx:10-19`: por decisão do PO, `/nfe-entrada` permanece com PageHeader (FormShell não encaminha `searchValue`/`onSearch`; pipeline exige `currentKey` único; Chatter com `entityId={null}` não faz sentido em listagem).

## 2. Componentes Compartilhados

| Componente | Caminho (linhas) | Consumidores | Testes | Migrado (padrão Odoo)? |
|---|---|---|---|---|
| `NFeEntradaConferenciaPanel` | `components/fiscal/` (1943) | `pages/NFeEntradaConferencia.tsx`, `CentralDfeWorkspaceSheet.tsx:15` | `NFeEntradaConferencia.formShell.test.tsx`, `nfeEntradaReaberturaAcoes.test.tsx` (4 casos no total) | Sim (FormShell+Pipeline somenteLeitura); `embedded=true` volta ao `<div>` cru (painel :1929) |
| `NFeEntradaDetalheDrawer` | `components/fiscal/` (174) | só `pages/NFeEntrada.tsx:9` | sem teste direto (só `vi.mock` em `nfeEntrada4014.test.tsx`) | Não |
| `FornecedorEntradaAcoes` | `components/fiscal/` (223) | `CTeHistoricoDetalheModal`, `NFeEntradaConferenciaPanel:7` | `nfeEntrada40152.test.tsx` (3 casos) | Parcial (2 Modais próprios :148,:205) |
| `NFeEntradaFinanceiroAcoes` | `components/fiscal/` (106) | `NFeEntradaConferenciaPanel:8`, `CentralDfeWorkspaceSheet:17` | `nfeEntrada40144.test.tsx` | Sim (navega p/ `/financeiro/contas-pagar?titulo=` :36) |
| `GerarContasPagarNfeEntradaModal` | `components/fiscal/` (435) | painel :6, sheet :18 | sem teste próprio | Não |
| `EquivalenciaEntradaEditor` | `components/fiscal/` (776) | só painel :75 | sem teste direto | Não |
| `NFeEntradaReabrirModal` | `components/fiscal/` (245) | `NFeHistoricaEntradaImportada.tsx:28`, painel | `nfeEntradaReabertura.test.tsx` (5) | Não |
| `NFeEntradaRevisaoDrawer` | `components/fiscal/` (261) | `pages/NFeEntrada.tsx:715` | `nfeEntradaRevisaoDrawer.test.tsx` (4) | Não |
| `NFeGerarDevolucaoCompraModal` | `components/fiscal/` (223) | só painel :10 | **zero testes** | Não |
| `CTeHistoricoDetalheModal` | `components/fiscal/` (706) | `CTeEntrada:159`, `CTeHistoricoImportado:665`, `CentralDfe:1416` | indireto (`dfeOrganizacao401022.test.tsx`) | Não |
| Importação XML | não existe componente dedicado — inline em `NFeEntrada.tsx:49,408-418`, `NFeHistoricaEntradaImportada.tsx:211`, `CTeHistoricoImportado.tsx:270`; diagnóstico `utils/nfeXmlImportDiagnostico.ts` (231) | — | — | Não (candidato a modal compartilhado no redesenho) |
| `StatusBadge` | `components/nexus/StatusBadge.tsx` (28) + `design-system/tokens.ts:31-149` (STATUS_MAP) | todas as telas de entrada | `modeloOperacional4010.test.tsx` (tangencial) | — |
| Shell: `FormShell` | `components/layout/` (217) | painel de conferência + cadastros (Cliente/Fornecedor/Produto/Família) + `CotacaoFornecedorDetalhe` | `FormShell.test.tsx` | — |
| Shell: `StatusPipeline` | `components/layout/` (113) | só dentro de FormShell :5 | helpers `lib/statusPipelineHelpers.ts` | — |
| Shell: `Chatter` | `components/layout/` (500) | 6 páginas (cadastros, produtos, família, cotação) — **zero em tela de entrada** | `Chatter.test.tsx` | — |

## 3. Fluxos Cruzados

- **NF-e Entrada ↔ CT-e**: lado NF-e = campo manual `cte_id` (`pages/NFeEntrada.tsx:67` → `services/api/fiscal.ts:77-93` → `nf-entradas/`); lado CT-e = `chaves_nfe_vinculadas` JSON (`models.py:1537`, resolvido em `cte_historico_conferencia.py:72-82,142`), exibido em `CTeHistoricoDetalheModal`. FK `NFeEntrada.cte` (`models.py:114-120`) é preenchida só por PATCH; **não há endpoint de vínculo automático nem modal dedicado de vínculo** (confirmado por grep; não encontrado).
- **Conferência ↔ Pedido de Compra**: comparação `conferencia_pedido.py:183` (`build_snapshot_pedido`); baixa real via `POST …/conferencia/baixar-pedido-compra` (`views.py:3560` → `pedido_compra_baixa.py:86`, `select_for_update :146`). UI: dentro da página de conferência (FormShell), sem página própria.
- **Conferência ↔ Estoque/Kardex**: `preparar-estoque` (`views.py:3344`, split por corrida) e `aplicar-estoque` (`views.py:3468` → `aplicacao_estoque_conferencia.py:488`; `EstoqueBarra` origem `CONFERENCIA_NFE_ENTRADA` `models.py:1249`). UI na página de conferência. **Elo direto entrada→Kardex não encontrado** — Kardex é página solta (`/estoque/kardex`, App.tsx:199).
- **Entrada ↔ Financeiro (contas a pagar)**: NF-e `financeiro/preview-contas-pagar` + `gerar-contas-pagar` (`views.py:3636,:3648` → `nfe_entrada_financeiro.py:185-187`, `OrigemTipo.NFE_ENTRADA`); CT-e idem (`views.py:3949,:3984` → `cte_financeiro.py:458`, frete separado de imposto `:553`) + rateio `frete/sugerir-rateio|salvar-rateio` (`views.py:3915,:3924`). UI: `GerarContasPagarNfeEntradaModal` (modal) e, no CT-e, dentro do `CTeHistoricoDetalheModal`.
- **Entrada ↔ Fiscal**: regras de entrada carregadas no contexto da conferência (`views.py:3238-3244` → `regras_fiscais/entrada_fiscal.py:177`); apurações `resumo-fiscal-entrada`/`apuracao-mensal|trimestral-entrada` (`views.py:2906,:2928,:2940`). **DIFAL em entrada: não existe** — `difal_aplicavel` só em `RegraFiscalSaida` (`regras_fiscais/models.py:437`); grep `difal` em todos os `*entrada*.py` sem match.
- **Devolução**: `conferencia/gerar-saida-devolucao-compra` (`views.py:3150` → `nfe_saida_from_entrada_devolucao.py`), UI `NFeGerarDevolucaoCompraModal`; efeitos pós-autorização SEFAZ em `nfe_entrada_devolucao_efeitos.py` (estooque :77, financeiro :146, estorno pedido :261, chamado por `aplicar_resultado.py:43`); `ItemDevolucaoCompra` amarra item de conferência (`models.py:725`). Reabertura com trilha imutável `NFeEntradaConferenciaReaberturaEvento` (`models.py:1077`, save/delete bloqueados :1110-1116).
- **Entrada ↔ Venda**: `AlocacaoAtendimentoViewSet` (`views.py:4798`) com `opcoes/nfe-entrada-importada` :4880, `opcoes/cte-importado-conferido` :4892, `alocar-entrada-venda` :4931; UI `AlocarEntradaParaVendaBlock` (teste `alocacaoEntradaVendaFase1.test.tsx`).
- **SEFAZ/Central DFe**: captura `dfe_recebidos/capturar/` (`api_urls.py:263`), manifestação :267-301, armazenamento XML `central-dfe/<pk>/armazenar-xml-nfe|cte` :252-261.

Auditoria/chatter por fluxo: **nenhum** desses fluxos grava `RegistroAuditoria` — as trilhas são campos próprios (`conferido_por`, `estoque_aplicado_por`, `rateado_por`, `reabertura_evento`, `conversao_estoque_auditoria`).

## 4. Backend (API)

| Entidade | ViewSet (views.py) | URL (`apps/api_urls.py`) | Actions principais | Serializers | Auditoria |
|---|---|---|---|---|---|
| `NFeEntrada` (entrada própria) | `NFeEntradaViewSet` :150, **ModelViewSet** (CRUD completo, destroy :399) | `nf-entradas/` :176 | consultar-situacao-sefaz :307, cancelar :339, inutilizar :211, aplicar-regras-devolucao :665, emitir-homologacao :685 / producao :745, reservar-numeracao :607, + ~15 de XML/DANFE | `NFeEntradaSerializer` (serializers.py:401), List :329 | Em `MODELOS_AUDITADOS` (`escopo.py:21`) e `ESCOPOS_HISTORICO` (`Chatter.tsx:50`); `registrar_nfe_entrada` só em CREATE :619 / UPDATE :656 — **DELETE, cancelar, inutilizar, emitir, reservar não auditam** |
| `NFeEntradaHistoricaImportada` + `NFeEntradaConferencia` | :2818, **ReadOnly** — toda escrita é `@action` | `nf-entradas-historicas-importadas/` :186 | importar-xml :2952, conferencia GET/POST :3130, reabrir :3296, aplicar-estoque :3468, baixar-pedido-compra :3560, fornecedor/* :3582-3611, financeiro/* :3636-3692, gerar-saida-devolucao-compra :3150, apurações :2906-2940 | Histórica :1478/:1598; `NFeEntradaConferenciaSerializer` :2161; equivalência/vínculo/contas :1736,:3592,:3614,:3653 | **Fora de `MODELOS_AUDITADOS` e de `ESCOPOS_HISTORICO`; zero `registrar_*` em toda a cadeia de conferência** |
| `CTeEntrada` (nativo) | :3709, **ReadOnly**; serializer real é `CTeEntradaOperacionalSerializer` :2678 que lista `CTeHistoricoImportado` (`cte_historico_conferencia.py:54`) | `cte-entradas/` :190 | nenhuma escrita | `CTeEntradaSerializer` importado em views.py:120 e **nunca usado** | Fora dos escopos (exclusão documentada em `escopo.py:14-15`); campo `nfe_ids` (models.py:1479) **órfão** |
| `CTeHistoricoImportado` (CT-e de entrada real) | :3742, **ReadOnly** | `cte-historicos-importados/` :191 | conferir :3862, marcar-divergente :3873, ignorar-operacional :3889, fornecedor/* :3811-3837, frete/* :3915-3924, financeiro/* :3949-3984, importar-xml :4006, dacte :4048, gerenciais :4108-4228 | List :2845, detalhe :2977 | Fora dos escopos; trilha própria (`conferido_por` :1598, `rateado_por` :1614, `situacao_financeira_por` :1637) |

Permissões: `IsAuthenticated` nos 4 viewsets (views.py:163, :2826, :3712, :3751). Única barreira de grupo real: produção SEFAZ da `NFeEntrada` (`nfe_entrada_emissao/servico_producao.py:135-137`, grupos admin/fiscal_nfe_producao). Barreiras de conferência são de **domínio**, não de permissão (`pode_marcar_conferido_operacional`, `motivo_bloqueio_financeiro_real`, impedimentos de reabertura).

Sobre `enviado_em` citado no contexto: no disco ele pertence a `NFeSaidaEnvioEmail` (`models.py:659`), com leituras ativas em `nfe_saida_envio_email.py:317,335,396` — **não é campo órfão e não é de entrada** (priorizando o disco sobre o enunciado).

## 5. Dívidas Técnicas (priorizadas)

Alta

1. Chatter ausente em 100% das telas de entrada e `NFeEntradaHistoricaImportada`/`NFeEntradaConferencia`/`CTeHistoricoImportado` fora de `MODELOS_AUDITADOS`/`ESCOPOS_HISTORICO` — sem ele não há "documento padrão Odoo" na entrada.
2. Auditoria de escrita da conferência é zero (estoque, contas a pagar, baixa de pedido, devolução, reabertura, importação XML) apesar de serem ações com efeito financeiro/fiscal.
3. Escrita de todo o domínio de entrada concentrada em `@action` de dois `ReadOnlyModelViewSet` com ~60 actions somadas em `views.py` (arquivo >245k linhas lidas só em parte pela investigação) — inibitivo para o redesenho.
4. `NFeEntradaConferenciaPanel` = 1943 linhas em dois modos (`embedded` true/false); qualquer mudança visual tem que validar os 2 consumidores (página e sheet).
5. Permissão `IsAuthenticated` pura em ações críticas (aplicar estoque, gerar contas a pagar, reabrir, gerar devolução).

Média

6. `PageHeader` nas 4 telas de entrada fora da conferência; em `/nfe-entrada` é decisão registrada (3.18-4), mas nas outras listas não há decisão equivalente documentada.
7. Vínculo NF-e↔CT-e manual (PATCH `cte_id` + JSON `chaves_nfe_vinculadas`), sem endpoint/modal de vínculo.
8. `CTeEntrada` fantasma: modelo sem caminho de escrita, serializer morto, campo `nfe_ids` órfão — a rota `/cte-entrada` lista outro modelo.
9. Duplicações medidas: formatador de moeda em 6 lugares (`lib/numberFields.ts:30` canônico vs `conferenciaEquivalencia.ts:73`, `formatBr.ts:3`, `numberFormat.ts:31`, wrapper em `CTeEntrada.tsx:21-24`, `nfeSaidaConferencia.ts:14`), data em 4 (`dateBr.ts:3` vs `expedicaoUi.ts:33` etc.), labels de status de entrada em 2 (`nfeEntradaOperacionalLabels.ts:16` vs `nfeEntradaHistoricaImportadaUi.ts:63`).
10. Importação XML inline em 3 telas sem componente compartilhado.
11. `registrar_nfe_entrada` só em CREATE/UPDATE; DELETE/cancelar/inutilizar/emitir sem auditoria.

Baixa

12. Devolução sem testes: `aplicar_regra_devolucao.py` (365 l.), `nfe_saida_from_entrada_devolucao.py` (539 l.), `NFeGerarDevolucaoCompraModal.tsx` (223 l.) — zero casos.
13. `CentralDfeCteDetalheModal` (124 l.) e `parser.py` de captura CT-e (373 l.) sem teste direto.
14. DIFAL de entrada não existe (pode ser requirement futuro, não bug).

## 6. Testes

Estático (contagem por grep; **nenhuma suíte foi executada** neste levantamento). Referências de baseline registradas no projeto (não revalidadas aqui): vitest 27 falhas/1173, tsc `-p tsconfig.app.json` 766 erros.

Frontend (núcleo entrada, 21 arquivos / ~137 casos):

| Arquivo (`frontend/src/`) | Testes | Cobre | Nota |
|---|---|---|---|
| `pages/NFeEntrada.listaSemShell.test.tsx` | 7 | trava 3.18-4 da lista | não deve quebrar no redesenho |
| `pages/NFeEntradaConferencia.formShell.test.tsx` | 14 | FormShell do painel | única cobertura do painel 1943 l. |
| `lib/nfeEntrada4014.test.tsx` | 11 | render de `pages/NFeEntrada` | drawer mockado |
| `lib/nfeEntrada40144.test.tsx` | 14 | `NFeEntradaFinanceiroAcoes` + wizard CP | modal `GerarContasPagar` sem teste |
| `lib/nfeEntrada40152.test.tsx` | 3 | `FornecedorEntradaAcoes` | fino p/ 223 l. |
| `lib/nfeEntradaReabertura.test.tsx` / `ReaberturaAcoes` | 5 / 2 | ReabrirModal / ações no painel | |
| `lib/nfeEntradaRevisaoDrawer.test.tsx` | 4 | RevisaoDrawer | |
| `lib/dfeOrganizacao40101/40102/401021/401022` | 7/8/9/8 | cobertura indireta das listas e do modal CT-e | único caminho de teste das telas CT-e |
| `lib/nfeEntradaHistoricaImportadaUi`, `conferenciaEquivalencia`, `conferenciaNfeOperadorUi`, `nfeEntradaItensJson` | 3/4/4/4 | só helpers | página histórica sem teste próprio |
| `lib/alocacaoEntradaVendaFase1.test.tsx` | 12 | bloco entrada→venda | |
| **Sem teste direto** | — | `NFeEntradaDetalheDrawer`, `EquivalenciaEntradaEditor` (776 l.), `GerarContasPagarNfeEntradaModal` (435 l.), `NFeGerarDevolucaoCompraModal`, `NFeEntradaEmissaoPanel` (473 l.), `NFeEntradaEmitidaRevisaoFiscal` (679 l.) | lacunas do redesenho |

Backend: 47 arquivos, ~532 `def test_` em `apps/fiscal/tests/` (+ `regras_fiscais/test_entrada_fiscal.py` 70, `comercial/test_alocacao_entrada_venda_fase1.py` 27+4, `qualidade/test_cf_rastreabilidade_conferencia.py` 9). Cobrem bem conferência/estoque/equivalência (ex.: `test_conferencia_preparar_estoque.py` 18, `test_nfe_entrada_devolucao_efeitos.py` 20, `test_cte_historico_conferencia_401022.py` 19); lacunas em devolução (item 12) e parser CT-e.

## 7. Recomendações para Redesenho

Ordem sugerida (cada etapa com diff + validação do PO, no workflow habitual):

1. **Base visual das listas** — `NFeHistoricaEntradaImportada` e `CTeHistoricoImportado` primeiro: são as duas telas de entrada de terceiros e hoje são PageHeader puro. Decidir explicitamente se a trava da 3.18-4 (lista sem FormShell) se aplica a elas também, estendendo `listaSemShell` — assim o padrão fica registrado por teste, não por conversa.
2. **Chatter + auditoria antes do formulário novo** — adicionar `nfeentradahistoricainportada`/conferência e `ctehistoricoimportado` a `MODELOS_AUDITADOS` + `ESCOPOS_HISTORICO` e plugar `<Chatter>` na página de conferência. Aceite: ações críticas (aplicar estoque, gerar CP, reabrir, devolução) aparecem no histórico. Sem isso, o redesenho da NF-e Entrada ficaria visualmente padrão Odoo mas sem o rail funcional.
3. **Dividir o `NFeEntradaConferenciaPanel`** — extrair blocos (equivalência, estoque, financeiro, devolução, reabertura) mantendo o contrato `embedded` para `CentralDfeWorkspaceSheet`; requisito: os 4+14 casos atuais de teste permanecem verdes, com novos casos por bloco extraído.
4. **Telas CT-e em página dedicada** — hoje o detalhe do CT-e vive num modal de 706 linhas repetido em 3 páginas; migrar para rota própria com FormShell alinha CT-e ao padrão da conferência NF-e e elimina o modal triplicado.
5. **Unificar importação XML** em componente compartilhado (3 chamadas inline hoje) com o diagnóstico existente `nfeXmlImportDiagnostico.ts`.
6. **Saneamento do `CTeEntrada` fantasma** — decidir com o PO: remover modelo/serializer órfãos ou dar caminho de escrita real; a rota `/cte-entrada` deveria refletir isso.

Dependências: 2 depende de 1 (o container do Chatter nasce da decisão de layout); 4 pode correr em paralelo com 3. Critério de aceite geral: tsc limpo no gate real (`-p tsconfig.app.json`, baseline 766), vitest sem regressão sobre a lista de falhas conhecida, testes-trava (`listaSemShell`, `formShell`) atualizados por decisão explícita — nunca quebrados de passagem.

## Incertezas Declaradas

- Container não verificado (só o host); se a base implantada divergir do `main` local, os números podem diferir.
- `views.py`/`serializers.py` do backend têm centenas de milhares de linhas; actions listadas foram conferidas nas classes relevantes, mas funções individuais do pacote `nfe_entrada_emissao/` não foram lidas uma a uma (a ausência de auditoria se apoia em grep global de `registrar_nfe_entrada(`).
- Contagens de testes são por grep de `it(`/`def test_`; suítes não foram executadas.
- Não encontrei rota/endpoint próprio de "vínculo NF-e↔CT-e" nem link direto entrada→Kardex — tratado como inexistente, não como omitido.
- `NFeEntradaAgrupamentoConferencia` (models.py:2085) não parece exposto por endpoint próprio; não confirmei cada ponto de uso.
