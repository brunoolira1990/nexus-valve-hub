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
| NF-e entrada própria | Não iniciado | Média | — | Devolução/recusa, retorno remessa, vínculo NF saída | Entrada Própria 1 |
| Remessas | Não iniciado | Média | CFOPs no catálogo auxiliar de saída | Modelo, emissão, retorno, controle pendente | Remessa 1 |
| Estoque / rastreabilidade | Em evolução | Alta | AtendimentoEstoque, aplicação física, CQ + rastreio | Kardex, estorno, relatório ponta a ponta | Estoque 3.13 |
| Qualidade | Concluído parcial | Média | CF, CQ, busca corrida, vínculo conferência | Relatório CQ, dashboard pendências | Qualidade 4 |
| Financeiro | Não iniciado / Futuro | Alta | Referências em pedido compra | AR/AP, parcelas, fluxo de caixa | Financeiro 1 |
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
- **NF-e Saída 3.6 (certificado A1 + status SEFAZ):** camada `apps/fiscal/nfe_integracao/adapters/` (nfelib, PyNFe, certificado_a1, sefaz_status_service); modelo `NFeSefazStatusConsulta`; API `POST /api/nfe-sefaz-status/consultar/`, `GET /api/nfe-sefaz-status/`, `GET /api/empresas/{id}/validar-certificado-nfe/`; UI `/nfe-sefaz`; homologação SP via `ComunicacaoSefaz.status_servico('nfe')`; sem emissão NF-e
- **NF-e Saída 3.5.3 (prontidão da conferência):** `status_conferencia` separado do status fiscal (`EM_CONFERENCIA`, `COM_PENDENCIAS`, `CONFERIDA`, `PRONTA_PARA_EMISSAO`); `GET .../prontidao/`, `POST .../validar-conferencia/`, `POST .../marcar-pronta/`; serviço `nfe_saida_prontidao.py`; eventos `CONFERENCIA_*`, `PRONTA_PARA_EMISSAO`, `PRONTIDAO_INVALIDADA`; UI na conferência e listagem; invalidação ao salvar complementos ou atualizar fiscal; sem SEFAZ/estoque/financeiro; migration `0023`

### Falta

- Transmissão SEFAZ / XML autorizado / DANFE definitivo
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
