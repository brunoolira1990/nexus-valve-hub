# Roadmap Nexus ERP

Documento central de evolução do projeto. Organiza o que já foi entregue, o que falta e a ordem recomendada das próximas fases.

> **Roadmap vivo:** atualizar este arquivo ao concluir cada fase (marcar checklists, ajustar status e registrar a próxima decisão).

---

## 1. Visão geral

O Nexus ERP está sendo construído por **macrofrentes**, para permitir evolução incremental com homologação fiscal e operacional antes de ligar comportamentos globais.

| # | Macrofrente | Papel |
|---|-------------|--------|
| 1 | Cadastros mestres | Base de clientes, fornecedores, produtos, empresas, transportadoras |
| 2 | CRM | Leads, oportunidades, pipeline e conversão comercial |
| 3 | Propostas | Simulação comercial, precificação e homologação fiscal |
| 4 | Pedido de venda | Compromisso comercial após proposta aprovada |
| 5 | Fiscal / NF-e entrada e saída | Classificação, validação, emissão e apuração |
| 6 | Estoque / remessas / rastreabilidade | Conferência, aplicação física, corridas e kardex |
| 7 | Qualidade | Certificados de fornecedor e de qualidade (CQ) |
| 8 | Financeiro | Contas a pagar/receber, fluxo de caixa, conciliação |
| 9 | Contábil | Plano de contas, lançamentos, DRE, SPED (futuro) |
| 10 | Relatórios / BI / auditoria | Dashboards, exportações e trilha de alterações |

### Separação fiscal já definida

| Fluxo | Responsabilidade |
|-------|------------------|
| **Entrada** | Classificação e **validação** do XML recebido (fornecedor). Regras de entrada, CFOP origem × CFOP entrada, bloqueios, elegibilidade de estoque, integração com conferência. |
| **Saída** | **Cenário fiscal** para proposta, homologação e futura emissão própria (NF-e saída). Motor com fallback na `RegraFiscal` legada até migração completa. |

Essa separação evita misturar “o que entrou” com “o que vamos emitir” e permite homologar o cenário de saída em propostas reais antes da NF-e operacional consumi-lo.

---

## 2. Checklist executivo

| Módulo | Status | Prioridade | O que já existe | O que falta | Próxima fase recomendada |
|--------|--------|------------|-----------------|-------------|-------------------------|
| Cadastros mestres | Concluído parcial | Média | Clientes, fornecedores, empresas, produtos, famílias | Contatos, endereços múltiplos, IE, regime, dados bancários refinados | Cadastros 1 — Diagnóstico |
| CRM | Não iniciado | Baixa | — | Leads, pipeline, atividades | CRM 1 |
| Propostas | Em evolução | Alta | CRUD, itens, precificação, fiscal legado/cenário, comparativo, homologação | Versionamento, aprovação, PDF, condições avançadas | Propostas 2.0 |
| Pedido de venda | Concluído parcial | Alta | Modelo, API, UI básica, conversão a partir de proposta | Status operacional, reserva, faturamento parcial, vínculos estoque/NF/financeiro | Pedido Venda 2 |
| Fiscal entrada | Em evolução | Alta | Classificação, validação XML, bloqueio, conferência, estoque | Snapshot persistido, relatórios de divergência/crédito | Fiscal Entrada 4 |
| Fiscal saída / Cenário | Em evolução | Alta | Cenário, regras, editor guiado, homologação e histórico 3.10 | NF-e consumindo cenário, DANFE/XML | NF-e Saída 1 |
| NF-e saída | Concluído parcial | Alta | Módulo operacional, modos atendimento estoque | Consumir `RegraFiscalSaida`, XML/DANFE do cenário, CC-e/cancelamento | NF-e Saída 1 |
| NF-e entrada própria | Em evolução | Alta | Importar XML entrada própria já emitida (4.0.14.x) | Emissão própria, devolução/recusa, retorno remessa, vínculo NF saída | Entrada Própria 1 |
| Remessas | Não iniciado | Média | CFOPs no catálogo auxiliar de saída | Modelo, emissão, retorno, controle pendente | Remessa 1 |
| Estoque / rastreabilidade | Em evolução | Alta | AtendimentoEstoque, aplicação física, CQ + rastreio | Kardex, estorno, relatório ponta a ponta | Estoque 3.13 |
| Qualidade | Concluído parcial | Média | CF, CQ, busca corrida, vínculo conferência | Relatório CQ, dashboard pendências | Qualidade 4 |
| Financeiro | **Base operacional (4.0.14)** | Alta | CR/CP manual, baixa, estorno | Geração a partir de NF-e (ação explícita), conciliação, DRE | Financeiro 2 |
| Contábil | Futuro | Baixa | Tela placeholder | Plano de contas, lançamentos, DRE | Contábil 1 |
| Relatórios / BI / auditoria | Concluído parcial | Média | Apuração fiscal, painéis gerenciais parciais | Dashboards unificados, auditoria de alterações | BI 1 |

**Legenda de status:** Concluído parcial · Em evolução · Não iniciado · Futuro · Precisa revisão

---

## 3. Fiscal de entrada

### Já feito

- Classificação fiscal de entrada (cenário/regras por escopo)
- CFOP origem × CFOP entrada
- Validação de XML importado
- ICMS, IPI, PIS, COFINS, FCP
- Reforma tributária preparatória
- Bloqueio fiscal (severidade informativo/alerta/bloqueio)
- Elegibilidade e efeitos para estoque
- Integração com **conferência de NF-e entrada** e **aplicação física** de estoque
- Certificados de fornecedor alinhados à conferência

### Falta

- Snapshot fiscal da entrada persistido (estado congelado pós-classificação)
- Relatório de divergências fiscais por período
- Melhorias futuras de apuração e crédito tributário

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Fiscal Entrada 4** | Snapshot fiscal da entrada |
| **Fiscal Entrada 5** | Relatórios de divergência e crédito |

### Checklist

- [x] Validação XML
- [x] Bloqueio fiscal
- [x] Efeitos para estoque
- [x] Integração conferência
- [ ] Snapshot fiscal persistido
- [ ] Relatório fiscal de entrada por período

---

## 4. Fiscal de saída

### Já feito

- `CenarioFiscalSaida` e cenário padrão
- Escopos: Geral / NCM / prefixo NCM / Produto
- `RegraFiscalSaida` com prioridade e UFs
- UI do cenário fiscal de saída
- Editor fiscal guiado (catálogos CST, modalidade, etc.)
- Busca/catálogo de **CFOP** (venda e ST)
- ICMS, IPI, PIS, COFINS, FCP, ICMS ST
- Reforma tributária guiada
- Recomendações NF-e/DANFE (cadastro informativo)
- Dedução de ICMS da base PIS/COFINS (opt-in no cenário)
- Motor de saída com **fallback** na `RegraFiscal` legada
- Comparativo **legado × cenário** (item e API)
- Cobertura/homologação **em lote** (propostas)
- Checklist de ativação global (sem ligar flag sozinho)
- **Opt-in por proposta** (`usar_cenario_fiscal_saida`)
- **Homologação assistida por proposta** (iniciar, resumo, aprovar, reprovar, voltar legado)

### Falta

- Histórico/auditoria de homologação fiscal (além do status atual na proposta)
- Ativação global controlada (`USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS`)
- NF-e saída consumindo cenário fiscal na prática
- Recomendações NF-e/DANFE virando comportamento real na emissão
- Emissão de XML/DANFE com impostos do cenário homologado

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Saída 3.10** | Histórico/auditoria de homologação fiscal |
| **Saída 4** | NF-e saída usando Cenário Fiscal de Saída |
| **Saída 4.1** | Aplicar recomendações NF-e/DANFE na emissão |
| **Saída 4.2** | Validação final antes da emissão |

### Checklist

- [x] Cenário fiscal de saída
- [x] Editor guiado
- [x] CFOP com busca
- [x] Comparativo legado × cenário
- [x] Homologação por proposta
- [x] Histórico de homologação (Fase 3.10) (trilha completa)
- [ ] NF-e saída usando cenário
- [ ] Recomendações aplicadas na emissão
- [ ] DANFE/XML usando cenário

---

## 5. Propostas

### Já feito

- CRUD de propostas e itens (produto e avulso com NCM)
- Precificação com custo carregado, margem e carga tributária de saída
- Regra fiscal **legada** por padrão
- Ativação do **cenário fiscal** por proposta (opt-in)
- Comparativo fiscal **por item** (botão “Comparar fiscal”)
- **Homologação fiscal** assistida (fluxo 3.9)
- Conversão básica para pedido de venda (quando cliente cadastrado e itens regularizados)
- Referências comerciais (frete, custo compra observado)
- **Comercial 2.2:** numeração automática, datas/status/condição padrão, UX de formulários
- **Comercial 2.2.1:** numeração `PROP/PV-AAAAMMDD-NNNN` (padrão pedido de compra); conversão gera número próprio do pedido (vínculo por `proposta_id`)
- **Comercial 2.3:** datas em dd/mm/aaaa, fonte fiscal única (Cenário de Saída) na UI, layout dos modais proposta/pedido, vencimentos claros
- **Comercial 2.3.1:** autocomplete de cliente e produto em Propostas/Pedidos (padrão Pedido de Compra, `AsyncAutocomplete` + busca API)
- **Comercial 2.3.2:** cadastro de vendedor (FK + API), autocomplete vendedor, layout cliente/unidade, produto cadastrado vs item avulso corrigido
- **Comercial/Cadastros 2.4:** modelo Colaborador (funções vendedor/comprador/fiscal/etc.), vínculo com login, Vendedor espelhado via Colaborador, layout cabeçalho e itens
- **Comercial/Cadastros 2.4.1:** tela de cadastro de Colaboradores (menu Cadastros, CRUD, funções, inativação)
- **Comercial/Cadastros 2.4.2:** vínculo Colaborador ↔ usuário/login na tela (API read-only `/api/usuarios/`, PATCH `usuario_id`, regra de unicidade entre ativos)
- **Comercial 2.5:** UX operacional do Pedido de Venda — modal em abas (Resumo, Itens, Faturamento, NF-e/Fiscal, Observações/Histórico), cabeçalho resumido, modal largo (`max-w-[1200px]`); **sem** alteração de regra fiscal, NF-e, estoque, financeiro ou faturamento no backend
- **Comercial 2.6:** PDF da Proposta (`GET /api/propostas/{id}/pdf/`) e PDF do Pedido de Venda (`GET /api/pedidos-venda/{id}/pdf/`) — ReportLab + `apps.core.pdf`, mesmo padrão do Pedido de Compra; botões no frontend; **sem** recálculo fiscal, NF-e, estoque ou financeiro
- **Comercial 2.6.1:** NCM nos PDFs comerciais (Proposta, Pedido de Venda, Pedido de Compra) — linha secundária abaixo da descrição; produto cadastrado, `ncm_avulso` ou snapshot; **sem** alteração fiscal/NF-e/estoque/financeiro
- **Comercial 2.6.3:** PDF externo da proposta (sem rentabilidade/cenário fiscal interno); `prazo_entrega_texto` em Proposta e Pedido de Venda; conversão copia prazo; correção `toFixed` em Propostas.tsx (`numberFormat.ts`); PDF interno futuro: `GET /api/propostas/{id}/pdf-interno/`
- **Comercial 2.6.4:** Status `CONVERTIDA` na proposta após conversão em Pedido de Venda; bloqueio de duplicidade; listagem/modal com badge e atalho «Abrir pedido»; migração de legado com pedido vinculado
- **Comercial 2.6.2:** Ações padronizadas «Visualizar PDF» / «Baixar PDF» (PC, Proposta, PV); helper `commercialPdfDownload`; download com `pedido-compra-` / `proposta-` / `pedido-venda-{numero}.pdf`; prévia com aviso sobre salvar via blob no Chrome; correção de `<nobr>` cru em grelhas (resumo faturamento / rentabilidade) — moeda como texto simples em `build_conditions_commercial_grid`

### Falta

- Versões da proposta
- Aprovação interna comercial/fiscal
- Margem mínima e alertas
- Condições comerciais avançadas
- Frete e prazo de entrega estruturados
- ~~Conversão robusta para pedido de venda~~ — **Propostas 2.1** concluída (serviço central, snapshot fiscal, vínculo item_proposta; ver seção 6)
- Histórico de alterações
- PDF comercial revisado

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Propostas 2.0** | Revisão comercial e aprovação |
| ~~**Propostas 2.1**~~ | ~~Conversão robusta para Pedido de Venda~~ — **concluída** |
| ~~**Comercial 2.2**~~ | ~~Numeração, datas e UX base (proposta/pedido)~~ — **concluída** |
| ~~**Comercial 2.2.1**~~ | ~~Numeração padrão PC (PROP/PV-AAAAMMDD-NNNN)~~ — **concluída** |
| ~~**Comercial 2.3**~~ | ~~UX proposta/pedido: datas BR, cenário fiscal único na UI, layout~~ — **concluída** |
| ~~**Comercial 2.3.1**~~ | ~~Autocomplete cliente/produto (padrão pedido de compra)~~ — **concluída** |
| ~~**Comercial 2.3.2**~~ | ~~Vendedor cadastrado, layout cliente/unidade, produto/avulso~~ — **concluída** |
| ~~**Comercial/Cadastros 2.4**~~ | ~~Colaboradores/responsáveis internos + layout comercial~~ — **concluída** |
| ~~**Comercial/Cadastros 2.4.1**~~ | ~~Tela de cadastro de Colaboradores~~ — **concluída** |
| ~~**Comercial/Cadastros 2.4.2**~~ | ~~Vínculo Colaborador ↔ usuário/login no ERP~~ — **concluída** |
| ~~**Comercial 2.5**~~ | ~~UX operacional do Pedido de Venda (abas no modal)~~ — **concluída** |
| ~~**Comercial 2.6**~~ | ~~PDF Proposta e PDF Pedido de Venda (padrão Pedido de Compra)~~ — **concluída** |
| ~~**Comercial 2.6.1**~~ | ~~NCM nos PDFs comerciais (Proposta, PV, PC)~~ — **concluída** |
| ~~**Comercial 2.6.2**~~ | ~~Visualizar/Baixar PDF padronizado + nomes de arquivo~~ — **concluída** |
| ~~**Comercial 2.6.3**~~ | ~~PDF proposta externo + prazo de entrega + fix numérico UI~~ — **concluída** |
| ~~**Comercial 2.6.4**~~ | ~~Status CONVERTIDA após conversão proposta → PV~~ — **concluída** |
| **Propostas 2.2** | Versionamento e histórico (fase futura) |
| **Comercial (futuro)** | PDF interno da proposta (`/pdf-interno/`) com rentabilidade e homologação fiscal |

### Checklist

- [x] Fiscal homologável (cenário + comparativo)
- [x] Opt-in cenário por proposta
- [ ] Versionamento
- [ ] Aprovação interna
- [x] Conversão para pedido (Propostas 2.1 — serviço `converter_proposta_pedido`, snapshot fiscal, UI na proposta)
- [x] Numeração automática e defaults comerciais (Comercial 2.2)
- [x] Numeração padrão pedido de compra (Comercial 2.2.1)
- [x] UX datas BR, cenário fiscal único na UI e layout modais (Comercial 2.3)
- [x] Autocomplete vendedor, vínculo usuário/login, layout cliente/unidade, produto cadastrado/avulso (Comercial 2.3.2)
- [x] Colaboradores/responsáveis internos, funções por área, layout cabeçalho/itens (Comercial/Cadastros 2.4)
- [x] Tela CRUD de Colaboradores no menu Cadastros (Comercial/Cadastros 2.4.1)
- [x] Vínculo Colaborador ↔ usuário/login na tela de Colaboradores (Comercial/Cadastros 2.4.2)
- [x] UX operacional do Pedido de Venda em abas (Comercial 2.5 — somente frontend)
- [x] PDF Proposta e PDF Pedido de Venda (Comercial 2.6)
- [x] NCM nos PDFs comerciais — Proposta, Pedido de Venda e Pedido de Compra (Comercial 2.6.1)
- [x] Visualizar PDF / Baixar PDF padronizado com nomes corretos (Comercial 2.6.2)
- [x] PDF proposta externo, prazo de entrega textual e fix numérico na UI (Comercial 2.6.3)
- [x] Status CONVERTIDA e bloqueio de reconversão proposta → pedido de venda (Comercial 2.6.4)
- [ ] Histórico de alteração
- [ ] PDF comercial revisado (demais campos além de NCM)

---

## 6. Pedido de venda

**Status no código:** Concluído parcial — **Propostas 2.1** (conversão proposta→pedido) e **Pedido Venda 3** (faturamento parcial via `FaturamentoPedidoVenda`, sem NF-e/estoque/financeiro); falta NF-e saída, estoque e financeiro definitivos.

### Objetivo

Criar o elo entre **proposta aprovada**, **estoque**, **faturamento**, **atendimento** e **financeiro**.

### Fluxo desejado

```text
Proposta aprovada
  → Pedido de venda
  → Reserva / compromisso de estoque
  → Atendimento (AtendimentoEstoque)
  → Faturamento (parcial ou total)
  → NF-e saída
  → Contas a receber
```

### Já feito (parcial)

- Modelo `PedidoVenda` e `ItemPedidoVenda`
- API CRUD e listagem no frontend
- **Propostas 2.1:** conversão via `converter_proposta_pedido.py` — snapshot fiscal por item, `item_proposta` FK, `snapshot_conversao` no pedido, filtros `?proposta_id=`, UI converter/abrir pedido na proposta
- Vínculo `proposta_id` no pedido
- Status inicial do pedido na conversão: `ABERTO`
- **Comercial 2.2:** numeração automática, formulário sem ID de proposta; status/datas padrão
- **Comercial 2.2.1:** `PROP-AAAAMMDD-NNNN` / `PV-AAAAMMDD-NNNN`; pedido da conversão com número próprio; legado preservado
- **Comercial 2.3:** formulários com datas BR, cenário fiscal de saída como fonte padrão (UI), blocos modais reorganizados
- **Pedido Venda 3:** `quantidade_faturada` / `status_item` no item; modelos `FaturamentoPedidoVenda` + `ItemFaturamentoPedidoVenda`; API `resumo-faturamento`, `faturamentos`, confirmar/cancelar rascunho; painel em `PedidosVenda.tsx`

### Falta

- Máquina de estados operacional completa (aprovação comercial formal)
- Aprovação e bloqueios comerciais adicionais
- Estorno de faturamento confirmado
- Reserva/compromisso de estoque
- Vínculo formal com `AtendimentoEstoque`
- Vínculo com NF-e saída
- Vínculo com financeiro (parcelas a receber)

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Pedido Venda 1** | Consolidar modelo e API (revisão) |
| **Pedido Venda 2** | Conversão de proposta e status |
| ~~**Pedido Venda 3**~~ | ~~Atendimento e faturamento parcial~~ — **concluída** (solicitação de faturamento; sem NF-e) |
| **Pedido Venda 4** | Integração financeiro |

### Checklist

- [x] Modelo PedidoVenda
- [x] Itens do pedido
- [ ] Status operacional completo
- [x] Conversão de proposta (Propostas 2.1 — robusta, sem NF-e/estoque/financeiro)
- [x] Faturamento parcial (Pedido Venda 3 — solicitação + confirmação, sem NF-e)
- [ ] Integração estoque / atendimento
- [ ] Integração NF-e saída
- [ ] Integração financeiro

---

## 7. NF-e saída

### Já feito

- Módulo **NFeSaida** operacional (UI e backend)
- Modos de atendimento de estoque (ex.: IMEDIATO / ANTECIPADO)
- Cenário fiscal de saída **pronto para consumo futuro** (motor + homologação em proposta)
- **NF-e Saída 1 (rascunho):** `POST .../faturamentos/{id}/gerar-nfe-saida/` — NF-e `RASCUNHO` a partir de `FaturamentoPedidoVenda` PRONTO_PARA_NFE; snapshot fiscal; sem SEFAZ/estoque/financeiro
- **NF-e Saída 2 (validação pré-emissão):** `GET /api/nf-saidas/{id}/validar-emissao/` — checklist pendências/alertas por grupo (cliente, emitente, itens, fiscal, valores, estoque, origem); sem transmissão SEFAZ/XML/DANFE/estoque/financeiro
- **NF-e Saída 3 (prévia XML/DANFE):** `preview-xml`, `preview-danfe`, `preview-dados` — rascunho sem valor fiscal, snapshot fiscal, recomendações DANFE parciais; sem SEFAZ/estoque/financeiro
- **NF-e Saída 3.1 (política de efeitos):** `GET .../efeitos-emissao/`, `POST .../aplicar-efeitos-autorizacao-interna/`, `POST .../cancelar-interno/` — política testável de autorização/cancelamento; status `AUTORIZADA_INTERNA` / `CANCELADA_INTERNA`; `NFeSaidaEvento`; estorno de `quantidade_faturada` no cancelamento interno; histórico no pedido; sem SEFAZ/protocolo/estoque/financeiro real
- **NF-e Saída 3.2 (UI efeitos/histórico):** `GET .../eventos/`; painel «Efeitos e histórico» na NF-e Saída; aba NF-e/Fiscal do pedido com histórico completo (canceladas visíveis, motivo, saldo liberado); ações internas com confirmação modal; sem transmissão SEFAZ
- **NF-e Saída 3.3 (consistência faturamento):** cliente herdado do pedido (UI sem mock); `modo_atendimento_estoque_display` na listagem; CFOP do snapshot (`cfop`/`cfop_venda`); DANFE prévia com coluna produto+NCM/CFOP sem sobreposição
- **Comercial/NF-e 3.4 (origem travada + complementares):** pedido `FATURADO` bloqueia itens no backend/UI; item com `quantidade_faturada` protegido; NF-e de faturamento trava itens/cliente; rascunho permite transporte/frete/peso/observações (`NFeSaida` migration `0020`); cópia faturamento→NF-e validada por produto; UI sem mock de produto; sem SEFAZ/estoque/financeiro real
- **NF-e Saída 3.5 (conferência completa):** modal por abas (Resumo, Itens, Fiscal, Reforma, Transporte, Obs., Validação, Histórico); `GET /api/nf-saidas/{id}/conferencia/`; pedido do cliente; helpers snapshot fiscal/reforma; checklist grupo Reforma; preview DANFE/XML com transporte e pedido cliente; migration `0021`; sem SEFAZ/estoque/financeiro
- **NF-e Saída 3.5.1 (UX conferência):** transportadora com `AsyncAutocomplete` + cadastro rápido no cadastro oficial; aba Transporte operacional (modalidades 0–9, volumes/placa); diagnóstico Reforma por item; fiscal com alertas; validação por severidade; modal 2xl com rodapé fixo; sem SEFAZ/estoque/financeiro
- **NF-e Saída 3.5.2 (atualizar impostos rascunho):** `GET/POST .../atualizar-impostos/preview|aplicar/`; serviço `nfe_saida_atualizar_impostos.py`; comparativo antes/depois por item; evento `IMPOSTOS_ATUALIZADOS`; botão na conferência (Fiscal, Reforma, Validação); Reforma/CFOP/ICMS/PIS/COFINS da regra atual; sem alterar origem comercial/SEFAZ/estoque/financeiro; migration `0022`
- **NF-e Saída 3.5.4 (DANFE de conferência):** endpoints `preview-danfe` / `danfe-conferencia`; dados em `danfe_conferencia.py`
- **NF-e Saída 3.5.4.2 (DANFE Conferência modelo 55 — MOC 7.0 Anexo II):** `danfe_modelo55_conferencia.py` — layout A4 retrato folhas soltas (Anexo III.02), coordenadas cm com origem superior, grades com divisórias (não relatório corrido); fontes Times/Courier; blocos canhoto/emitente/quadro DANFE/chave+área barcode/IE/destinatário/fatura/impostos/transporte/produtos/dados adicionais/reservado fisco; marca d’água «DANFE CONFERÊNCIA / SEM VALOR FISCAL / NF-e NÃO AUTORIZADA / SEM PROTOCOLO SEFAZ»; série «Conferência» e nº interno em rascunho; sem chave/protocolo/barcode fake; endpoints `preview-danfe` e `danfe-conferencia`; sem SEFAZ/estoque/financeiro; pronto para certificado/status serviço
- **NF-e Saída 3.5.4.3 (DANFE Conferência — ajuste fino MOC §3.8.1):** matriz ReportLab MOC §3.8.1 (base para fallback)
- **NF-e Saída 3.5.4.4 (DANFE Conferência — template fiscal HTML):** diagnóstico: **nfelib** e **PyNFe** não possuem gerador DANFE/PDF no projeto; **xhtml2pdf** inviável no slim sem cairo; escolhido **WeasyPrint** + `templates/danfe/modelo55_conferencia.html` + `.css` (A4, grid, tabela produtos legível, marca d’água discreta); `danfe_render.py` (HTML primário, ReportLab Canvas fallback); Docker com libcairo/pango; sem chave/protocolo/barcode fake; sem SEFAZ/estoque/financeiro
- **NF-e Saída 3.5.4.5 (acabamento visual DANFE HTML):** tipografia maior (9pt base), padding em mm nos blocos, cabeçalho/canhotto/quadro DANFE equilibrados, faixa unificada chave+barcode reservada (sem fake), tabela produtos com alinhamento e zebra, marca d’água mais suave; testes `test_nfe_saida_3545_danfe_acabamento_visual.py`; motor WeasyPrint inalterado
- **NF-e Saída 3.5.4.6 (DANFE HTML layout MOC cm):** template `modelo55_conferencia` com posicionamento absoluto §3.8.1 (margem 0,25 cm, área 20,57 cm); produtos y=17,87/h=6,77; rodapé inf. compl./fisco y=26,33; colunas MOC; matriz `danfe_moc_matriz_a4_retrato.py` sincronizada
- **NF-e Saída 3.5.4.7 (DANFE acabamento ref. visual):** densidade A4, produtos min 13,2 cm + linhas vazias grade, marca d’água no quadro produtos, stub barcode não escaneável, PIS/COFINS/IPI imposto e colunas IPI; sem chave/barcode fake
- **NF-e Saída 3.5.4.6b (DANFE paginação 1 item):** correção bloqueante — removidas 16 linhas filler e `min-height` no fluxo; produtos/rodapé em posição absoluta MOC (y=17,97 / 26,08 cm); 1 item = 1 página (`test_nfe_saida_3546_danfe_paginacao`); cache-bust no frontend; headers `Cache-Control` + debug `X-Danfe-*`
- **NF-e Saída 3.5.4.6 (POC BrazilFiscalReport DANFE 55):** módulo isolado `nfe_integracao/danfe_brazil_fiscal_report.py`; dependência `BrazilFiscalReport==0.7.4` (LGPL-3.0); flag `FISCAL_DANFE_RENDERER` (default `html`); testes `test_danfe_brazil_fiscal_report`; doc `docs/fiscal/brazil-fiscal-report-poc.md`. **Decisão POC:** Opção B — BFR só para DANFE autorizada futura (XML+protocolo reais); conferência permanece HTML/WeasyPrint até customização/licença. Motivo: preview XML Nexus não é drop-in (`nNF` texto, comentários XML); marca d’água conferência não customizável; LGPL exige validação jurídica para SaaS
- **NF-e Saída 4.0.1 (XML oficial NF-e 4.00 — nfelib):** `nfe_saida_xml_nfelib.py` monta `Tnfe` 4.00 via nfelib/xsdata a partir de `gerar_dados_preview_nfe_saida`; `GET .../preview-xml-oficial/`; `Id=NFePREVIEW{id}` (não é chave); `tpAmb=2`; sem `protNFe`/transmissão/assinatura; testes `test_nfe_saida_401_xml_nfelib`; prévia simplificada (`preview-xml`) mantida
- **NF-e 4.0.2 (emissão real homologação SEFAZ):** `NFeNumeracaoConfiguracao` por empresa/ambiente (homolog/prod separados); reserva atômica (`nfe_emissao/numeracao.py`); XML oficial com chave/série/nNF reais (`nfe_emissao/xml_oficial.py` + `infCpl` via `danfe_xml_adicionais`); assinatura A1 PyNFe; transmissão `ComunicacaoSefaz.autorizacao` só homologação; protocolo/cStat/xMotivo reais em `NFeSaida`; procNFe em `xml_autorizado`; DANFE homologação via BFR (`danfe-homologacao`); API `emitir-homologacao`, `reservar-numeracao`, CRUD `nfe-numeracoes`; UI conferência + cadastro empresa; **sem produção**, **sem estoque/financeiro real**; testes `test_nfe_saida_402_emissao_homologacao`
- **NF-e 4.0.3 (pós-autorização homologação — identidade fiscal e FAT):** numeração própria `FAT-YYYYMMDD-NNNN` em `FaturamentoPedidoVenda` (`gerar_numero_faturamento`, migration `0030`); `nfe_saida_apresentacao.py` com `titulo_exibicao`/`subtitulo_exibicao`/badges; NF-e fiscal (série/nº) como identidade principal após `AUTORIZADA_HOMOLOGACAO`; `RASCUNHO-FAT-*` apenas origem interna; UI modal/listagem/resumo/PV corrigidas; modo leitura pós-autorização; **sem produção**, **sem estoque/financeiro real**; testes `test_faturamento_numero_fat`, `test_nfe_saida_402_pos_autorizacao_homolog`, `nfeSaidaApresentacao.test.ts`
- **NF-e 4.0.4 (sanitização Cursor/teste + apresentação limpa):** `auditoria_limpeza_cursor`, `backup_limpeza_cursor`, `limpar_dados_cursor` (`apps/fiscal/limpeza_cursor/`); dry-run + backup obrigatório; preservação NF-e cStat 100/XML/protocolo; produtos só classificados; UI sem `Origem interna`/`FAT-LEGADO`; migration `0031` normaliza FAT legado; testes `test_nfe_saida_404_limpeza_apresentacao`, `nfeSaida404ApresentacaoLimpa.test.ts`
- **ERP 4.0.5 (paginação global):** `NexusPageNumberPagination`, `AutocompleteOrPaginationMixin`, busca/ordenação/filtros; endpoints paginados em empresas, clientes, produtos, pedidos venda, NF-e saída; componentes frontend reutilizáveis (`usePaginatedList`, `PaginationControls`, estados vazio/erro/loading); testes `test_paginacao_global`, `apiList.test.ts`
- **ERP 4.0.6 (dashboard operacional):** `GET /api/dashboard/resumo/` com blocos Comercial, Fiscal, Financeiro (em preparação), Estoque e Alertas; remoção de dados fake no Dashboard; cards clicáveis com filtros; financeiro stub (CR da NF-e saída prod / CP da NF-e entrada — sem gerar títulos nesta fase); testes `test_dashboard_resumo`
- **ERP 4.0.7 (paginação módulos restantes):** paginação server-side em fornecedores, transportadoras, colaboradores, propostas, pedidos compra, NF-e entrada, NF-e entrada histórica/XML, CT-e entrada, CT-e histórico/XML, regras fiscais (legado), saldos estoque, atendimentos estoque, certificados qualidade/fornecedor e corridas; `AutocompleteOrPaginationMixin` preservado (`limit` sem `page` → array); frontend com `usePaginatedList`, `PaginationControls`, `FilterBar`, estados vazio/erro/loading; dashboard com links filtrados (`/estoque?filtro=baixo_estoque`, `/produtos?sem_ncm=1`, `/pedidos-venda?status=parcialmente_faturado`); **sem financeiro real**, **sem produção NF-e**, **sem estoque real novo**; testes `test_paginacao_407`, `paginacao407.test.ts`
- **ERP 4.0.8 (BI modular por permissões):** home personalizada `/dashboard` + painéis `/dashboard/{comercial|fiscal|estoque|compras|qualidade|financeiro}`; endpoints `GET /api/dashboard/home/` e por módulo; helper `usuario_pode_ver_dashboard_modulo` (permissoes dos módulos + admin); KPIs, gráficos (recharts), rankings, alertas e drill-down filtrados; filtros período/empresa; backend omite/nega dados sem permissão; financeiro em preparação; compatibilidade `GET /api/dashboard/resumo/`; testes `test_dashboard_bi_408`, `dashboardBi408.test.tsx`
- **ERP 4.0.8.1 (acabamento visual BI):** período em pt-BR (`Maio/2026`, datas `dd/mm/aaaa`); submenu Dashboard no sidebar por permissão; home executiva com KPI hero e «Ver painel»; painéis com hierarquia (hero KPI, gráficos min 280px, alertas compactos); financeiro com `BIPreparationState`; estados vazios compactos; `GET /api/dashboard/permissoes/`; testes `test_dashboard_bi_408_1`, `dashboardBi4081.test.tsx`
- **ERP 4.0.9 (Design System Nexus — base visual):** tokens CSS/Tailwind (`index.css`, `design-system/tokens.ts`); componentes Nexus (`PageContainer`, `PageHeader` evoluído, `NexusCard`, `Badge`/`StatusBadge`, `DataTable`, inputs, skeleton, empty/error); app shell modernizado (sidebar, topbar, breadcrumbs); toasts `sonner` no `App`; telas piloto: Dashboard/BI, Produtos, NF-e Saída, Empresas, Clientes, Pedidos de Venda; doc `docs/design-system-nexus.md`; testes `designSystem409.test.tsx`; **sem alteração de regra fiscal, NF-e, financeiro, estoque ou permissões**
- **ERP 4.0.9.1 (migração visual incremental):** Fornecedores, Transportadoras, Propostas, Pedidos de Compra, NF-e Entrada e Histórico XML de Entrada migrados para `PageHeader`, `DataTableShell`/`DataTable`, `StatusBadge`, `TableSkeleton`, `EmptyState`/`ErrorState`, `NexusButton`/`NexusCard`; paginação server-side e `getAll`/autocomplete preservados; listagem NF-e sem XML completo (`chaveNfeResumida`); testes `designSystem4091.test.tsx`; build OK; **sem alteração de regra de negócio, fiscal, financeiro ou estoque**
- **ERP 4.0.9.2 (Qualidade/Cadastros):** Colaboradores, Corridas/Lotes Técnicos, Certificados de Qualidade e Certificados de Fornecedor migrados para padrão Nexus; filtros em `NexusCard` (Colaboradores); status de qualidade em `tokens.ts`; testes `designSystem4092.test.tsx`; **sem alteração de regras de qualidade, fiscal ou permissões**
- **ERP 4.0.9.3 (Estoque/CT-e/Fiscal):** Estoque/Saldos, Atendimentos de Estoque, CT-e Entrada, Histórico XML CT-e e Regras Fiscais (aba legada + header) migrados para padrão Nexus; chaves fiscais resumidas via `chaveNfeResumida` (XML completo só em modal/detalhe); tokens de estoque, atendimento, CT-e e fiscal em `tokens.ts`; testes `designSystem4093.test.tsx`; paginação/autocomplete preservados; **sem alteração de regra fiscal, estoque, CT-e ou permissões**
- **ERP 4.0.10 (Modelo operacional Nexus):** documentação oficial `docs/modelo-operacional-nexus.md`; enums `TipoAtendimentoItem`, `StatusEntradaFiscal`, `OrigemFisica`, `DestinoFisico`; model `AlocacaoAtendimento` (intenção de atendimento, campos opcionais); helpers read-only em `modelo_operacional.py`; fluxos A/B/C (entrada antes/depois da saída, misto); compra N:1 com vendas; estoque não bloqueia NF-e; financeiro/expedição/conciliação **não implementados**; testes `test_modelo_operacional_4010.py`; tokens operacionais no Design System
- **ERP 4.0.10.1 (Organização DF-e):** `dfe_classificacao.py` (operacional / base importada / homologação); homologação **excluída** da apuração (`apuracao_fiscal.py`); renomeação conceitual das bases importadas (UI + menu); NF-e Entrada: “Emitir entrada própria” + “Importar XML de fornecedor”; CT-e: “Importar XML CT-e”; correção `listPaginated` na base NF-e entrada importada; `docs/base-dfe-importada.md`; testes `test_dfe_organizacao_40101.py`, `dfeOrganizacao40101.test.tsx`
- **ERP 4.0.10.1 (Organização DF-e):** `dfe_classificacao.py` (operacional, base importada, homologação); homologação **excluída** da apuração (`apuracao_fiscal.py`); telas renomeadas (Base NF-e/CT-e Importada); UI NF-e Entrada/CT-e; badges homologação/fora apuração; correção `listPaginated` NF-e entrada importada; `docs/base-dfe-importada.md`; testes `test_dfe_organizacao_40101.py`, `dfeOrganizacao40101.test.tsx`
- **ERP 4.0.10.2 (Importação/recebimento DF-e):** `metadados_classificacao_dfe` + `classificacao_dfe` nas listagens; filtros de precificação excluem homologação; breadcrumbs “Base … Importada”; conferência com aviso sem efeito automático; badges conferida/preparada; KPI CT-e “Faturamento base para comparação”; testes `test_dfe_organizacao_40102.py`, `dfeOrganizacao40102.test.tsx`
- **ERP 4.0.10.2.1 (Separação UX base × operacional):** CT-e Entrada e NF-e Entrada sem importador duplicado; links para bases importadas; badges DF-e em Base NF-e Saída e Base CT-e; testes `test_dfe_organizacao_401021.py`, `dfeOrganizacao401021.test.tsx`
- **ERP 4.0.10.2.2 (Conferência segura CT-e importado):** status de conferência no `CTeHistoricoImportado`; endpoints conferir/divergente/ignorar; CT-e Entrada lista conferidos (`apto_operacional`); modal com aba Conferência, participantes formatados, documentos vinculados; sem financeiro/expedição/rateio automático; testes `test_cte_historico_conferencia_401022.py`, `dfeOrganizacao401022.test.tsx`
- **ERP 4.0.8.3 (Correção dashboards BI):** interceptor Axios para 401 (sessão expirada + redirect login); hooks `useDashboardBI` / `useDashboardPermissoes` / `usePaginatedList` sem Uncaught Promise; fallback seguro de permissões; `BIErrorState` / `BIAccessDenied` para 401/403; `BIKpiHeroCard` sem corte de valor (layout full-width + `break-words`); gráficos Recharts com wrapper `min-h-[280px] h-[320px]` e `BIEmptyChart` sem dados; helpers `biChartData.ts`; testes `dashboardBiBugfix4083.test.tsx`; **sem alteração de regra de negócio, NF-e ou permissões backend**
- **ERP 4.0.11 (Visibilidade operacional PV/FAT/NF-e):** serviço read-only `resumo_atendimento_operacional.py`; campo `resumo_atendimento_operacional` em serializers PV/NF-e e resumo de faturamento; componentes `AtendimentoOperacionalBadge`, `AtendimentoOperacionalResumo`, `AtendimentoOperacionalInline`; badges informativos (entrada pendente/conciliada, retirada fornecedor, entrega direta, misto, não definido, divergente); listagem NF-e enxuta; detalhe PV/FAT/conferência NF-e; testes `test_resumo_atendimento_operacional_4011.py` + `atendimentoOperacional4011.test.tsx`; **sem CRUD de alocação, sem estoque/financeiro, sem alteração de emissão NF-e/XML/DANFE**
- **ERP 4.0.12 (Gestão operacional de atendimento por item):** CRUD `AlocacaoAtendimento` (`/api/alocacoes-atendimento/`, actions PV/NF-e); service `alocacao_atendimento_service.py` (validação de quantidades, sem estoque/financeiro/expedição); vínculos opcionais compra/NF-e entrada/CT-e conferido/NF-e histórica; resumo 4.0.11 alimentado por alocações reais; UI aba PV + «Gerenciar atendimento» em faturamento e conferência NF-e; migration `0036`; testes `test_alocacao_atendimento_4012.py` + `alocacaoAtendimento4012.test.tsx`; **sem financeiro, estoque, expedição, apuração, emissão/XML/DANFE ou bloqueio de NF-e por entrada pendente**
- **ERP 4.0.13 (Busca e vínculo assistido DF-e/compra na AlocacaoAtendimento):** endpoints `opcoes/*` (fornecedor, PC, item PC, NF-e entrada importada, item NF-e, CT-e conferido); validações de homologação/conferência/produto em `alocacao_atendimento_vinculos.py`; autocompletes no formulário (sem IDs manuais); campo `vinculos` legível na API/lista; testes `test_alocacao_atendimento_busca_4013.py` + `alocacaoAtendimento4013.test.tsx`; **vínculo não gera financeiro/estoque/expedição nem promove base importada**
- **ERP 4.0.13.1 (Atendimentos Operacionais):** tela consolidada de `AlocacaoAtendimento` (`GET /api/atendimentos-operacionais/`, KPIs, filtros operacionais); substitui visualmente «Atendimentos de Estoque» (rota `/atendimentos-estoque` mantida); edição via modal 4.0.12/4.0.13; Saldos de Estoque permanecem em `/estoque`; testes `test_atendimentos_operacionais_40131.py` + `atendimentosOperacionais40131.test.tsx`; **sem estoque/financeiro/expedição/NF-e/apuração**
- **ERP 4.0.13.2 (Refinamento modal Pedido de Venda):** labels amigáveis NF-e/faturamento na modal PV (Resumo, Faturamento, NF-e/Fiscal, Observações); identidade fiscal (`NF-e Homologação nº …`) em vez de `RASCUNHO-FAT` como título; badges Homologação/Sem valor fiscal/Fora da apuração; PDF do pedido vs DANFE/XML separados; rodapé contextual (Salvar / Fechar / Salvar observações); alerta pedido faturado sem atendimento operacional; `pedidoVendaModalUi.ts` + testes; **sem alteração de emissão NF-e, apuração, financeiro, estoque ou expedição**
- **ERP 4.0.13.2.1 (Acabamento modal + PDF Pedido de Venda):** mesma linguagem na modal (`pedido_venda_apresentacao.py`, `formatBr.ts`); PDF **comercial** sem seção NF-e vinculada (dados fiscais só no ERP — aba NF-e / Fiscal); valores/quantidades pt-BR; itens faturados read-only; testes `test_pedido_venda_apresentacao_40132.py` + `formatBr.test.ts`; **sem emissão NF-e, apuração, financeiro, estoque ou expedição**
- **ERP 4.0.13.3 (Duplicatas no XML/DANFE da NF-e Saída):** `nfe_saida_duplicatas.py` gera cobrança comercial/fiscal a partir do pedido/faturamento; grupo `<cobr>/<dup>` no XML preliminar/oficial; DANFE de conferência exibe fatura/duplicatas; aba NF-e / Fiscal na modal PV lista `duplicatas_nfe`; API expõe `duplicatas_nfe` (não título financeiro); testes `test_nfe_saida_40133_duplicatas.py`; **sem contas a receber, boleto, estoque, apuração ou emissão produção**
- **ERP 4.0.13.4 (Reforma Tributária NF-e — pesquisa/preparação):** `docs/reforma-tributaria-nfe-nexus.md`; pacote `apps.fiscal.reforma_tributaria`; feature flags; helpers cálculo/validação/XML/DANFE stubs; `montar_payload_reforma_tributaria_nfe`; `nfe_saida_listagem.py`; **sem tags RTC no XML/DANFE de emissão; produção bloqueada**
- **ERP 4.0.13.4.1 (NF-e Saída compacta + Reforma na API/UI):** detalhe com `reforma_tributaria`; listagem com `listagem_resumo`; tela compacta + drawer; helpers pt-BR; testes 401341; **sem RTC no XML, sem financeiro/estoque/expedição**
- **ERP 4.0.13.5 (Checklist fiscal pré-homologação NF-e):** `nfe_saida_checklist_homologacao.py` + endpoints `POST /api/nf-saidas/checklist-homologacao/`, `POST /api/nf-saidas/{id}/checklist-homologacao/`, `POST /api/pedidos-venda/{id}/checklist-nfe-homologacao/`; modal `NFeChecklistHomologacaoModal`; valida XML/DANFE/duplicatas/apuração/Reforma/efeitos sem transmitir; testes `test_nfe_saida_40135_checklist_homologacao.py` + `nfeChecklistHomologacao.test.tsx`; **não emite NF-e, não gera financeiro/estoque/expedição**
- **ERP 4.0.13.5.1 (DANFE no checklist pré-homologação):** checklist reutiliza `gerar_preview_danfe_nfe_saida` (mesma base do botão DANFE); homologação autorizada usa XML autorizado via BFR; `_bloqueio_preview` liberado para homologação; modal checklist mais largo com resumo e seções colapsáveis
- **ERP 4.0.13.5.2 (Material de produtos + higienização teste/dev):** `material`/`material_label` na API; preservação em PATCH; `/produtos` com coluna Material; comando `limpar_dados_teste_nexus` (dry-run + confirmação; bloqueio produção); critérios em `limpeza_cursor/criterios.py`; DELETE amigável (409) em produto/cliente/pedido; testes `test_produto_material_401352.py`, `test_limpar_dados_teste_nexus.py`, `produtoMaterial.test.ts`; **sem inventar material, sem apagar dados reais, sem alterar NF-e/XML autorizado/apuração/financeiro/estoque**
- **ERP 4.0.13.5.3 (Layout DANFE/NF-e de conferência):** correção visual MOC §3.8.1 — seções FATURA/DUPLICATA, destinatário, imposto e transportador sem sobreposição; marca d'água discreta; duplicatas em tabela própria; coordenadas sem escala 1.058; testes `test_nfe_saida_401353_danfe_layout.py`; **sem transmissão SEFAZ, sem alterar XML autorizado, sem financeiro/estoque**
- **ERP 4.0.13.6 (Cadastro rápido comercial/compras + quantidade PV):** `ClienteComercialField`, `ProdutoComercialField`, `FornecedorOpcaoField` (Alocação) com modal compacto e seleção automática pós-save; reutiliza `POST /api/clientes/`, `/fornecedores/`, `/produtos/`; correção quantidade editável no Pedido de Venda (`aplicarConversao` com patch, input inline); `itemPedidoQuantidadeEditavel` + aviso read-only quando faturado; testes `test_comercial_40136_quantidade_cadastro_rapido.py`, `cadastroRapido40136.test.ts`, `nfeSaidaUi.test.ts`; **sem financeiro, estoque, expedição, NF-e/XML/DANFE ou apuração**
- **ERP 4.0.13.6.1 (Estabilização urgente PV/Faturamento/NF-e/DANFE):** hotfix `hotfix/401361-estabilizacao-pedido-faturamento-danfe`; cadastro rápido **suspenso na UI** (autocomplete estável); `valor_faturado` com desconto proporcional; `POST .../faturamentos/{id}/estornar/` e `.../reparar-vinculo-nfe/`; detecção `inconsistencias` no resumo (GERADO_NFE órfão, valor faturado > total); limpeza Cursor corrige status FAT ao remover NF-e; DANFE conferência restaurado ao layout `08a7170`; **PDF comercial PV** usa `calcular_totais_pedido_venda` (não `valor_total` salvo desatualizado); testes `test_comercial_401361_estabilizacao.py`, `test_pedido_venda_pdf_totais.py`; **sem financeiro, estoque, transmissão NF-e ou apuração**
- **ERP 4.0.13.6.13A (Limpeza renderizadores DANFE — BFR único):** `DANFE_RENDERER_OFICIAL=BFR`; removidos fallback HTML/WeasyPrint, templates `modelo55_conferencia.*`, renderers ReportLab legados de DANFE e flag `FISCAL_DANFE_RENDERER`; `danfe_render.py` só BFR com `DanfeBfrRenderError` (503) e logs `[DANFE_BFR_ERROR]` / `[DANFE_FALLBACK_BLOQUEADO]`; checklist/prontidão bloqueiam emissão se BFR falhar; UI badge «Renderer oficial BFR»; `weasyprint` removido de `requirements.txt` (permanece `reportlab` para PDFs comerciais); **sem alteração fiscal/XML/emissão/estoque/financeiro**
- **ERP 4.0.14 (Financeiro base operacional):** app `apps.financeiro` — cadastros, CR/CP, parcelas, baixa/estorno, status e origem rastreável; **CP com despesas manuais** (tipo lançamento: fornecedor, despesa, serviço, tributo, outros), **tributos a recolher** (ICMS…FGTS) com **parcelamento manual**, baixa por parcela; UI `ContaPagarDespesaModal` / `ContaPagarTributoModal`; testes `test_financeiro_operacional.py` (9) + `financeiroUi4014.test.tsx`; **sem cálculo automático de imposto, sem apuração fiscal, sem geração a partir de NF-e/XML/Reforma, sem seed de dados**
- **ERP 4.0.14.x (Importar NF-e entrada própria já emitida):** ação **«Importar entrada própria já emitida»** na NF-e Entrada operacional (`POST /api/nf-entradas/importar-entrada-propria-emitida/`); detecção `eh_entrada_propria_ja_emitida` (emitente = empresa, `tpNF=0`); status `IMPORTADA_PENDENTE_CONFERENCIA`; bases importadas rejeitam com orientação ao novo fluxo; deduplicação por chave; migration `0041_nfentrada_entrada_propria_importada_4014`; testes `test_entrada_propria_importada_4014.py` + `nfeEntrada4014.test.tsx`; **sem SEFAZ, financeiro, estoque, expedição ou apuração automática**
- **ERP 4.0.14.0.1 (Correção — remoção de Condições de pagamento do Financeiro):** removido o cadastro/rota/modelo financeiro de `Condição de pagamento`; títulos financeiros não exigem condição; parcelamento segue por parcelas diretas no título (receber/pagar/despesa/tributo); testes financeiros atualizados (10); **sem alteração em Proposta/Pedido/Faturamento/NF-e/XML/DANFE/duplicatas/estoque**.
- **NF-e Saída 4.0.1b (XML preliminar + DANFE BrazilFiscalReport):** `nfe_integracao/nfe_xml_preliminar.py` + `nfe_chave_acesso.py` + `nfe_numero_fiscal_preliminar.py` (série homologação configurável, `nNF` numérico do pk — nunca `RASCUNHO-FAT-*` como `nNF`); `GET .../preview-xml-preliminar/`; `danfe_brazil_fiscal_report.gerar_danfe_bfr_nfe_preliminar`; campos opcionais `xml_preliminar` / `chave_acesso_preliminar` com `sem_autorizacao`; sem transmissão SEFAZ, sem protocolo fake, sem estoque/financeiro; testes `test_nfe_saida_401_bfr_preliminar` + `test_danfe_brazil_fiscal_report`
- **NF-e Saída 4.0.1c (acabamento DANFE BFR):** `resolver_marca_dagua_danfe()` + `DanfeNexus` (marca d’água por status — conferência sem «CANCELADA» indevida); `montar_informacoes_complementares_danfe()` (infCpl enxuto; `observacoes_internas` nunca no PDF); logo emitente via `DanfeConfig.logo` + `get_empresa_logo_path_or_none`; `infcpl_semicolon_newline`; testes `test_nfe_saida_401_bfr_acabamento`
- **NF-e Saída 3.6 (certificado A1 + status SEFAZ):** camada `apps/fiscal/nfe_integracao/adapters/` (nfelib, PyNFe, certificado_a1, sefaz_status_service); modelo `NFeSefazStatusConsulta`; API `POST /api/nfe-sefaz-status/consultar/`, `GET /api/nfe-sefaz-status/`, `GET /api/empresas/{id}/validar-certificado-nfe/`; UI `/nfe-sefaz`; homologação SP via `ComunicacaoSefaz.status_servico('nfe')`; sem emissão NF-e
- **NF-e Saída 3.5.3 (prontidão da conferência):** `status_conferencia` separado do status fiscal (`EM_CONFERENCIA`, `COM_PENDENCIAS`, `CONFERIDA`, `PRONTA_PARA_EMISSAO`); `GET .../prontidao/`, `POST .../validar-conferencia/`, `POST .../marcar-pronta/`; serviço `nfe_saida_prontidao.py`; eventos `CONFERENCIA_*`, `PRONTA_PARA_EMISSAO`, `PRONTIDAO_INVALIDADA`; UI na conferência e listagem; invalidação ao salvar complementos ou atualizar fiscal; sem SEFAZ/estoque/financeiro; migration `0023`

### Falta

- Emissão **produção** SEFAZ, contingência, cancelamento/CC-e/inutilização
- ~~Transmissão homologação / XML autorizado / DANFE homologação~~ — **4.0.2 homologação** (ver item acima; produção fora)
- NF-e saída aplicando `RegraFiscalSaida` na emissão (recálculo na transmissão)
- ~~Geração de XML oficial NF-e 4.00 (nfelib) em rascunho~~ — **4.0.1 concluída** (sem transmitir)
- Assinatura XML e transmissão SEFAZ (fase 4)
- Geração de XML com impostos do cenário (recálculo na emissão)
- DANFE alinhado às recomendações cadastradas
- Cancelamento, carta de correção, inutilização
- Devolução, remessa, venda para entrega futura, simples faturamento

### Próximas fases

| Fase | Objetivo |
|------|----------|
| ~~**NF-e Saída 1**~~ | ~~Rascunho a partir do faturamento do pedido~~ — **concluída** |
| **NF-e Saída 1b** | Consumir cenário fiscal na emissão |
| ~~**NF-e Saída 2**~~ | ~~Validações fiscais antes da emissão~~ — **concluída** |
| ~~**NF-e Saída 3**~~ | ~~XML e DANFE prévia~~ — **concluída** |
| ~~**NF-e Saída 3.1**~~ | ~~Política de efeitos emissão/cancelamento~~ — **concluída** (simulação interna; SEFAZ/estoque/financeiro futuros) |
| ~~**NF-e Saída 3.2**~~ | ~~UI de efeitos, eventos e histórico no pedido/NF-e~~ — **concluída** |
| ~~**NF-e Saída 3.3**~~ | ~~Consistência NF-e de faturamento + DANFE preview~~ — **concluída** |
| ~~**Comercial/NF-e 3.4**~~ | ~~Origem comercial travada + dados complementares em rascunho~~ — **concluída** |
| ~~**NF-e Saída 3.5**~~ | ~~Tela de conferência fiscal + Reforma Tributária~~ — **concluída** |
| ~~**NF-e Saída 3.5.1**~~ | ~~UX conferência + transportadora autocomplete/cadastro rápido~~ — **concluída** |
| ~~**NF-e Saída 3.5.2**~~ | ~~Atualizar impostos do rascunho (regra fiscal atual)~~ — **concluída** |
| ~~**NF-e Saída 3.5.3**~~ | ~~Prontidão da conferência (validar / marcar pronta)~~ — **concluída** |
| ~~**NF-e Saída 3.5.4**~~ | ~~DANFE de conferência em layout real (PDF)~~ — **concluída** |
| **NF-e Saída 4** | Transmissão SEFAZ / autorização real |
| **NF-e Saída 5** | Cancelamento / CC-e / inutilização na SEFAZ |
| **NF-e Saída 6** | Remessa / devolução / entrega futura |

### Checklist

- [x] Rascunho NF-e a partir do faturamento (NF-e Saída 1)
- [x] Validação fiscal/operacional pré-emissão em rascunho (NF-e Saída 2)
- [x] Prévia XML e DANFE para conferência (NF-e Saída 3)
- [x] Política de efeitos autorização/cancelamento e histórico operacional (NF-e Saída 3.1)
- [x] UI de efeitos, eventos e histórico NF-e no pedido e na tela de NF-e (NF-e Saída 3.2)
- [x] Consistência cliente/CFOP/atendimento e layout DANFE prévia (NF-e Saída 3.3)
- [x] Pedido faturado bloqueia itens; NF-e de faturamento trava origem comercial; complementares editáveis em rascunho (3.4)
- [x] Conferência NF-e rascunho por abas + IBS/CBS + pedido cliente (3.5)
- [x] UX conferência: autocomplete transportadora, cadastro rápido, diagnóstico reforma (3.5.1)
- [x] Atualizar impostos do rascunho a partir da regra fiscal atual, com preview e evento de auditoria (3.5.2)
- [x] Fluxo de prontidão da conferência: validar, marcar pronta, eventos e invalidação ao editar (3.5.3)
- [x] DANFE de conferência em layout real com marca d’água sem valor fiscal (3.5.4)
- [ ] Cenário aplicado na emissão/transmissão
- [ ] XML com impostos do cenário
- [ ] DANFE
- [ ] Cancelamento
- [ ] Carta de correção
- [ ] Inutilização
- [ ] Remessas
- [ ] Devoluções

---

## 8. NF-e entrada própria

Além de **importar XML de fornecedor**, o ERP precisará **emitir NF-e própria de entrada** em cenários como:

- Recusa ou devolução de cliente
- Retorno de remessa
- Entrada simbólica
- Entrada por industrialização
- Devolução de venda

### Falta

- Modelo e fluxo de emissão própria de entrada
- CFOPs e regras específicas de entrada própria
- Vínculo com NF de saída original
- Vínculo com estoque e financeiro

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Entrada Própria 1** | Diagnóstico e modelagem |
| **Entrada Própria 2** | Emissão por devolução/recusa |
| **Entrada Própria 3** | Retorno de remessa |

### Checklist

- [ ] Modelo de emissão própria
- [ ] Vínculo com NF saída
- [ ] XML
- [ ] Estoque
- [ ] Fiscal
- [ ] Financeiro

---

## 9. Remessas

Controle do que **sai**, **permanece em terceiros** e **retorna** (industrialização, conserto, demonstração, conta e ordem).

### Falta

- Tipos de remessa modelados
- NF-e de remessa e retorno
- Saldo pendente de retorno
- Impacto em estoque e relatório

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Remessa 1** | Modelo de controle |
| **Remessa 2** | Emissão NF-e remessa |
| **Remessa 3** | Retorno e baixa |

### Checklist

- [ ] Tipo de remessa
- [ ] NF remessa
- [ ] Controle pendente
- [ ] Retorno
- [ ] Estoque
- [ ] Relatório

---

## 10. Estoque e rastreabilidade

### Já feito

- `AtendimentoEstoque` (imediato e antecipado)
- Vinculação com conferência de NF-e entrada
- Aplicação física em estoque por corrida
- CQ definitivo exige rastreabilidade
- Corrida/lote vinculados ao produto e à NF

### Falta

- Relatório **ponta a ponta** (NF entrada → conferência → estoque → saída → CQ)
- **Kardex** / `MovimentoEstoque`
- Estorno controlado
- Tela Corridas/Lotes técnicos aprimorada
- Histórico consolidado por produto/corrida

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Estoque 3.13** | Relatório ponta a ponta |
| **Estoque 3.14** | MovimentoEstoque / Kardex |
| **Estoque 3.15** | Estorno controlado |
| **Estoque 3.16** | Corridas / Lotes técnicos |

### Checklist

- [x] Aplicação física de estoque
- [x] Atendimento antecipado
- [x] Integração conferência
- [ ] Kardex
- [ ] Estorno controlado
- [ ] Relatório ponta a ponta
- [ ] Histórico por produto/corrida

---

## 11. Qualidade

### Já feito

- Certificado de fornecedor (entrada)
- Certificado de qualidade (CQ)
- Busca por corrida
- Vínculo com conferência e itens de NF
- Rastreabilidade obrigatória para emissão definitiva de CQ

### Falta

- Relatório de rastreabilidade no CQ
- Dashboard de certificados pendentes
- Exceção administrativa controlada (se necessário)

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Qualidade 4** | Relatório de rastreabilidade CQ |
| **Qualidade 5** | Dashboard de pendências |
| **Qualidade 6** | Exceção administrativa controlada |

### Checklist

- [x] Certificado fornecedor (CF)
- [x] Certificado qualidade (CQ)
- [x] Rastreabilidade
- [ ] Relatório CQ
- [ ] Dashboard pendências
- [ ] Exceção controlada

---

## 12. Cadastros mestres

Base para fiscal, comercial e estoque. Refinar progressivamente.

### Escopo de refinamento

- Clientes e fornecedores (contatos, endereços, IE, regime)
- Transportadoras
- Produtos (fiscal, comercial, estoque, NCM)
- Vendedores
- Condições de pagamento
- Dados bancários
- Tabelas fiscais auxiliares

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Cadastros 1** | Diagnóstico dos cadastros atuais |
| **Cadastros 2** | Cliente completo |
| **Cadastros 3** | Fornecedor completo |
| **Cadastros 4** | Transportadora |
| **Cadastros 5** | Produto fiscal/comercial/estoque |

### Checklist

- [ ] Cliente completo
- [ ] Fornecedor completo
- [ ] Transportadora
- [ ] Produto completo
- [ ] Contatos
- [ ] Endereços múltiplos
- [ ] Dados fiscais refinados
- [ ] Dados bancários

---

## 13. Financeiro

### Falta (macro)

- Contas a receber e a pagar
- Parcelas, boletos, Pix
- Baixa manual e automática
- Fluxo de caixa
- Centro de custo e plano financeiro
- Comissões
- Conciliação bancária

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Financeiro 1** | Contas a receber |
| **Financeiro 2** | Contas a pagar |
| **Financeiro 3** | Fluxo de caixa |
| **Financeiro 4** | Conciliação |
| **Financeiro 5** | Comissões |

### Checklist

- [ ] Contas a receber
- [ ] Contas a pagar
- [ ] Parcelas
- [ ] Baixa
- [ ] Fluxo de caixa
- [ ] Conciliação
- [ ] Comissões

---

## 14. CRM

### Falta

- Leads e oportunidades
- Pipeline e etapas
- Follow-up e próxima ação
- Motivo de perda
- Histórico de contato
- Conversão para proposta

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **CRM 1** | Leads e oportunidades |
| **CRM 2** | Pipeline |
| **CRM 3** | Atividades e follow-up |
| **CRM 4** | Conversão para proposta |

### Checklist

- [ ] Leads
- [ ] Oportunidades
- [ ] Pipeline
- [ ] Atividades
- [ ] Histórico de contato
- [ ] Conversão para proposta

---

## 15. Contábil

**Futuro** — após financeiro e fiscal operacionais estarem sólidos.

### Falta

- Plano de contas
- Lançamentos contábeis (manuais e automáticos)
- Integração fiscal e financeira
- Centros de custo
- DRE e balancete
- SPED (horizonte longo)

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **Contábil 1** | Plano de contas |
| **Contábil 2** | Lançamentos automáticos |
| **Contábil 3** | DRE e balancete |
| **Contábil 4** | SPED |

### Checklist

- [ ] Plano de contas
- [ ] Lançamentos
- [ ] Integração fiscal
- [ ] Integração financeiro
- [ ] DRE
- [ ] Balancete
- [ ] SPED

---

## 16. Relatórios / BI / Auditoria

### Já feito (parcial)

- Apuração fiscal (entrada/saída)
- Painéis gerenciais históricos (fiscal/comercial)
- Métricas de apoio em propostas e pedidos

### Falta

- Dashboards operacionais unificados (comercial, fiscal, estoque, qualidade)
- Auditoria de alterações em cadastros e documentos
- Logs operacionais estruturados
- Exportações padronizadas

### Próximas fases

| Fase | Objetivo |
|------|----------|
| **BI 1** | Dashboard operacional |
| **BI 2** | Auditoria de alterações |
| **BI 3** | Relatórios fiscais e comerciais |
| **BI 4** | Exportações |

### Checklist

- [ ] Dashboard comercial
- [ ] Dashboard fiscal
- [ ] Dashboard estoque
- [ ] Dashboard qualidade
- [ ] Auditoria de alterações
- [ ] Exportação

---

## 17. Ordem recomendada das próximas fases

Prioridade sugerida para maximizar valor com menor risco (homologar antes de emitir):

| Ordem | Fase | Motivo |
|-------|------|--------|
| 1 | **Saída 3.10** — Histórico/auditoria da homologação fiscal | Fechar ciclo da homologação 3.9 antes da NF-e |
| 2 | Homologar propostas reais com cenário fiscal | Validar regras em produção controlada |
| 3 | **Pedido Venda 1** — Modelo e API (revisão/consolidação) | Base já parcial no código |
| ~~4~~ | ~~**Propostas 2.1**~~ — Converter proposta em pedido | **Concluída** |
| ~~4b~~ | ~~**Pedido Venda 3**~~ — Faturamento parcial do pedido | **Concluída** |
| ~~4c~~ | ~~**NF-e Saída 1**~~ — Rascunho a partir do faturamento | **Concluída** |
| ~~4d~~ | ~~**Comercial 2.2**~~ — Numeração/datas/UX proposta e pedido | **Concluída** |
| ~~4d1~~ | ~~**Comercial 2.2.1**~~ — Numeração padrão CQ (PROP{n}/PV{n}) | **Concluída** |
| 5 | **NF-e Saída 1** — Consumir cenário fiscal | Objetivo principal do cenário de saída |
| ~~6~~ | ~~**NF-e Saída 2** — Validações pré-emissão~~ | **Concluída** |
| 7 | **Cadastros 1** — Diagnóstico/refino | Base para emissão e financeiro |
| 8 | **Estoque 3.13** — Relatório ponta a ponta | Visibilidade operacional |
| 9 | **Estoque 3.14** — Kardex | Controle de movimentação |
| 10 | **Financeiro 1** — Contas a receber | Fechar ciclo venda → recebimento |
| 11 | **Remessa 1** — Modelo de controle | Pré-requisito para NF remessa |
| 12 | **Entrada Própria 1** — Diagnóstico/modelagem | Devoluções e retornos |
| 13 | **CRM 1** — Leads/oportunidades | Funil comercial |
| 14 | **Contábil 1** — Plano de contas | Após financeiro maduro |

---

## 18. Política de checklist daqui para frente

A cada nova fase de desenvolvimento, registrar no PR ou na descrição da fase:

| Campo | Conteúdo |
|-------|----------|
| **Objetivo** | O que a fase entrega |
| **Escopo permitido** | Arquivos/módulos que podem ser alterados |
| **Não fazer** | O que está explicitamente fora (evitar creep) |
| **Checklist antes** | Pré-condições |
| **Checklist depois** | Entregáveis verificados |
| **Validações** | Comandos obrigatórios |
| **Próxima decisão** | O que fica para a fase seguinte |

### Formato padrão

#### Checklist da fase

**Antes**

- [ ] Ler roadmap e fase anterior
- [ ] Confirmar escopo / não fazer
- [ ] Identificar migrations e testes do app

**Durante**

- [ ] Implementar somente o escopo
- [ ] Manter compatibilidade com legado (quando aplicável)
- [ ] Documentar endpoints/contratos se houver API

**Depois**

- [ ] Atualizar `docs/roadmap-nexus-erp.md` (status e checklists)
- [ ] Revisar linter nos arquivos alterados

**Validações (quando houver código)**

- [ ] `docker compose exec frontend npm run -s build`
- [ ] `docker compose exec backend python manage.py check`
- [ ] `docker compose exec backend python manage.py makemigrations --check --dry-run`
- [ ] Testes do app alterado (`apps.<nome> -v 1`)
- [ ] Regressões principais (comercial, regras_fiscais, fiscal, qualidade — conforme impacto)

**Critérios de aceite**

- [ ] Comportamento descrito no objetivo verificado
- [ ] Nenhuma regressão conhecida nos testes acima
- [ ] Payload/API documentado se mudou contrato

---

## 19. Observação final

Este roadmap é **vivo**. Ao concluir uma fase:

1. Marcar checklists neste documento.
2. Ajustar status na tabela executiva (seção 2).
3. Registrar a **próxima fase recomendada** na seção 17, se a prioridade mudar.
4. Manter a separação **Entrada** (validação do XML recebido) vs **Saída** (cenário para proposta/emissão).

Documentos complementares existentes:

- `docs/qualidade-certificados.md` — certificados e rastreabilidade
- `backend/docs/importacao_ncm.md` — importação NCM

---

*Última atualização: maio/2026 — Saída 3.10 (histórico/auditoria homologação), Saída 3.9, roadmap central.*

## ERP 4.0.13.6.2 — Padronização segura dos campos comerciais

- Padronização de inputs de quantidade/moeda/percentual no fluxo comercial.
- Estabilização de `Pedido de Venda`, `Proposta`, `Pedido de Compra` e `Faturamento`.
- Linha de item como resumo; edição única no painel expandido/modal.
- Payload de itens limpo e normalizado para API.
- Consistência entre total do pedido, resumo financeiro e PDF comercial.

## ERP 4.0.13.6.3 — Segunda passada segura (Propostas e Pedidos de Compra)

- Reaproveito dos componentes comerciais padronizados em `Propostas` e `Pedidos de Compra`.
- Remoção de inputs genéricos críticos para quantidade/preço/desconto em pontos de edição de item.
- Padronização de feedback amigável (`toast`) no salvar/validações desses módulos.
- Build frontend mantido estável após ajustes.

## ERP 4.0.13.7 — Inteligência de equivalência, composição e montagem de produtos

- Equivalência simples e composta por fornecedor; composição/montagem de produto (simples, roscada, soldada, com serviço, terceirizada).
- Motor de sugestão genérico na conferência NF-e entrada com confiança 0–100; confirmação manual obrigatória.
- XML de entrada preservado; equivalência não movimenta estoque nem financeiro nesta fase.

## ERP 4.0.13.7.1 — Generalização da estrutura de equivalência, composição e montagem

- Remoção de acoplamento com exemplos operacionais reais (fornecedor/pedido/NF/produto específicos).
- Modelo revisado: composição com múltiplas origens (comprar pronto + montar + kit); `ProcessoMontagem` cadastral.
- Heurísticas genéricas: regra cadastrada, composição cadastrada, similaridade textual/agregada, tolerâncias configuráveis.
- Aba **Composição / Montagem** no cadastro de produto; testes e documentação com dados sintéticos.
- **Famílias/Figuras permanecem a base** de produtos técnicos; composição/equivalência é camada complementar.
- Dados sintéticos de teste **somente em banco isolado** (`test_*`); não poluir banco de desenvolvimento.
- Pendência futura: ordem de montagem com movimentação real de estoque.

## ERP 4.0.13.7.2 — Limpeza segura de produtos artificiais de teste

- Comando `limpar_produtos_teste_401372` com dry-run obrigatório e confirmação explícita.
- Remove apenas produtos da lista autorizada (código + descrição exata «Fam») sem vínculos operacionais.
- Preserva famílias/figuras, templates de código e produtos reais.
- `NexusDiscoverRunner` bloqueia testes no banco de desenvolvimento.

## ERP 4.0.13.6.13 — Higienização final do XML de transmissão NF-e

- XML **preview/conferência** pode conter `NFePREVIEW`, comentários e avisos internos.
- XML **transmissão** é limpo: Id com chave real, sem marcas de prévia, `dhEmi` com timezone.
- IE é exibida com máscara na UI, mas serializada **sem máscara** no XML de transmissão.
- `indFinal` e `indPres` devem ser confirmados na conferência antes da emissão.
- Validação XSD e checklist incluem grupo **Higienização XML**.

## ERP 4.0.13.6.12 — Performance e UX da conferência NF-e

- Abertura da conferência é **leve** (`GET .../conferencia/?modo=abertura`) — sem checklist completo, sem XML, sem DANFE.
- XML e DANFE são gerados **sob demanda** (botões dedicados).
- **Salvar alterações** (`POST .../salvar-conferencia/`) persiste complementos sem validação pesada.
- **Validar dados salvos** executa checklist completo uma única vez por requisição.
- **Salvar e validar** (`POST .../salvar-e-validar-conferencia/`) em uma requisição.
- Checklist **leve** (modo `leve`) vs **completo** (modo `completo`: ViaCEP + Reforma no XML).
- Cache de XML pré-autorização reutilizado quando `xml_preliminar` persistido e não invalidado.
- Logs `[NFE_PERF]` em DEBUG/homologação (`NFE_PERF_LOGGING`); produção sem logs verbosos.
- Validação **não altera** cálculo fiscal, transporte, Reforma ou duplicatas.

## ERP 4.0.13.6.11 — Base IBS/CBS 2026 parametrizada

- Base de cálculo IBS/CBS é **parametrizável** por regra fiscal (`modo_base_ibs_cbs`).
- Modos: base cheia, sem ICMS, sem ICMS/PIS/COFINS, sem IPI, oficial 2026, customizada.
- Snapshot registra fórmula, deduções, fonte e status (`pendente_confirmacao` | `confirmada`).
- XML usa exatamente a base do snapshot — mesma camada central IBSCBS/IBSCBSTot.
- Produção bloqueia regra pendente; homologação alerta.
- Comparação com XML externo é diagnóstico — não altera regra automaticamente.
- Referência normativa: NT 2025.002-RTC / LC 214/2025 — confirmar com contabilidade antes de produção.

## ERP 4.0.13.6.10 — Persistência e validação da aba Transporte na conferência NF-e

- Aba Transporte com **salvamento explícito**; validar conferência usa apenas dados já persistidos.
- `modFrete = 9` representa ausência de transporte — não pode coexistir com transportadora/volumes/pesos (pendência bloqueante).
- Botões: **Salvar alterações**, **Salvar e validar**, **Validar dados salvos**, **Marcar pronta para emissão**.
- Estado de alterações não salvas (dirty form) com aviso inline; validar/marcar pronta bloqueados enquanto houver edição local.
- Confirmação ao selecionar modalidade 9 com dados preenchidos (limpar transporte ou manter modalidade anterior).
- XML respeita transporte salvo: `modFrete=9` omite transportadora/volumes no binding nfelib.
- Transporte não gera financeiro, estoque, expedição nem altera ICMS/PIS/COFINS/Reforma.

## ERP 4.0.13.6.9 — Reforma Tributária em todos os XMLs da NF-e

- Serialização oficial `IBSCBS` / `IBSCBSTot` via nfelib (`TtribNfe`, `TibscbsmonoTot`) a partir do snapshot calculado.
- Builders centrais reutilizados por preliminar, preview, download, checklist e transmissão.
- Correção de `cMun` do destinatário (sem reutilizar `cMunFG` do emitente); bloqueio quando cidade/UF/cMun incoerentes.
- Validação e checklist bloqueiam se Reforma calculada não estiver no XML; XML autorizado não é alterado.

## ERP 4.0.13.6.8 — Estorno seguro de faturamento e descarte de NF-e rascunho (pré-autorização)

- Estorno de faturamento confirmado quando **não** há NF-e autorizada (sem protocolo/cStat 100/XML autorizado).
- NF-e rascunho marcada como `DESCARTADA_INTERNA` (histórico preservado; não apaga XML/DANFE).
- Motivo obrigatório (mín. 10 caracteres); eventos `ESTORNO_FATURAMENTO_PRE_AUTORIZACAO_NFE` e `DESCARTE_RASCUNHO_NFE`.
- Endpoints: `POST .../faturamentos/{id}/estornar/`, `POST /api/nf-saidas/{id}/descartar-rascunho/`.
- UI: modal com aviso “não envia evento à SEFAZ”; botões Cancelamento/CC-e desabilitados (fases 4.0.13.6.9 / 4.0.13.6.10).

## ERP 4.0.13.6.7 — Ajuste de layout do DANFE de conferência (duplicatas e totais)

- Bloco Fatura/Duplicatas com altura dinâmica, grade 1 ou 2 colunas (até 10 no bloco; excedente em Dados Adicionais).
- Rótulos longos do quadro Cálculo do Imposto com quebra de linha (`VALOR TOTAL DOS PRODUTOS`, etc.).
- Somente renderização PDF/HTML; sem alteração de XML, cálculos ou emissão.

## ERP 4.0.13.6.6 — Correção da aplicação e cálculo da Reforma Tributária no snapshot da NF-e rascunho

- Parsing de alíquotas IBS/CBS com vírgula (`0,1` → `0.1`) na persistência da regra e no cálculo do snapshot.
- Serviço `nfe_saida_reforma_calculo.py`: base × alíquota%, redução/diferimento opcionais, status `CALCULADA` / `ATENCAO`.
- Conferência NF-e exibe base, alíquota e valor por item; validação alerta `REFORMA_ALIQUOTA_SEM_VALOR` quando aplicável.

## ERP 4.0.13.6.5 — Correção da aplicação de regra fiscal existente no rascunho da NF-e

- `Atualizar fiscal` da NF-e rascunho passa a buscar **sempre** no cenário padrão de saída (`buscar_regra_fiscal_nfe_saida_rascunho`), independente de `USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS`.
- Corrige caso em que regras apareciam na tela Regras Fiscais mas não eram encontradas no modal (busca só na tabela legada).
- SP→PA aplicada quando destino é PA; SP→SP não é fallback indevido.
- Testes `test_nfe_atualizar_fiscal_cenario_401365.py`.

## ERP 4.0.13.6.4 — Consistência fiscal de cliente/endereço + diagnóstico de regra fiscal na NF-e

- Validação de endereço fiscal do cliente (CEP × cidade × UF) com consulta ViaCEP reutilizável.
- Cadastro comercial pode ser salvo com alerta; bloqueio fiscal na NF-e quando endereço inconsistente.
- `Atualizar fiscal` usa UF destino real do cliente (via CEP) — não aplica SP→SP se destino fiscal é PA.
- Diagnóstico explícito: endereço inconsistente vs falta de regra `NCM · origem · destino`.
- Snapshot fiscal só é gerado quando regra compatível existe; sem mascaramento de erro.
- Testes `test_endereco_fiscal_nfe_401361.py`, `enderecoFiscal.test.ts`; **sem emissão/transmissão NF-e, financeiro, estoque ou apuração**.

## ERP 4.0.13.8 — Padronização operacional da interface do Nexus

- Camada UX: linguagem de negócio na tela principal; detalhes técnicos em Avançado/Suporte.
- NF-e Saída: Ver DANFE, Baixar XML, Emitir NF-e; XMLs múltiplos e renderer movidos para seção avançada.
- Produtos/Famílias: «Modelo de medidas», «Como o código será formado»; enums de composição com labels amigáveis.
- Pedidos/Propostas/Compras/NF-e Entrada: status e ações comerciais padronizados.
- Componentes `AdvancedSupportSection`, `OperationalMessage`; dicionário `operationalUi.ts`.
- **Escopo exclusivo UX** — sem alteração fiscal, XML, DANFE, estoque ou financeiro.
- Testes frontend: `operationalUi401308.test.ts`; build Vite.

## ERP 4.0.14.1 — Formas fixas de pagamento, créditos e abatimentos por devolução

Escopo operacional do Financeiro para remover cadastro de formas, padronizar lista fixa, criar créditos de cliente/fornecedor, permitir abatimento por devolução, aplicação de crédito e estorno com rastreabilidade.

## ERP 4.0.14.1.1 — Ajuste de Conta Financeira tipo Banco e menu financeiro

- Modal Conta/Caixa com campos bancários condicionais (Tipo = Banco); validação frontend + serializer (`banco` obrigatório).
- Listagem exibe banco cadastrado; legado sem banco mostra «Não informado».
- Menu lateral Financeiro: apenas um item ativo por rota (`/financeiro` exato para Visão geral).
- Testes: `financeiroUi401411.test.tsx` + `test_financeiro_operacional.py` (conta Banco/Caixa).
- **Sem migration** (campos `banco`/`agencia`/`conta` já existiam); **sem alteração** em NF-e/XML/DANFE/Reforma/pedidos/estoque/baixas/créditos por regra de negócio.

## ERP 4.0.14.1.2 — Ajuste de labels de conta financeira tipo Banco

- Labels e placeholders do modal Conta/Caixa: apelido operacional vs instituição bancária; ordem Banco → Descrição/Apelido.
- Sem campo novo no model; sem migration; testes `financeiroUi401412.test.tsx`.

## ERP 4.0.14.1.3 — Padronização da busca de fornecedor no Financeiro

- `FornecedorSearchSelect` substitui select simples em Nova conta a pagar e Nova despesa.
- API: `GET /api/fornecedores/?search=&limit=` (busca por razão social, fantasia, CNPJ).
- Serializer de título expõe `fornecedor_nome` e `fornecedor_cnpj` para listagem/detalhe.
- Testes: `financeiroUi401413.test.tsx`, `test_busca_fornecedores.py`.

## ERP 4.0.14.1.4 — Padronização de Cliente em Contas a Receber

- `ClienteSearchSelect` substitui select simples; botão/modal «Nova conta a receber».
- API: `GET /api/clientes/?search=&limit=` com busca por documento normalizado (dígitos).
- Serializer de título expõe `cliente_cnpj` para detalhe/listagem.
- Testes: `financeiroUi401414.test.tsx`, `test_busca_cadastros.py` (cliente).

## ERP 4.0.14.1.5 — Detalhe financeiro por status

- Mensagem e ações do drawer são determinadas por **status**, **saldo em aberto** e **existência de baixas ativas**.
- Título em aberto permite baixa, edição e cancelamento (conforme flags da API).
- Título quitado orienta estorno antes de alteração sensível.
- Título cancelado não aceita novas baixas.
- Helpers: `getTituloFinanceiroOperationalMessages`, `getTituloFinanceiroAcoes` (`financeiroUi.ts`).
- Serializer expõe `pode_editar`, `pode_baixar`, `pode_cancelar`, `possui_baixa_ativa`, `pode_estornar_baixa`, `pode_abater`, `pode_aplicar_credito`.
- Testes: `financeiroUi401415.test.tsx`, `test_financeiro_operacional.py` (flags serializer).

## ERP 4.0.14.2 — Créditos, abatimentos e aplicação operacional

- Modais reais: novo crédito (cliente/fornecedor), aplicar crédito, abater por devolução.
- Tela `/financeiro/creditos` com listagem, filtros, detalhe e cancelamento.
- Drawer de título integrado aos modais (substitui toasts informativos).
- Backend: filtros em `GET /api/financeiro/creditos/`; serializer enriquecido; origens `PAGAMENTO_A_MAIOR`, `OUTROS`.
- Testes: `financeiroUi40142.test.tsx`, `test_financeiro_creditos_40142.py`.

## ERP 4.0.14.2.1 — Acabamento operacional de Créditos e exclusão segura de lançamentos manuais

- Tela Créditos com empty state limpo e botão único «Novo crédito».
- Drawer operacional: editar, cancelar (motivo), excluir (motivo), histórico formatado pt-BR.
- Flags backend: `pode_editar`, `pode_editar_completo`, `pode_excluir`, `possui_movimento`, `origem_manual`, etc.
- Endpoints: `PATCH /api/financeiro/creditos/{id}/`, `POST .../excluir/`, `POST .../contas-receber|pagar/{id}/excluir/`.
- Testes: `financeiroUi401421.test.tsx`, `test_financeiro_acabamento_401421.py`.

## ERP 4.0.14.2.2 — Correção de exclusão segura após estorno e refinamento dos drawers financeiros

- `pode_excluir` distingue movimento **ativo** vs **estornado**; saldo reaberto permite exclusão de manual.
- Flags: `possui_movimento_ativo`, `possui_apenas_movimentos_estornados`, `motivo_bloqueio_exclusao`.
- Drawers: histórico recolhido, ações agrupadas, títulos operacionais.
- Testes: `financeiroUi401422.test.tsx`, `test_financeiro_exclusao_401422.py`.

## ERP 4.0.14.3 — Gerar Contas a Receber a partir de NF-e autorizada (confirmação manual)

- Ponte **manual** entre NF-e autorizada e Contas a Receber — **sem automação** ao autorizar NF-e ou faturar.
- Wizard de preview com parcelas editáveis (duplicatas fiscais → parcelas financeiras).
- Endpoints: `GET .../financeiro/preview-contas-receber/`, `POST .../gerar-contas-receber/`, `GET .../contas-receber/`.
- Idempotência por `origem_tipo=NFE_SAIDA` + `origem_id`; título com origem **não excluível**.
- Cancelamento posterior da NF-e **não apaga** financeiro — alerta nos títulos vinculados.
- Testes: `test_nfe_saida_40143_gerar_contas_receber.py`, `nfeSaida40143.test.tsx`.

## ERP 4.0.14.4 — Gerar Contas a Pagar a partir de NF-e Entrada (confirmação manual)

- Ponte **manual** entre NF-e Entrada conferida e Contas a Pagar — **sem automação** na importação, vínculo de pedido ou conferência.
- Wizard de preview com parcelas editáveis (duplicatas/fatura do XML → parcelas financeiras).
- Endpoints: `GET .../financeiro/preview-contas-pagar/`, `POST .../gerar-contas-pagar/`, `GET .../contas-pagar/` em `nf-entradas-historicas-importadas`.
- Idempotência por `origem_tipo=NFE_ENTRADA` + `origem_id`; título com origem **não excluível**.
- Cancelamento posterior da NF-e Entrada **não apaga** financeiro — alerta nos títulos vinculados.
- Pedido de Compra vinculado é **contexto** — não altera pedido nem estoque.
- Testes: `test_nfe_entrada_40144_gerar_contas_pagar.py`, `nfeEntrada40144.test.tsx`.

## ERP 4.1 (futuro) — Multiempresa, matriz/filiais e multi-CNPJ

**Não implementado.** Planejado após operação em produção com dados reais.

## ERP 4.0.14.10.2 — Gestão de perfil de acesso do usuário no colaborador

- Badges de acesso na listagem (Superusuário, perfil, Sem perfil, Acesso inativo).
- Bloco Acesso ao sistema completo + modal **Editar acesso** (`PATCH .../acesso/`).
- Prontidão: superusuário não gera crítico de sem perfil; mensagem orienta Editar acesso.
- Testes: `test_colaborador_acesso_4014102.py`, `colaboradores4014102.test.tsx`.

## ERP 4.0.14.10.1 — Regra fiscal de entrada como validação de uso

- Entrada incompleta → aviso na prontidão; saída continua crítica.
- Bloqueio em preparar/finalizar NF-e Entrada fiscal via `validar_regra_fiscal_entrada_para_uso()`.
- Checklist separado saída/entrada; badge **Incompleta**; relatório com `avisos_entrada` e `bloqueios_por_fluxo`.
- Testes: `test_regras_fiscais_minimas_4014101.py`, `regrasFiscais4014101.test.tsx`.

## ERP 4.0.14.10 — Regras fiscais mínimas para produção

- Validação fiscal mínima na prontidão; checklist em `/regras-fiscais`.
- `GET /api/regras-fiscais/checklist-producao/`; relatório `pre_producao_*.json` com seção fiscal.
- Sem seed/migration de regra real; sem alteração de NF-e/XML/DANFE/BFR.
- Testes: `test_regras_fiscais_minimas_401410.py`, `regrasFiscais401410.test.tsx`.

## ERP 4.0.14.9.4.1 — Correção de nome exibido do usuário no Header/UserMenu/Minha conta

- `getUsuarioNomeExibicao` no frontend; invalidação de cache stale; login limpa contexto.
- Backend reforça `nome_exibicao` = nome do colaborador quando vinculado.
- Testes: `test_minha_conta_4014941.py`, `usuarioExibicao4014941.test.ts`, `header4014941.test.tsx`.

## ERP 4.0.14.9.4 — Minha conta, nome exibido e cabeçalho refinado

- `GET /api/app/contexto/` — `usuario.nome_exibicao` (colaborador → first+last → username); empresa com razão social no header.
- `GET/PATCH /api/minha-conta/` — dados da conta; PATCH permite e-mail e telefone (sem perfil/grupo/login).
- Header: empresa completa quando couber, menu com nome humano, aviso e-mail técnico em Minha conta.
- **Sem** multiempresa, troca de empresa, matriz/filial ou multi-CNPJ.
- Testes: `test_minha_conta_401494.py`, `header401494.test.tsx`, `minhaConta401494.test.tsx`.

## ERP 4.0.14.9.3 — Cabeçalho operacional: busca, empresa atual e menu do usuário

- Busca global: `GET /api/busca-global/?q=...` (cadastros, documentos, financeiro).
- Contexto do app: `GET /api/app/contexto/` — empresa atual (informativa), usuário, ambiente.
- `GET /api/minha-conta/` — dados da conta (sem alterar permissões).
- Header: busca funcional, nome da empresa, selo Homologação, menu do usuário (Minha conta / Alterar senha).
- **Sem** multiempresa, troca de empresa, matriz/filial ou multi-CNPJ.
- Testes: `test_busca_global_401493.py`, `header401493.test.tsx`.

## ERP 4.1 (futuro) — Fechamento fiscal/contábil e DF-e

**Não implementado nesta fase.** Módulo planejado para após início operacional do ERP com dados reais em produção.

Escopo futuro (referência):

- Central de DF-e; manifestação do destinatário; consulta/download de XMLs.
- Organização de XMLs de entrada e saída; pacote mensal para contador.
- Exportação de arquivos fiscais e relatórios contábeis; fechamento mensal.
- Conferência de documentos fiscais; ZIP por período; relatórios emitidas/recebidas.
- Integração futura com apuração fiscal; arquivos para contador.

## ERP 4.0.14.9.2 — Criação de usuário com senha inicial e redefinição por Admin

- Criar usuário em Colaboradores com **senha inicial** (hash Django); sem convite/SMTP.
- Validação e-mail, senha e confirmação (frontend + backend).
- `POST .../redefinir-senha/` — apenas Admin redefine senha de outro usuário.
- `POST /api/minha-conta/alterar-senha/` — usuário troca a própria senha com senha atual.
- Sem obrigatoriedade de troca no primeiro acesso; senha nunca retornada na API.
- Prontidão: usuário ativo sem senha utilizável, e-mail inválido, sem perfil.
- Procedimento documentado: `changepassword` / `createsuperuser` se único Admin esquecer senha.
- Testes: `test_colaborador_senha_401492.py`, `colaboradores401492.test.tsx`.

## ERP 4.0.14.9.1 — Acesso ao sistema na tela de Colaboradores

- Separação UX: **Dados** / **Funções internas** / **Acesso ao sistema** (funções ≠ perfil/grupo Django).
- Coluna **Acesso** na listagem com badges e ações (Criar usuário, Definir perfil, Desativar, Reenviar convite).
- Endpoints: `POST .../criar-usuario/` (perfil obrigatório), `.../vincular-usuario/`, `.../definir-perfil-acesso/`, `.../desativar-acesso/`, `.../reenviar-convite/`, `GET .../perfis-acesso/`.
- Serializer com `acesso_status`, `perfil_acesso_label`, flags `pode_*`, sugestão de perfil.
- Prontidão: crítico usuário ativo sem perfil com orientação «Cadastros > Colaboradores > Editar > Acesso ao sistema».
- Testes: `test_colaborador_acesso_401491.py`, `colaboradores401491.test.tsx`; ajuste `test_colaborador_usuario_40148.py`.

## ERP 4.0.14.9 — Pré-produção, limpeza segura e checklist final

- Prontidão ampliada: CR/CP duplicados, usuários sem perfil, admin ausente, e-mails duplicados, produtos, fiscal.
- Dry-run ampliado: preservados (produtos, NCM, grupos, contas…) e candidatos (financeiro, estoque, comercial, fiscal).
- Produtos **nunca** candidatos à limpeza; bloqueio explícito na execução.
- Execução bloqueada sem backup, confirmação, prontidão crítica ou documentos reais.
- `python manage.py gerar_relatorio_pre_producao` → `reports/pre_producao_YYYYMMDD_HHMMSS.json`.
- Testes: `test_pre_producao_40149.py`.

## ERP 4.0.14.8 — Preparação para produção: numeração CR/CP, vencimento, usuários e limpeza segura

- Numeração transacional `CR-AAAA-000001` / `CP-AAAA-000001` (`gerar_numero_titulo_financeiro`).
- Vencimento obrigatório na criação; exibição em relatórios/PDF via `vencimento_exibicao.py` (sem «—» em título válido).
- Colaboradores: criar usuário (`POST /api/colaboradores/{id}/criar-usuario/`), desativar acesso, status de acesso.
- Grupos: `create_groups` estendido (financeiro, compras, estoque, produtos, consulta).
- Comandos: `verificar_prontidao_producao` (leitura), `preparar_limpeza_producao` (dry-run + execução com backup e confirmação `APAGAR_DADOS_TESTE`).
- Testes: `test_financeiro_40148.py`, `test_colaborador_usuario_40148.py`, `test_prontidao_limpeza_40148.py`.

## ERP 4.0.14.6 — Relatórios financeiros operacionais

- Menu **Financeiro > Relatórios** (`/financeiro/relatorios`).
- Endpoints: `GET /api/financeiro/relatorios/contas-receber|contas-pagar|fluxo-previsto|categorias|clientes|fornecedores/`.
- Somente leitura; filtros na URL; baixa via modal existente com confirmação.
- Exportação CSV: pendência (não obrigatória nesta fase).
- Testes: `test_financeiro_relatorios_40146.py`, `financeiroRelatorios40146.test.tsx`.

## ERP 4.0.14.7 — Motor central de relatórios e geração de PDF operacional

- `apps.relatorios`: `ReportDefinition`, `ReportPdfRenderer`, `ReportExportService` (ReportLab, isolado do fiscal).
- PDF financeiro: `GET /api/financeiro/relatorios/*/pdf/` (6 relatórios).
- Frontend: `RelatorioPdfActions` + `relatorioPdfDownload.ts`.
- Testes: `test_financeiro_relatorios_pdf_40147.py`, `financeiroRelatorios40147.test.tsx`.
- Arquitetura documentada para expansão (Fiscal, Comercial, Estoque, etc.) — sem implementar nesta fase.

## ERP 4.0.14.6.1 — Ajustes de consistência dos relatórios financeiros

- Filtros unificados em `RelatorioFiltrosPanel` (sem duplicidade “Filtros avançados” + “Filtros do relatório”).
- Parâmetros API: `incluir_quitados`, `incluir_cancelados`, `incluir_sem_saldo` (padrão `false`).
- Exibição padrão prioriza títulos ativos; histórico e linhas zeradas só com flags.
- Cards de aberto/vencido isolados de cancelados/quitados; categorias com colunas Original / Em aberto / Baixado / Total.
- Testes: `test_financeiro_relatorios_401461.py`, `financeiroRelatorios401461.test.tsx`.

## ERP 4.0.14.5 — Visão geral financeira, vencimentos e alertas operacionais

- Endpoint `GET /api/financeiro/resumo/` com cards, alertas, resumo por conta/categoria e créditos disponíveis.
- Tela `/financeiro` como visão geral operacional com período selecionável.
- Filtros avançados em Contas a Receber e Contas a Pagar (vencimento, origem, categoria, origem fiscal cancelada).
- Badge «Origem cancelada» na listagem quando NF-e de origem cancelada.
- Testes: `test_financeiro_resumo_40145.py`, `financeiro40145.test.tsx`.

## ERP 4.0.14.4.1 — Separação pendências operacionais × Contas a Pagar NF-e Entrada

- Financeiro da NF-e Entrada é **independente** da aplicação de estoque e da resolução de equivalências.
- Pendências operacionais (produto, estoque, pedido, equivalência) **não bloqueiam** Contas a Pagar.
- Bloqueios financeiros reais: fornecedor, valor, cancelamento, duplicidade, XML inválido.
- Geração com pendências operacionais exige **ciência explícita** do usuário no wizard.
- Salvar conferência com pendências mantém divergências abertas e **não gera** financeiro automaticamente.
