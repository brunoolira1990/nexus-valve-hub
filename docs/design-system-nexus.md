# Design System Nexus — ERP 4.0.9

Base visual reutilizável do Nexus ERP. Objetivo: consistência entre módulos **sem alterar regras de negócio**.

## Princípios

1. **Confiável antes de chamativo** — ERP moderno, não landing page.
2. **Reaproveitar stack existente** — Tailwind, shadcn/Radix, `lucide-react`, `sonner`, classes `erp-*` legadas.
3. **Migrar incrementalmente** — telas piloto primeiro; demais módulos na sequência.
4. **Dark mode preparado** — tokens em CSS variables (`:root`); tema escuro em fase futura.

## Tokens visuais

Definidos em `frontend/src/index.css` (`:root`) e mapeados no Tailwind (`tailwind.config.ts`).

| Categoria | Exemplos |
|-----------|----------|
| Cores | `--primary`, `--primary-hover`, `--primary-soft`, `--success`, `--warning`, `--danger`, `--info`, `--surface`, `--surface-muted` |
| Status | `--status-rascunho`, `--status-conferencia`, `--status-autorizada`, etc. |
| Tipografia | classes `.nexus-heading-xl/lg/md`, `.nexus-body`, `.nexus-caption`, `.nexus-label`, `.nexus-numeric` |
| Espaçamento | `--page-padding`, `--card-padding`, `--section-gap`, `--form-gap`, `--table-row-py` |
| Sombra/radius | `--shadow-card`, `--shadow-modal`, `--radius-sm/md/lg` |

Mapeamento semântico de status: `frontend/src/design-system/tokens.ts` (`resolveStatusToken`, `StatusBadge`).

## Componentes

Pasta: `frontend/src/components/nexus/`

| Componente | Uso |
|------------|-----|
| `PageContainer` | Largura/padding consistente no `MainLayout` |
| `PageHeader` | Título, descrição, breadcrumbs, ações, busca |
| `NexusButton` | Re-export do `Button` shadcn + variantes `success`/`warning` + `loading` |
| `NexusCard` | Cards padrão, KPI, alerta, preparação, clicável |
| `Badge` / `StatusBadge` | Status operacionais (NF-e, comercial, geral) |
| `AtendimentoOperacionalBadge` / `Resumo` / `Inline` | Badges de atendimento operacional 4.0.11 (PV/FAT/NF-e) |
| `AlocacaoAtendimentoGerenciarPanel` / `GerenciarSection` | CRUD intenção operacional 4.0.12 (lista, modal, alertas de segurança) |
| `AlocacaoAtendimentoVinculosForm` + `AlocacaoVinculosLinha` | Autocompletes DF-e/compra 4.0.13 (`AsyncAutocomplete`) |
| `ClienteComercialField` / `ProdutoComercialField` | Autocomplete comercial (cadastro rápido **suspenso** na 4.0.13.6.1) |
| `FornecedorPedidoCompraField` / `FornecedorOpcaoField` | Cadastro rápido fornecedor (PC, Alocação) |
| `AtendimentoOperacionalEditModal` + página **Atendimentos Operacionais** | Listagem consolidada 4.0.13.1 (`DataTable`, KPIs clicáveis, filtros autocomplete, `EmptyState`) |

**Notas BI (4.0.8.3):** `BIChartCard` / `BIStatusChart` exigem wrapper com altura definida (`min-h-[280px] h-[320px]`). `BIKpiHeroCard` não deve truncar o valor principal (`break-words`, padding à direita quando há link). Erros 401 → `BIErrorState` com mensagem de sessão; 403 → `BIAccessDenied`.
| `DataTableShell` / `DataTable` | Listagens com hover e cabeçalho padronizado |
| `FormField` / `FormSection` | Labels, helper, erro |
| `SearchInput`, `TextInput`, … | Inputs base (`erp-input` compatível) |
| `LoadingSpinner`, `Skeleton*` | Loading e placeholders |
| `EmptyState`, `ErrorState` | Estados vazio/erro com ação útil |

**Legado:** classes `erp-btn`, `erp-card`, `erp-table`, `erp-badge` permanecem válidas. Preferir componentes Nexus em código novo.

## Botões

Variantes: `default` (primary), `secondary`, `outline`, `ghost`, `destructive`, `success`, `warning`, `link`.

Tamanhos: `sm`, `default`, `lg`, `icon`. Prop `loading` exibe spinner e desabilita.

## Badges / status

- Homologação NF-e: anel tracejado (`StatusBadge` com `homologacao: true`).
- **DF-e 4.0.10.1:** tokens `base_importada`, `fora_apuracao`, `sem_valor_fiscal`, `sem_efeito_operacional_automatico`, `apura`, `alimenta_precificacao`, `xml_importado`, `operacional`, `producao` em `tokens.ts`.
- **DF-e 4.0.10.2:** tokens `conferida`, `preparada`, `divergente`, `importada`; componente `DfeClassificacaoBadges` para listagens da base importada.
- **DF-e 4.0.10.2.2 (CT-e):** tokens `conferido`, `ignorado`, `processado`, `sem_financeiro_automatico`, `sem_expedicao_automatica`; badges na Base CT-e Importada e CT-e Entrada operacional.
- **DF-e 4.0.10.2.1:** `DfeClassificacaoBadges` também em Base NF-e Saída Importada e Base CT-e Importada; telas operacionais usam link “Ir para Base … Importada” (sem importador duplicado).
- Produção vs homologação visualmente distintos.
- Status comercial: Aberto, Aprovado, Faturado, Parcialmente faturado, `pendente_faturamento` (modal PV 4.0.13.2).
- **Modal Pedido de Venda 4.0.13.2:** `pedidoVendaModalUi.ts` mapeia faturamento/NF-e para `StatusBadge` (`homologacao`, `autorizada_homologacao`, `sem_valor_fiscal`, `fora_apuracao`, `producao`, `apura`); enums técnicos (`GERADO_NFE`, `AUTORIZADA_HOMOLOGACAO`) só em tooltip/área técnica.
- **4.0.13.2.1:** `formatBr.ts` (modal); PDF comercial sem NF-e (`pedido_venda_pdf.py`); helpers fiscais em `pedido_venda_apresentacao.py` usados no ERP/modal, não no PDF ao cliente.
- **4.0.13.3:** tabela compacta «Duplicatas da NF-e» na aba NF-e / Fiscal da modal PV (`numero`, `vencimento_formatado`, `valor_formatado`); texto auxiliar de que não gera contas a receber; DANFE mantém bloco «Fatura / duplicata».

## Tabelas

- `DataTableShell` = card + scroll horizontal.
- `DataTable` = `nexus-table` + compat `erp-table`.
- Paginação: manter `PaginationControls` + `usePaginatedList` (sem paginação client-side fake).

## Modais e tabs

- `Modal` existente: sombra `nexus-modal-shadow`; header/footer fixos preservados.
- NF-e conferência: **não redesenhada** nesta fase.
- Tabs shadcn em `components/ui/tabs.tsx` — usar em novas telas.

### Autocomplete com cadastro rápido (4.0.13.6)

Padrão replicado da transportadora/NF-e e fornecedor no PC:

- `AsyncAutocomplete` + `renderListFooter` com botão **«+ Cadastrar novo …»** (borda tracejada, fundo `primary/5`).
- Link secundário abaixo do campo com a mesma ação.
- Modal compacto (`Modal` size `md`): campos mínimos, consulta CNPJ/CEP quando aplicável, footer «Cancelar» / «Salvar e usar».
- Após save: seleção automática; formulário pai não perde estado.
- Erro de CNPJ duplicado: mensagem amigável da API.

### Campos read-only em documentos faturados (4.0.13.6)

- Pedido faturado/cancelado: itens somente leitura; aviso `MSG_PEDIDO_FATURADO_ITENS` na aba Itens.
- Quantidade: input numérico inline na grade quando `itemPedidoQuantidadeEditavel`; texto formatado quando bloqueado.
- Item parcialmente faturado: alerta âmbar com quantidade mínima.

### PDF / DANFE de conferência (4.0.13.5.3 / 4.0.13.6.13A)

- Renderizador oficial: **BrazilFiscalReport (BFR)** — badge «Renderer oficial BFR» na conferência NF-e.
- Layout MOC §3.8.1 gerado pelo BFR (`DanfeNexus` + marca d'água conferência).
- Fatura/Duplicata: seção entre destinatário e cálculo do imposto; tabela Nº / Vencimento / Valor.
- Marca d'água: «DANFE DE CONFERÊNCIA — SEM VALOR FISCAL».
- Erro BFR: mensagem «DANFE oficial não gerado. BFR falhou e o fallback HTML está bloqueado.»; aviso «Fallback HTML bloqueado» — **não** exibir PDF alternativo como oficial.
- Modo diagnóstico HTML (se habilitado): botão separado «DANFE diagnóstico — não usar», desabilitado por padrão (`DANFE_ALLOW_HTML_DIAGNOSTIC=false`).
- PDF comercial do Pedido de Venda permanece sem dados fiscais/NF-e (ReportLab).

## Toasts

`sonner` montado em `App.tsx` (`Toaster`). Uso: `import { toast } from 'sonner'`.

## Telas piloto migradas (4.0.9)

| Tela | Alterações |
|------|------------|
| Dashboard / BI | `BIPageLayout` com tipografia Nexus |
| Produtos | `PageHeader` com descrição |
| NF-e Saída | `PageHeader`; listagem compacta 4.0.13.4.1; drawer de detalhe |
| Empresas | `PageHeader` com descrição |
| Clientes | `PageHeader`, `DataTableShell`, empty com ação |
| Pedidos de Venda | `PageHeader`, `DataTable`, `StatusBadge`, empty com ação |

### Migradas na 4.0.9.1

| Tela | Alterações |
|------|------------|
| Fornecedores | `PageHeader`, colunas cidade/status, `DataTable`, `StatusBadge`, `TableSkeleton` |
| Transportadoras | Idem + placa; autocomplete `getAll` preservado |
| Propostas | `PageHeader`, `FilterBar`, `StatusBadge`, `DataTable`, empty com ação |
| Pedidos de Compra | `PageHeader`, `StatusBadge`, `DataTable`, empty com ação |
| NF-e Entrada | `PageHeader`, chave resumida, `DataTable`; modal intacto |
| Histórico XML Entrada | `NexusCard` import, filtros, `DataTable`, `StatusBadge`; XML só no detalhe |

### Migradas na 4.0.9.2

| Tela | Alterações |
|------|------------|
| Colaboradores | `PageHeader`, filtros em `NexusCard`, `DataTable`, `StatusBadge`, telefone, `TableSkeleton` |
| Corridas / Lotes | `PageHeader`, `DataTable`, empty com ação, `TableSkeleton` |
| Certificados de Qualidade | `PageHeader`, `DataTable`, `StatusBadge` + rastreabilidade legada |
| Certificados de Fornecedor | `PageHeader`, `DataTable`, `StatusBadge`, `TableSkeleton` |

### Migradas na 4.0.9.3

| Tela | Alterações |
|------|------------|
| Estoque / Saldos | `PageHeader`, filtros em `NexusCard`, `DataTable`, `StatusBadge` (situação/alertas), `TableSkeleton` |
| Atendimentos de Estoque | `PageHeader`, filtros em `NexusCard`, `DataTable`, `StatusBadge`, resumo saldos em `NexusCard` |
| CT-e Entrada | `PageHeader`, `DataTable`, `TableSkeleton`, empty com ação |
| Histórico XML CT-e | `PageHeader`, import/filtros em `NexusCard`, chave resumida, `StatusBadge`, `DataTable`; XML completo só no modal |
| Regras Fiscais | `PageHeader` com descrição; aba legada com `DataTable`/`StatusBadge`; cenários entrada/saída intactos |

## Próximos módulos a migrar

1. Formulários longos (cadastros) com `FormField` / `FormSection`
2. Cenários fiscais entrada/saída (listagens internas)
3. NF-e Saída modal conferência (visual parcial)
4. Demais listagens do menu lateral

## Regras de uso

- Não alterar fluxos fiscais sensíveis só por estética.
- Botão destrutivo sempre `destructive`.
- Empty state com ação quando houver permissão de criar.
- Erros: mensagem amigável; sem stack trace.
- Não adicionar biblioteca pesada sem necessidade (sem framer-motion nesta fase).

### NF-e Saída — listagem compacta (ERP 4.0.13.4.1)

| Padrão | Uso |
|--------|-----|
| Colunas | NF-e (título + subtítulo FAT/PV), Cliente, Emissão, Fiscal, Atendimento, Valor, Ações |
| Badge fiscal | **Um** badge principal (`listagem_resumo.fiscal_resumo.badge`); `cStat` e apuração no **subtexto** — não repetir Homologação / Sem valor fiscal / Fora da apuração em badges separados na linha |
| Atendimento | Máx. 2 badges (`label` + `variant`) + `+N` ocultos; vazio → «Atendimento não definido» |
| Valor/data | `formatCurrencyBRL` / `formatDateBr` — nunca `toFixed(2)` cru |
| Drawer | `formatStatusNfe` / `formatAmbienteNfe` — sem enums crus na UI principal |
| Detalhe | Drawer lateral `NFeSaidaDetalheDrawer` — identidade fiscal, comercial, duplicatas, atendimento, Reforma Tributária, ações DANFE/XML |
| Reforma Tributária | `NFeReformaTributariaResumo` — estados de preparação/pesquisa; sem valores falsos; **não** no PDF comercial do Pedido |
| Reforma NF-e conferência (4.0.13.6.6) | Aba Reforma: base/alíquota/valor CBS e IBS UF; badges `OK` / `Atenção` / `Sem cálculo`; `PercentInput` na regra fiscal; `formatMoneyBRL` / `formatPercentBR` |
| DANFE conferência layout (4.0.13.6.7) | Grade `.dup-grid` para duplicatas; `.lbl-wrap` / `.moc-imp-lbl-wrap` para rótulos fiscais longos; variáveis CSS `--moc-fatura-h`, `--moc-extra-fatura` |
| Transporte NF-e conferência (4.0.13.6.10) | Aviso inline «alterações não salvas»; botões **Salvar alterações** / **Salvar e validar** / **Validar dados salvos**; `AlertDialog` ao escolher modalidade 9 com dados preenchidos; mensagens inline de inconsistência modFrete 9 + transportadora/volumes (sem `alert()`) |
| Performance conferência NF-e (4.0.13.6.12) | Loading por ação («Carregando conferência…», «Salvando alterações…», «Validando dados fiscais…»); botões desabilitados durante processamento; prevenção de clique duplo; mensagem na aba Validação quando checklist não foi carregado na abertura |
| Higienização XML transmissão (4.0.13.6.13) | Seção «Higienização XML de transmissão» na aba Validação; badges preview vs transmissão; campos confirmáveis `indFinal`/`indPres` na aba Resumo |
| Equivalência/composição NF-e entrada (4.0.13.7) | Cards «Possível equivalência composta»; badges confiança alta/média/baixa; badge montagem simples/roscada; aviso «não movimenta estoque automaticamente» |
| Base IBS/CBS Reforma (4.0.13.6.11) | Bloco de fórmula fiscal na aba Reforma; badge **Regra pendente de confirmação** / **Base oficial confirmada**; exibição de deduções (ICMS, PIS, COFINS) e base IBS/CBS auditável |

### Checklist fiscal pré-homologação (ERP 4.0.13.5)

| Padrão | Uso |
|--------|-----|
| Ação | Botão «Validar» / «Validar pré-homologação» na listagem NF-e Saída e no drawer |
| Modal | `NFeChecklistHomologacaoModal` — `size="xl"`, cabeçalho/rodapé fixos, resumo com contadores, bloqueios/alertas no topo, seções colapsáveis por `secao`; badge no drawer após validar |
| Resultado | `aprovado` → «Pronto para novo teste de homologação»; `bloqueado` → lista de pendências; **não emite NF-e** |

### Exclusão com vínculo (ERP 4.0.13.5.2)

| Padrão | Uso |
|--------|-----|
| API | HTTP **409** com `detail` em português («Este produto não pode ser excluído porque está vinculado ao pedido PV-…») |
| UI | `apiErrorMessage` no `alert` após falha de DELETE — **não** mensagem genérica silenciosa |
| Confirmação | Diálogo explícito antes de excluir produto, cliente ou pedido de venda |

## Testes

`frontend/src/lib/designSystem409.test.tsx` — shell, PageHeader, Button, Badge, Card, states, Dashboard.

`frontend/src/lib/modeloOperacional4010.test.tsx` — tokens operacionais (entrada pendente/conciliada, retirada fornecedor, entrega direta).

`frontend/src/lib/atendimentoOperacional4011.test.tsx` — componentes de visibilidade operacional (badges, resumo, inline; separação fiscal vs operacional).

`frontend/src/lib/dashboardBiBugfix4083.test.tsx` — 401/403, KPI Hero, Recharts, gráficos vazios.

Documentação: `docs/modelo-operacional-nexus.md` (seção 18 — visibilidade 4.0.11)

```bash
docker compose exec -T frontend npm test -- --run src/lib/designSystem409.test.tsx src/lib/designSystem4091.test.tsx src/lib/designSystem4092.test.tsx src/lib/designSystem4093.test.tsx src/lib/modeloOperacional4010.test.tsx src/lib/atendimentoOperacional4011.test.tsx src/lib/dashboardBiBugfix4083.test.tsx
docker compose exec -T frontend npm run build
```

## Campos comerciais padronizados (ERP 4.0.13.6.2)

- Linha de item em `Pedido de Venda`, `Proposta` e `Pedido de Compra` é resumo; edição fica no painel expandido/modal.
- Componentes padrão:
  - `QuantityInput` / `QuantityDisplay`
  - `MoneyInput` / `MoneyDisplay`
  - `PercentInput` / `PercentDisplay`
  - `DiscountInput`
  - `UnitSelect`
  - `ReadonlyCalculatedField`
- Helpers padrão: `parseMoneyInputToDecimal()`, `formatMoneyBRL()`, `parseQuantityInputToDecimal()`, `formatQuantityBR()`, `parsePercentInputToDecimal()`, `formatPercentBR()`, `normalizeDecimalForApi()`.
- Payload comercial deve enviar decimal técnico (`"250.00"`, `"2.000"`), sem máscara BRL, sem unidade embutida e sem objeto cru.

### Aplicação por módulo (ERP 4.0.13.6.3)

- `Pedido de Venda`: linha do item somente resumo; edição no painel expandido.
- `Proposta`: campos de quantidade/preço/desconto/unidade padronizados com componentes comerciais base.
- `Pedido de Compra`: campos de quantidade/preço/desconto/unidade padronizados com os mesmos componentes, mantendo total de item e total de pedido somente calculados.

### Alerta de endereço fiscal inconsistente (ERP 4.0.13.6.4)

- Banner `border-amber-500/35 bg-amber-500/10` nas abas **Endereço** e **NF-e / DANFE** do cadastro de cliente.
- Texto orienta correção de CEP/cidade/UF; deixa claro que o cadastro comercial pode ser salvo, mas a NF-e fica bloqueada até correção.
- Conferência NF-e / modal **Atualizar fiscal**: bloco **Contexto fiscal consultado** + pendências por item com título e detalhe (endereço vs falta de regra).

## Equivalência e composição (ERP 4.0.13.7 / 4.0.13.7.1)

Padrões para conferência NF-e entrada e cadastro de produto:

| Elemento | Uso |
|----------|-----|
| Card de sugestão | `rounded-md border border-border p-3` com resumo produto interno, itens NF-e, valores |
| Badge confiança | `erp-badge-success` (alta), `erp-badge-warning` (média), `erp-badge-danger` (baixa) |
| Badge montagem simples | `erp-badge-outline` + label «Montagem simples» |
| Badge montagem roscada | `erp-badge-outline` + label «Montagem roscada» |
| Badge equivalência composta | label «Itens do fornecedor agrupados» no card de sugestão |
| Aviso sem estoque | texto `text-xs text-muted-foreground` — *«Equivalência confirmada para conferência. Movimentação de estoque ou montagem real será feita em fase própria.»* |

Helpers: `frontend/src/lib/conferenciaEquivalencia.ts` — `badgeConfiancaEquivalencia`, `labelTipoEquivalencia`, `labelTipoComposicao`.

Testes: `frontend/src/lib/conferenciaEquivalencia.test.ts`.

## Financeiro operacional (ERP 4.0.14)

| Padrão | Regra |
|--------|-------|
| Status financeiro | `StatusBadge` com rótulos amigáveis (`Em aberto`, `Parcialmente recebido`, `Vencido`) — **proibido** `PARCIALMENTE_RECEBIDO` na UI |
| Cards visão geral | ERP 4.0.14.5: blocos CR/CP (hoje, vencido, 7 dias, em aberto, período), saldo previsto, alertas, créditos (`FinanceiroVisaoGeral`) |
| Filtros CR/CP | Painel recolhível: vencimento, status, origem, categoria, origem fiscal cancelada (`TituloFinanceiroFiltrosPanel`) |
| Origem cancelada | Badge âmbar «Origem cancelada» na listagem; alerta no detalhe do título |
| Listagem títulos | Colunas: vencimento, cliente/fornecedor, número, valor, saldo, status, origem; ações Ver detalhes / Baixar |
| Drawer detalhe | Dados, parcelas, baixas, histórico, origem; mensagem se título baixado exige estorno para editar |
| Baixa | Modal com data, valor, conta/caixa, forma, juros/multa/desconto/tarifa |
| Estorno / cancelamento | `MotivoAcaoDestrutivaModal` com motivo mínimo 10 caracteres |
| Mensagens | `mensagem` da API ou `apiErrorMessage`; sucesso via toast (`Recebimento registrado…`, `Baixa estornada…`) |
| Cadastro financeiro | Não exibe `Condições de pagamento`; apenas contas, formas, categorias e centros de custo |

Helpers: `frontend/src/lib/financeiroUi.ts` — `FINANCEIRO_STATUS_LABELS`, `tituloModoConfig`, `FINANCEIRO_ACTION_LABELS`.

Testes: `frontend/src/lib/financeiroUi4014.test.tsx`.

### Despesas e tributos (complemento 4.0.14)

| Padrão | Regra |
|--------|-------|
| Ações CP | Três entradas: Nova despesa, Novo tributo a pagar, Nova conta a pagar (fornecedor) |
| Modal despesa | Descrição, fornecedor opcional, categoria, competência (mês), vencimento, valor |
| Modal tributo | Tipo tributo amigável, competência, período apuração, parcelar com grade 001/002/… |
| Baixa parcelada | Select «Parcela» quando há mais de uma; saldo por parcela |
| Aviso tributo | Texto: lançamento manual — sem cálculo a partir de NF-e/apuração |

Componentes: `ContaPagarDespesaModal`, `ContaPagarTributoModal`.

## Camada operacional da interface (ERP 4.0.13.8)

| Padrão | Regra |
|--------|-------|
| `AdvancedSupportSection` | Fechado por padrão; título «Avançado / Suporte técnico»; não compete com ações principais |
| `OperationalMessage` | O que aconteceu + impacto + orientação; traduz erros técnicos via `friendlyOperationalMessage` |
| Ações NF-e rascunho | Salvar, Validar dados, Ver DANFE, Emitir NF-e, Descartar rascunho |
| Ações NF-e autorizada | Ver DANFE, Baixar XML, Cancelar NF-e, Carta de Correção |
| Badges status | Linguagem de negócio (`NF-e autorizada`, `Em conferência`) — **proibido** enum interno na UI principal |
| Produtos | «Modelo de medidas», «Como o código será formado», «Montagem roscada» (não `MONTAGEM_ROSCADA`) |
| Mensagens | Sem `ValidationError`, `payload`, `snapshot` expostos ao usuário final |

Helpers: `frontend/src/lib/operationalUi.ts` — `ACTION_LABELS`, `friendlyOperationalMessage`, status labels.

Testes: `frontend/src/lib/operationalUi401308.test.ts`.

## ERP 4.0.14.1 — Linguagem visual financeira

- Labels de formas fixas: Pix, Boleto, Transferência bancária, Dinheiro, Cartão de crédito, Cartão de débito, Cheque, Depósito bancário, Sem movimentação financeira, Outros.
- Labels de tipos de movimento: Recebimento, Pagamento, Recebimento parcial, Pagamento parcial, Abatimento por devolução, Crédito gerado, Uso de crédito, Reembolso, Estorno, Ajuste manual.
- Mensagens operacionais: crédito aplicado, abatimento por devolução, saldo reaberto por estorno.
- Histórico operacional deve apresentar ação, usuário, data e impacto em saldo.

### Conta financeira e menu lateral (ERP 4.0.14.1.1)

| Padrão | Regra |
|--------|-------|
| Campos condicionais | Modal Conta/Caixa: Banco, Agência e Conta visíveis **somente** quando Tipo = Banco; banco obrigatório neste caso |
| Labels condicionais (4.0.14.1.2) | Tipo **Banco**: «Descrição / Apelido da conta» + «Banco» (instituição); ordem Banco → Apelido → Agência → Conta. Tipo **Caixa/Carteira/Outro**: «Nome da conta/caixa» |
| Listagem contas | Coluna Nome = apelido; coluna Banco = instituição; «Não informado» se vazio; «—» para Caixa/Carteira/Outro |
| Active state menu | Rotas filhas de `/financeiro` não devem ativar «Visão geral» — apenas o item da rota atual (`isSidebarPathActive` em `sidebarNav.ts`) |

Helpers: `contaFinanceiraTipoBanco`, `labelBancoContaListagem`, `labelNomeContaFinanceira`, `validarContaFinanceiraForm` em `financeiroUi.ts`.

Testes: `frontend/src/lib/financeiroUi401411.test.tsx`, `financeiroUi401412.test.tsx`, `financeiroUi401413.test.tsx`.

### Busca de fornecedor no Financeiro (ERP 4.0.14.1.3)

| Padrão | Regra |
|--------|-------|
| `FornecedorSearchSelect` | Autocomplete sob demanda (`fornecedoresService.search`); debounce 300 ms; placeholder operacional |
| Sem resultados | «Nenhum fornecedor encontrado.» |
| Cadastro | Link «Cadastrar novo fornecedor» → `/fornecedores` (sem cadastro automático) |
| Conta a pagar | Fornecedor obrigatório; mensagem «Selecione um fornecedor.» |
| Despesa | Fornecedor opcional; helper «Informe um fornecedor se esta despesa estiver vinculada a alguém.» |

### Busca de cliente no Financeiro (ERP 4.0.14.1.4)

| Padrão | Regra |
|--------|-------|
| `ClienteSearchSelect` | Autocomplete sob demanda (`clientesService.search`); placeholder operacional CNPJ/CPF |
| Nova conta a receber | Botão/modal «Nova conta a receber» — **não** usar «Novo recebimento» para criação de título |
| Baixa | «Baixar recebimento» permanece exclusivo para baixa/entrada de dinheiro |
| Parcelamento | Checkbox «Parcelar este título» (substitui «Gerar parcelas automaticamente») |
| Cadastro | Link «Cadastrar novo cliente» → `/clientes` (sem cadastro automático) |

Testes: `financeiroUi401414.test.tsx`.

### Drawer financeiro por status (ERP 4.0.14.1.5)

| Padrão | Regra |
|--------|-------|
| Mensagens operacionais | Banner contextual por status (em aberto, parcial, quitado, cancelado, vencido) + complementos (crédito, abatimento) |
| Ações contextuais | Rodapé do drawer com baixa, editar, cancelar, estornar, crédito, abatimento e histórico conforme flags |
| Título em aberto | **Não** exibir mensagem genérica de «já baixado»; orientar baixa/edição/cancelamento |
| Título quitado | Orientar estorno para alteração sensível |
| Fechar | Sempre disponível no rodapé |

Testes: `financeiroUi401415.test.tsx`.

### Créditos e abatimentos (ERP 4.0.14.2)

| Padrão | Regra |
|--------|-------|
| `CreditoNovoModal` | Cliente ou fornecedor via busca padronizada; origem manual/devolução/ajuste |
| `AplicarCreditoModal` | A partir do título; lista créditos disponíveis da mesma contraparte |
| `AbaterDevolucaoModal` | Valor, data, motivo; sem movimentação de caixa |
| Movimentos no drawer | Tipo, valor, forma, observação; estorno contextual (uso de crédito / abatimento) |
| Mensagens | Sucesso parcial/quitado; estorno reabre saldos |

Testes: `financeiroUi40142.test.tsx`.

### Acabamento Créditos (ERP 4.0.14.2.1)

| Padrão | Regra |
|--------|-------|
| Empty state limpo | Sem créditos e sem filtro: só título, descrição e botão «Novo crédito» |
| Novo crédito | Um botão → modal de escolha Cliente / Fornecedor |
| Filtros | Visíveis apenas quando há créditos ou filtro/busca ativa |
| Drawer crédito | Ações por flags da API (`pode_editar`, `pode_excluir`, etc.) |
| Histórico financeiro | Cards com data/hora, usuário, valor em pt-BR (`FinanceiroEventoHistorico`) |
| Exclusão segura | Modal com motivo obrigatório; só manual sem movimento |

Testes: `financeiroUi401421.test.tsx`.

### Exclusão após estorno (ERP 4.0.14.2.2)

| Padrão | Regra |
|--------|-------|
| Movimento ativo vs estornado | `pode_excluir` false só com efeito financeiro ativo ou origem externa |
| Motivo de bloqueio | Aviso discreto no drawer quando exclusão indisponível |
| Histórico recolhido | Seção «Movimentos e histórico» com accordion fechado por padrão |
| Ações agrupadas | Principal / Outras ações / Ações sensíveis no rodapé |
| Título operacional | «Crédito de cliente», «Conta a receber» — ID técnico secundário |

Testes: `financeiroUi401422.test.tsx`.

### Geração financeira a partir de NF-e (ERP 4.0.14.3)

| Padrão | Regra |
|--------|-------|
| Automático (produção) | Após autorização SEFAZ: toast «Contas a receber gerado»; se já existir → «Ver contas a receber»; se falhar → aviso + «Gerar contas a receber» |
| Wizard | Título «Gerar contas a receber» — 4 etapas: origem, parcelas, classificação, confirmação (recuperação) |
| Parcelas | Grade editável (vencimento, valor, observação); soma deve bater com total (tolerância R$ 0,05) |
| Ação principal | «Gerar contas a receber» na NF-e autorizada em produção sem título; após gerar → «Ver contas a receber» |
| Homologação | Sem geração financeira automática nem manual |
| Bloqueio | NF-e não autorizada: botão desabilitado «Disponível após autorização da NF-e.» |
| Duplicidade | Mensagem «Contas a receber já foram geradas para esta NF-e.» + link para vinculados |
| Origem na listagem CR | «NF-e nº …» — sem expor content_type/object_id |
| Grupo de ações | «Ações financeiras» no rodapé da NF-e (drawer e conferência) |

Testes: `nfeSaida40143.test.tsx`, `nfeSaidaProducaoUi4015.test.tsx`.

### Geração financeira a partir de NF-e Entrada (ERP 4.0.14.4)

| Padrão | Regra |
|--------|-------|
| Wizard | Título «Gerar contas a pagar» — 4 etapas: origem, parcelas, classificação, confirmação |
| Parcelas | Grade editável (vencimento, valor, observação); soma deve bater com total (tolerância R$ 0,05) |
| Ação principal | «Gerar contas a pagar» na NF-e Entrada conferida/preparada; após gerar → «Ver contas a pagar» |
| Bloqueio | Somente bloqueio financeiro real (fornecedor, valor, cancelada, duplicidade) |
| Duplicidade | Mensagem «Contas a pagar já foram geradas para esta NF-e Entrada.» + link para vinculados |
| Origem na listagem CP | «NF-e Entrada nº …» — sem expor content_type/object_id |
| Grupo de ações | «Ações financeiras» na tela de conferência da NF-e Entrada |

Testes: `nfeEntrada40144.test.tsx`.

### Financeiro com pendências operacionais (ERP 4.0.14.4.1)

| Padrão | Regra |
|--------|-------|
| Bloqueio financeiro | Somente fornecedor, valor, cancelamento, duplicidade, XML inválido |
| Pendências operacionais | Alerta âmbar — **não desabilita** «Gerar contas a pagar» |
| Wizard | Alerta no topo + checkbox de ciência quando há pendências operacionais |
| Salvar conferência | Permite salvar com pendências; toast informa que financeiro ainda pode ser gerado |
| Texto auxiliar | «Gere o financeiro… Estoque e conferência operacional não serão alterados.» |

Testes: `nfeEntrada40144.test.tsx` (casos 401441 incluídos).

### Visão geral financeira (ERP 4.0.14.5)

| Padrão | Regra |
|--------|-------|
| Cards | Clicáveis → listagem CR/CP com filtro aplicado na URL |
| Período | Este mês (padrão), hoje, semana, próximos 7/30 dias |
| Status vencido | Calculado na UI/API quando vencimento &lt; hoje e saldo em aberto |
| Alertas | Lista com ação «Ver →»; não bloqueia operação |

Testes: `financeiro40145.test.tsx`.

### Relatórios financeiros (ERP 4.0.14.6)

| Padrão | Regra |
|--------|-------|
| Hub | Cards com título, descrição e link (`FinanceiroRelatoriosHub`) |
| Cabeçalho | Nome + descrição + voltar aos relatórios |
| Cards | `RelatorioMetricCards` — totais em moeda |
| Filtros | `RelatorioFiltrosPanel` — bloco único **Filtros** |
| Tabela | `RelatorioTitulosTable` — ações abrir/baixar |
| Empty state | Mensagem amigável sem dados no período |

Testes: `financeiroRelatorios40146.test.tsx`, `financeiroRelatorios401461.test.tsx`.

### Relatórios PDF operacionais (ERP 4.0.14.7)

| Padrão | Regra |
|--------|-------|
| Motor | `apps.relatorios` + ReportLab — **não** DANFE/BFR |
| Ação | Botão **Gerar PDF** (`RelatorioPdfActions`) — filtros atuais da URL |
| Cabeçalho PDF | Empresa, título, período, filtros aplicados, data/usuário |
| Corpo | Cards/resumo + tabela (cabeçalho repetido em quebra de página) |
| Rodapé | NEXUS APP + numeração + aviso operacional (não substitui documento fiscal/contábil) |
| Orientação | Retrato (padrão); paisagem para tabelas largas (CR/CP/categorias) |

Testes: `test_financeiro_relatorios_pdf_40147.py`, `financeiroRelatorios40147.test.tsx`.

### Relatórios financeiros — consistência (ERP 4.0.14.6.1)

| Padrão | Regra |
|--------|-------|
| Filtros | Um painel **Filtros**; principais visíveis (vencimento/período, status, origem, toggles histórico); **Mais filtros** recolhido por padrão |
| Histórico | Toggles *Incluir quitados*, *Incluir cancelados*; aviso âmbar (`RelatorioAvisoHistorico`) quando ativos |
| Sem saldo | *Incluir registros sem saldo* em relatórios por cliente/fornecedor (Mais filtros) |
| Cards CR/CP | Total em aberto, vencido, recebido/pago no período, parcial, quantidade (e tributos em CP) — excluem cancelados dos totais de aberto/vencido |
| Categoria | Colunas Original, Em aberto, Baixado, Total + texto explicativo |
| Empty state | `EMPTY_STATE_RELATORIO` por tipo de relatório |
| Ver títulos | Link para CR/CP com query herdada (`linkVerTitulosRelatorio`) |

### Preparação para produção (ERP 4.0.14.8)

| Padrão | Regra |
|--------|-------|
| Número CR/CP | Exibir `CR-AAAA-000001` / `CP-AAAA-000001` na coluna Documento; origem NF-e separada |
| Vencimento | `RelatorioTitulosTable` — nunca «—» se parcela/título tem data; aviso «Vencimento não informado.» só legado |
| Colaborador — acesso | Coluna **Acesso**: Sem acesso / Usuário ativo / Sem perfil / Usuário inativo; ações contextuais (Criar usuário, Definir perfil) |

## ERP 4.0.14.9.4.1 — Nome exibido do colaborador no Header

- Helper `getUsuarioNomeExibicao` — prioriza colaborador; `username` é login técnico, não nome principal.
- Cache do contexto invalida respostas antigas em que `nome_exibicao === username` com colaborador vinculado.
- Login limpa cache; alterações em Colaboradores recarregam o header.

### Cabeçalho global (ERP 4.0.14.9.3 / 4.0.14.9.4 / 4.0.14.9.4.1)

| Padrão | Regra |
|--------|-------|
| Layout | Empresa atual · Ambiente · Usuário ▼ · Sair · Busca (prioridade visual decrescente) |
| Busca | `GlobalSearch` — debounce, mín. 2 caracteres, dropdown agrupado, Enter abre 1º resultado |
| Empresa | `EmpresaAtualBadge` — **razão social completa** no desktop quando couber; truncamento responsivo com ellipsis; tooltip com razão social + CNPJ; **somente informativa** (sem troca) |
| Ambiente | `AmbienteBadge` — ex.: Homologação |
| Usuário | `UserMenu` — **nome humano** (`nome_exibicao`); login técnico no dropdown; Minha conta, Alterar senha |
| Nome exibido | `getUsuarioNomeExibicao` — colaborador → nome_exibicao → first+last → username (fallback); **nunca** username quando há colaborador |
| Minha conta | `/minha-conta` — blocos Dados pessoais / Acesso / Colaborador / Empresa; **Editar meus dados** (e-mail, telefone); aviso para e-mail técnico/local |

### Acesso ao sistema — Colaboradores (ERP 4.0.14.9.1)

| Padrão | Regra |
|--------|-------|
| Seções do modal | **Dados do colaborador** · **Funções internas** (texto auxiliar: não substituem perfil) · **Acesso ao sistema** |
| Badges | `Sem acesso` (neutro) · `Usuário ativo` (sucesso) · `Sem perfil` (alerta) · `Usuário inativo` (neutro) |
| Criar usuário | Modal `CriarUsuarioColaboradorModal`; e-mail + perfil obrigatórios; sugestão de perfil pelas funções internas |
| Vincular / perfil | Modais dedicados; perfil reflete grupo Django real |
| Desativar acesso | Confirmação com motivo opcional; colaborador permanece |
| Senha (criar) | Modal com Senha + Confirmar senha; texto «não será exibida novamente após salvar» |
| Senha (Admin) | Modal `RedefinirSenhaColaboradorModal`; senha atual não exibida |
| Minha conta | `/minha-conta/alterar-senha` — senha atual + nova + confirmação |
| Senha | **Nunca** exibir senha salva; campos `type=password` |
| Mensagens | E-mail duplicado, perfil ausente, acesso desativado — textos operacionais amigáveis |

| Limpeza perigosa | Dry-run obrigatório; execução exige frase `APAGAR_DADOS_TESTE` + `--backup-confirmado` |
| Produtos | Sempre listados como **preservados** no relatório de limpeza |

### Pré-produção (ERP 4.0.14.9 / 4.0.14.10)

| Padrão | Regra |
|--------|-------|
| Terminal | Prontidão e limpeza via `manage.py` — **sem botão de limpeza real na UI** nesta fase |
| Relatório | JSON em `reports/pre_producao_*.json` — sem senhas/tokens/certificados; seção `fiscal` |
| Críticos | Vermelho no terminal; bloqueiam limpeza real |
| Avisos | Âmbar; revisão antes de produção |
| Produtos | Linha explícita «Produtos preservados: N» no dry-run |

### Regras fiscais mínimas (ERP 4.0.14.10)

| Padrão | Regra |
|--------|-------|
| Checklist | Bloco informativo em `/regras-fiscais` — não cria regras automaticamente |
| Empty state | «Nenhuma regra fiscal cadastrada» + CTA Nova regra fiscal |
| Badges | Entrada/Saída na listagem legada; Ativa/Inativa nos cenários |
| Validação | CFOP, natureza da operação e CST/CSOSN obrigatórios na regra legada |
| Mensagens | «Informe o CFOP.» · «Informe a natureza da operação.» · «Informe o CST/CSOSN de ICMS.» |
| API | `GET /api/regras-fiscais/checklist-producao/` — checklist e métricas fiscais |

### Regra fiscal de entrada — aviso vs bloqueio (ERP 4.0.14.10.1)

| Padrão | Regra |
|--------|-------|
| Checklist | Dois blocos: **Pronto para venda/saída** e **Pendente para entrada fiscal** |
| Badge | **Incompleta** em regra de entrada ativa com pendência (CFOP, natureza ou CST/CSOSN) |
| Avisos | Âmbar — entrada incompleta não bloqueia produção geral |
| Bloqueio por fluxo | Ao preparar/finalizar entrada fiscal: «Cadastre regra fiscal de entrada…» |
| NF-e Entrada | Gerar Contas a Pagar continua disponível com dados financeiros válidos |

### Acesso ao colaborador (ERP 4.0.14.10.2)

| Badge | Quando |
|-------|--------|
| Sem acesso | Colaborador sem usuário |
| Acesso inativo | Usuário vinculado inativo |
| Sem perfil | Usuário ativo sem grupo (alerta) |
| Superusuário | `is_superuser=true` |
| Perfil específico | Nome do grupo (Financeiro, Fiscal, etc.) |

| Padrão | Regra |
|--------|-------|
| Bloco Acesso ao sistema | Status, login, e-mail, perfil, tipo, grupos |
| Modal Editar acesso | Admin edita perfil/e-mail/status; superusuário só para superusuário logado |
| Tooltip coluna Acesso | Login, e-mail, status, grupos, superusuário sim/não |
