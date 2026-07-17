# Modelo operacional Nexus — ERP 4.0.10

Documento oficial do modelo operacional da Nexus Válvulas no ERP. Define como venda, compra, NF-e, estoque e expedição se relacionam **sem assumir estoque obrigatório antes da venda**.

---

## 1. Premissa operacional

A Nexus trabalha majoritariamente com **venda sob demanda** e **atendimento flexível**.

O produto pode:

1. Entrar antes da NF-e de saída (Fluxo A).
2. Ser retirado no fornecedor depois da NF-e de saída (Fluxo B).
3. Ser entregue direto do fornecedor ao cliente.
4. Ser retirado no fornecedor e entregue na transportadora.
5. Atender parcialmente uma venda.
6. Atender várias vendas com uma mesma compra.
7. Sobrar para estoque.
8. Ter NF-e entrada conciliada depois da saída.

**Regra principal:** o ERP controla **origem e atendimento do item**, não apenas saldo físico.

O estoque existe, mas **não é o bloqueio central** do fluxo comercial/fiscal.

---

## 2. Fluxo A — Entrada antes da saída

```
Pedido de Venda → Pedido de Compra (se necessário) → NF-e Entrada (importada/conferida)
→ Produto disponível/conferido → Faturamento → NF-e Saída → Expedição/entrega
```

Indicadores típicos:

- `tipo_atendimento`: `ENTRADA_CONCILIADA` ou `ESTOQUE_PROPRIO`
- `status_entrada_fiscal`: `CONCILIADA`
- `origem_fisica`: `ESTOQUE_PROPRIO`
- `destino_fisico`: `CLIENTE` ou `TRANSPORTADORA`

---

## 3. Fluxo B — Saída antes da entrada

```
Pedido de Venda → Faturamento → NF-e Saída (autorizada) → Retirada no fornecedor
→ Entrega ao cliente/transportadora → NF-e Entrada posterior → Conciliação
→ (Futuro) Contas a pagar da NF-e Entrada
```

Indicadores típicos:

- `tipo_atendimento`: `RETIRADA_FORNECEDOR`, `ENTREGA_DIRETA_FORNECEDOR_CLIENTE` ou `RETIRADA_FORNECEDOR_TRANSPORTADORA`
- `status_entrada_fiscal`: `PENDENTE` até a NF-e Entrada chegar
- Após conciliação futura: `CONCILIADA`

**Importante:** a NF-e Saída **não é bloqueada** automaticamente por ausência de NF-e Entrada.

---

## 4. Fluxo C — Misto

- Parte do item já entrou e está conciliada.
- Parte será retirada no fornecedor.
- Parte pode ficar pendente.
- Conciliação ocorre por item/quantidade.

Indicador: `tipo_atendimento`: `MISTO`

---

## 5. Compra não é 1:1 com saída

Uma **Pedido de Compra** pode atender:

- uma venda;
- várias vendas;
- parte de uma venda;
- estoque (sobra);
- expedição direta;
- saldo futuro.

O vínculo é modelado em **`AlocacaoAtendimento`** (N:1 entre alocações e itens de compra/entrada).

---

## 6. Estoque não é bloqueio central

| Conceito | Modelo existente | Papel |
|----------|------------------|-------|
| Compromisso NF saída antecipada | `AtendimentoEstoque` | Vínculo NF saída ↔ conferência entrada; **sem baixa física automática** |
| Saldo físico | `EstoqueCorrida` | Consulta e aplicação futura |
| Intenção operacional | `AlocacaoAtendimento` (4.0.10) | Tipo de atendimento, entrada fiscal, origem/destino físico |

Nenhum desses modelos **bloqueia emissão NF-e** por falta de entrada física nesta fase.

---

## 7. Tipos de atendimento (`tipo_atendimento`)

| Valor | Descrição |
|-------|-----------|
| `ESTOQUE_PROPRIO` | Item atendido do estoque próprio |
| `ENTRADA_CONCILIADA` | Entrada fiscal já conciliada |
| `RETIRADA_FORNECEDOR` | Retirada no fornecedor após saída |
| `ENTREGA_DIRETA_FORNECEDOR_CLIENTE` | Fornecedor entrega direto ao cliente |
| `RETIRADA_FORNECEDOR_TRANSPORTADORA` | Fornecedor → transportadora |
| `COMPRA_VINCULADA` | Compra vinculada, destino a definir |
| `MISTO` | Cenário misto por item |
| `NAO_DEFINIDO` | Padrão seguro quando não informado |

Definidos em `apps/fiscal/modelo_operacional.py` → `TipoAtendimentoItem`.

---

## 8. Status de entrada fiscal (`status_entrada_fiscal`)

| Valor | Uso |
|-------|-----|
| `NAO_APLICAVEL` | Sem relação com entrada de fornecedor |
| `PENDENTE` | NF-e Entrada ainda não recebida/conciliada |
| `RECEBIDA` | XML/importação recebida, conciliação pendente |
| `CONCILIADA` | Entrada alinhada com compra/venda/expedição |
| `DIVERGENTE` | Divergência quantidade/produto/valor |
| `CANCELADA` | Entrada cancelada/desconsiderada |

---

## 9. Origem e destino físico

**Origem (`origem_fisica`):** `ESTOQUE_PROPRIO`, `FORNECEDOR`, `TRANSPORTADORA`, `CLIENTE`, `TERCEIRO`, `NAO_DEFINIDA`

**Destino (`destino_fisico`):** `CLIENTE`, `TRANSPORTADORA`, `ESTOQUE_PROPRIO`, `TERCEIRO`, `NAO_DEFINIDO`

Preparam a **Expedição futura** (retirada, entrega direta, coleta, romaneio).

---

## 10. Vínculos entre documentos

Entidades relacionadas (todas opcionais em `AlocacaoAtendimento`):

| Documento | Campo FK |
|-----------|----------|
| Item Pedido de Venda | `pedido_venda_item` |
| Item Faturamento | `faturamento_item` |
| Item Pedido de Compra | `pedido_compra_item` |
| Item NF-e Entrada | `nf_entrada_item` |
| Item NF-e Saída | `item_nf_saida` |
| Fornecedor | `fornecedor` |
| Produto | `produto` (obrigatório) |

Quantidades: `quantidade_necessaria`, `quantidade_atendida`, `quantidade_pendente`.

---

## 11. Conciliação futura da NF-e Entrada

Base preparada; **conciliação completa não implementada** na 4.0.10.

Futuro: vincular NF-e Entrada com PC, PV, FAT, NF-e Saída, expedição e quantidades.

Divergências futuras: quantidade, produto, valor, fornecedor, impostos, NF-e não localizada.

Helpers read-only: `marcar_entrada_fiscal_pendente()`, `marcar_entrada_fiscal_conciliada()` — retornam dict, **não alteram banco**.

---

## 12. Regras para NF-e Saída

Permitido (e já suportado pelo ERP):

1. NF-e saída com entrada conciliada.
2. NF-e saída com entrada pendente.
3. NF-e saída com retirada no fornecedor.
4. NF-e saída com entrega direta fornecedor → cliente.
5. NF-e saída com entrega fornecedor → transportadora.

A validação fiscal (`validacao_nfe_saida.py`) **não exige** NF-e Entrada conciliada.

UI futura: avisos operacionais (entrada pendente, retirada fornecedor, conciliação posterior).

---

## 13. Expedição futura

Expedição **não** será apenas “saída de estoque”.

Controlará: retirada em fornecedor, entrega direta, motorista, volumes, DANFE, PC, romaneio, comprovantes, status de entrada fiscal.

Tipos futuros: `ESTOQUE_PROPRIO`, `RETIRADA_FORNECEDOR`, `ENTREGA_DIRETA_FORNECEDOR_CLIENTE`, `RETIRADA_FORNECEDOR_TRANSPORTADORA`, `MISTO`.

Status futuros: `AGUARDANDO_SEPARACAO`, `AGUARDANDO_RETIRADA_FORNECEDOR`, `MOTORISTA_ENVIADO`, `RETIRADO_FORNECEDOR`, `EM_TRANSITO`, `ENTREGUE_TRANSPORTADORA`, `ENTREGUE_CLIENTE`, `ENTRADA_FISCAL_PENDENTE`, `ENTRADA_FISCAL_CONCILIADA`, `OCORRENCIA`, `CANCELADO`.

---

## 14. Regras financeiras futuras

| Origem | Gera título? |
|--------|----------------|
| Pedido de Venda | Não — origem comercial |
| Pedido de Compra | Não — intenção operacional |
| NF-e Saída autorizada **produção** | Sim → Contas a Receber |
| NF-e Saída homologação | Não |
| NF-e Entrada fornecedor | Sim → Contas a Pagar |

Uma NF-e Entrada pode estar relacionada a **várias vendas** atendidas pela mesma compra.

**4.0.10:** nenhum título financeiro é gerado.

---

## 15. Impactos em BI (futuro)

Indicadores planejados:

- **Comercial:** vendas com entrada pendente, retirada fornecedor, entrega direta.
- **Compras:** compras vinculadas, saldo a alocar, entrada pendente.
- **Fiscal:** NF-e saída com entrada pendente, conciliação pendente, divergências.
- **Expedição:** aguardando retirada, em trânsito, entregue.
- **Financeiro:** recebíveis por NF-e saída produção; pagamentos por NF-e entrada.

---

## 16. Implementação técnica (4.0.10)

| Artefato | Caminho |
|----------|---------|
| Enums + helpers | `backend/apps/fiscal/modelo_operacional.py` |
| Modelo | `AlocacaoAtendimento` em `backend/apps/fiscal/models.py` |
| Migration | `0034_alocacao_atendimento_modelo_operacional_4010` |
| Testes | `backend/apps/fiscal/tests/test_modelo_operacional_4010.py` |
| Tokens UI | `frontend/src/design-system/tokens.ts` |

**Não implementado nesta fase:**

- Expedição completa
- Conciliação NF-e Entrada
- Contas a pagar / receber
- Movimentação de estoque
- Bloqueio NF-e por entrada
- Telas obrigatórias preenchendo alocação
- API pública de alocação (somente model + helpers)

---

## 18. Visibilidade operacional (ERP 4.0.11)

Fase de **leitura apenas**: exibir resumo de `AlocacaoAtendimento` em Pedido de Venda, Faturamento e NF-e Saída.

### Onde aparecem os badges

| Tela | Comportamento |
|------|----------------|
| Listagem PV | Resumo enxuto (máx. 2 badges; «não definido» quando sem alocação) |
| Detalhe/modal PV (aba Resumo) | Card «Atendimento operacional» com badges e mensagem |
| Painel Faturamento | Resumo compacto do pedido |
| Listagem NF-e Saída | Badges compactos na coluna Atendimento (somente se `tem_alocacao`) |
| Conferência NF-e Saída | Card na aba Resumo |

### Status distintos (não confundir)

| Camada | Exemplo |
|--------|---------|
| **Fiscal** | Autorizada homologação · cStat 100 |
| **Comercial** | Status do pedido (Aberto, Faturado…) |
| **Operacional** | Retirada fornecedor · Entrada pendente |
| **Financeiro** | Em preparação (futuro) |

A modal do **Pedido de Venda** (ERP 4.0.13.2) separa status comercial, fiscal e operacional em abas distintas. Referências internas como `RASCUNHO-FAT-*` podem aparecer em área técnica secundária, mas **não** substituem a identidade fiscal amigável da NF-e (ex.: «NF-e Homologação nº … — Série …») após autorização em homologação ou produção.

O **PDF comercial do Pedido de Venda** (ERP 4.0.13.2.1) contém pedido, condições, itens e resumo de faturamento comercial — **sem** seção NF-e vinculada, DANFE, XML, cStat ou dados de homologação. A identidade fiscal amigável permanece na modal do ERP (aba NF-e / Fiscal). Referências internas como `RASCUNHO-FAT` não aparecem no PDF enviado ao cliente.

**Duplicatas da NF-e** (ERP 4.0.13.3) representam dados de cobrança informados no XML/DANFE (fatura, vencimento, valor por parcela) a partir da condição de pagamento do pedido/faturamento. **Não** significam geração de financeiro automático (contas a receber, boleto ou baixa) nesta fase. O PDF comercial do pedido continua sem duplicatas fiscais; o DANFE e a aba NF-e / Fiscal exibem essas informações quando aplicável.

### Ciclo de vida pré-autorização NF-e (ERP 4.0.13.6.8)

| Situação | Ação permitida | Não é |
|----------|----------------|-------|
| Pedido faturado + NF-e rascunho/conferência **sem** protocolo SEFAZ | **Estornar faturamento** (reverte qty, pedido editável) + descarte interno da NF-e | Cancelamento SEFAZ |
| NF-e rascunho isolada sem autorização | **Descartar rascunho** (libera faturamento para nova NF-e; qty do pedido mantida) | Exclusão física do registro |
| NF-e autorizada homologação/produção ou com protocolo | Bloqueio de estorno/descarte simples | — |

Descarte interno e estorno **não** transmitem eventos à SEFAZ, **não** geram financeiro, **não** movimentam estoque e **não** criam expedição. Cancelamento fiscal e Carta de Correção serão fases **4.0.13.6.9** e **4.0.13.6.10**.

**Correção de Material dos Produtos e higienização de dados de teste/dev** (ERP 4.0.13.5.2): a API de produtos expõe `material` e `material_label` quando o valor existe no banco; salvar ou PATCH parcial **não** deve apagar Material existente se o campo vier vazio por engano. A listagem e o formulário usam o rótulo amigável. A limpeza de dados de teste roda **somente** em ambiente seguro (`local`, `development`, `homologacao`, `test` ou `DEBUG=True`), com **dry-run** obrigatório por padrão (`python manage.py limpar_dados_teste_nexus --dry-run`) e execução apenas com `--confirmar LIMPAR_DADOS_TESTE_NEXUS`. Critérios conservadores: PV no padrão `PV-[hash]` (ex.: `PV-3c6d60`), cliente «Cli», produto «PROD NF» — preservando PV oficial `PV-YYYYMMDD-000X`, NF-e autorizada, XML autorizado, apuração e produtos reais (inclusive sem Material por bug anterior). Sem cascade cego; exclusão pelo app retorna mensagem clara quando há vínculo (409).

**Checklist fiscal de pré-homologação** (ERP 4.0.13.5 / 4.0.13.5.1) valida, antes de um novo teste de NF-e em homologação: pedido/faturamento, duplicatas, XML preliminar (`cobr`/`dup`/`pag`), renderização DANFE, exclusão da apuração, Reforma Tributária em preparação, ausência de efeitos em financeiro/estoque/expedição e PDF comercial limpo. Status geral: `aprovado`, `aprovado_com_alertas` ou `bloqueado`. A validação **não transmite** NF-e, **não altera** XML autorizado e **não emite** automaticamente. Endpoints: `POST /api/nf-saidas/{id}/checklist-homologacao/`, `POST /api/nf-saidas/checklist-homologacao/`, `POST /api/pedidos-venda/{id}/checklist-nfe-homologacao/`. No drawer NF-e Saída, o botão **Validar** abre o checklist e exibe badge de pré-homologação (aprovada ou bloqueada). A validação do DANFE usa o mesmo fluxo do botão **DANFE** (`gerar_preview_danfe_nfe_saida`); NF-e homologada autorizada renderiza pelo XML autorizado sem exigir status rascunho.

Ideia futura (não implementada): «PDF interno do pedido com dados fiscais» para uso operacional.

### Limitações da 4.0.11 (superadas na 4.0.12 para CRUD)

- Na 4.0.11 não havia CRUD; a 4.0.12 adiciona gestão explícita (ver seção 19).
- Badges não bloqueiam ações nem alteram NF-e/estoque/financeiro.

### Implementação

| Camada | Artefato |
|--------|----------|
| Backend | `apps/comercial/services/resumo_atendimento_operacional.py` |
| API | `resumo_atendimento_operacional` em PV, NF-e, `resumo-faturamento` |
| Frontend | `AtendimentoOperacionalBadge`, `AtendimentoOperacionalResumo`, `AtendimentoOperacionalInline` |

---

## 19. Gestão operacional por item (ERP 4.0.12)

Camada de **intenção operacional**: o usuário registra, consulta e ajusta como cada item/quantidade será atendido, **sem efeitos automáticos** em estoque, financeiro, expedição ou NF-e.

### Regra central

`AlocacaoAtendimento` não movimenta estoque, não gera contas a pagar/receber, não cria expedição, não altera apuração/precificação/emissão NF-e/XML/DANFE e não promove documentos da base DF-e importada.

### Gestão por item/quantidade

| Campo / conceito | Uso |
|------------------|-----|
| `quantidade_necessaria`, `quantidade_atendida`, `quantidade_pendente` | Atendimento parcial e misto |
| `tipo_atendimento`, `status_entrada_fiscal` | Intenção e entrada fiscal (pendente/conciliada…) |
| `origem_fisica`, `destino_fisico` | Rastreio físico |
| `pedido_compra_item`, `nf_entrada_item` | Vínculos operacionais opcionais |
| `nf_entrada_historica_item`, `cte_historico_importado` | Rastreabilidade base importada (sem efeito automático) |
| `fornecedor`, `observacao_operacional` | Contexto humano |

Múltiplas alocações por item são permitidas; a soma de `quantidade_necessaria` não pode ultrapassar a quantidade do item no PV.

### API

| Endpoint | Uso |
|----------|-----|
| `GET/POST /api/alocacoes-atendimento/` | Listagem paginada e criação |
| `GET/PATCH/DELETE /api/alocacoes-atendimento/{id}/` | Detalhe, edição, exclusão |
| `GET /api/pedidos-venda/{id}/alocacoes-atendimento/` | Lista + resumo do PV (`?faturamento_id=` opcional) |
| `GET /api/nf-saidas/{id}/alocacoes-atendimento/` | Lista + resumo da NF-e |

Filtros: `pedido_venda`, `pedido_venda_item`, `faturamento`, `nfe_saida`, `produto`, `fornecedor`, enums.

### UI

| Tela | Acesso |
|------|--------|
| Pedido de Venda (modal) | Aba «Atendimento operacional» + resumo na aba Resumo |
| Faturamento do pedido | «Gerenciar atendimento» (seção expansível) |
| Conferência NF-e Saída | «Gerenciar atendimento» na aba Resumo |

Alertas fixos: operação informativa; entrada pendente não bloqueia NF-e; vínculo base importada sem efeito automático.

### Implementação

| Camada | Artefato |
|--------|----------|
| Service | `apps/comercial/services/alocacao_atendimento_service.py` |
| API | `AlocacaoAtendimentoViewSet`, actions aninhadas PV/NF-e |
| Migration | `0036_alocacao_atendimento_vinculos_4012` (NF-e histórica + CT-e histórico) |
| Frontend | `alocacaoAtendimento.ts`, `AlocacaoAtendimentoGerenciarPanel` |
| Testes | `test_alocacao_atendimento_4012.py`, `alocacaoAtendimento4012.test.tsx` |

O resumo da 4.0.11 passa a refletir alocações **reais** criadas pelo usuário (read-only no resumo).

---

## 20. Vínculo assistido DF-e/compra (ERP 4.0.13)

Substitui campos manuais de ID por **busca assistida** no formulário de alocação.

### Endpoints de opções (leves, sem XML)

| Endpoint | Uso |
|----------|-----|
| `GET /api/alocacoes-atendimento/opcoes/fornecedores/` | Autocomplete fornecedor |
| `GET .../opcoes/pedidos-compra/` | PC por número/fornecedor |
| `GET .../opcoes/pedidos-compra-itens/` | Item de PC (filtro `pedido_compra_id`, `produto_id`) |
| `GET .../opcoes/nfe-entrada-importada/` | NF-e base importada produção/autorizada (`somente_conferidas`) |
| `GET .../opcoes/nfe-entrada-importada-itens/` | Item da NF-e histórica |
| `GET .../opcoes/cte-importado-conferido/` | CT-e conferido/apto operacional |

### Regras de elegibilidade (validação ao salvar)

- NF-e homologação **não** pode ser vinculada.
- CT-e deve estar **conferido/preparado**, produção, autorizado; divergente/ignorado/homologação bloqueados.
- Item de PC com produto diferente do da alocação é **bloqueado** quando ambos têm `produto_id`.
- Vínculo **não** gera CP/CR, estoque, expedição, apuração ou alteração de NF-e.

### UI

- `AlocacaoAtendimentoVinculosForm` + `AsyncAutocomplete`
- Lista de alocações exibe `vinculos` (nomes legíveis)
- Aviso: «Vincular documentos não gera financeiro/estoque/expedição»

---

## 21. Atendimentos Operacionais (ERP 4.0.13.1)

Substitui **visualmente** a tela legada «Atendimentos de Estoque» como acompanhamento operacional por item. A rota `/atendimentos-estoque` permanece por compatibilidade; o menu exibe **Atendimentos Operacionais**.

### Fonte de dados

- **`AlocacaoAtendimento`** (criada na 4.0.12/4.0.13) — não o modelo `AtendimentoEstoque` (compromisso NF saída antecipada + vínculo conferência).
- **Saldos de Estoque** continuam na tela `/estoque` (estoque físico real).

### API

| Endpoint | Uso |
|----------|-----|
| `GET /api/atendimentos-operacionais/` | Listagem paginada consolidada (PV, FAT, NF-e saída, cliente, vínculos, badges) |
| `GET /api/atendimentos-operacionais/kpis/` | Cards informativos (mesmos filtros da listagem) |
| `GET /api/atendimentos-operacionais/{id}/` | Detalhe resumido de uma alocação |
| `PATCH /api/alocacoes-atendimento/{id}/` | Edição (mesmo formulário da 4.0.12/4.0.13) |

Filtros: `search`, `cliente_id`, `produto_id`, `tipo_atendimento`, `status_entrada_fiscal`, `somente_pendentes`, `somente_sem_compra`, `tem_nfe_entrada_vinculada`, `tem_cte_vinculado`, período (`data_inicio`/`data_fim`), entre outros.

### O que **não** faz

- Não movimenta estoque, não reserva/baixa saldo.
- Não gera financeiro (CP/CR), expedição ou rateio de frete.
- Não altera NF-e, XML/DANFE, apuração, precificação ou regras fiscais.
- Não promove Base DF-e Importada automaticamente.

### UI

- Página `AtendimentosEstoque.tsx` (título **Atendimentos Operacionais**): filtros amigáveis (autocomplete), KPIs clicáveis, tabela de alocações, modal `AtendimentoOperacionalEditModal`.
- Serviço frontend `atendimentosOperacionais.ts`.

---

## 22. Cadastro rápido e quantidade no Pedido de Venda (ERP 4.0.13.6)

Antes do Financeiro Base, o fluxo comercial/compras ganhou **cadastro inline** de entidades ausentes e correção da **quantidade travada em 1** no Pedido de Venda.

### Cadastro rápido (sem efeitos colaterais)

| Entidade | Telas | Endpoint |
|----------|-------|----------|
| Cliente | Proposta, Pedido de Venda | `POST /api/clientes/` |
| Fornecedor | Pedido de Compra, Alocação de Atendimento | `POST /api/fornecedores/` |
| Produto (MANUAL) | Proposta, Pedido de Venda, Pedido de Compra | `POST /api/produtos/` |

Comportamento:

1. Usuário busca no autocomplete; se não encontrar, clica **«Cadastrar novo»**.
2. Modal compacto com campos mínimos; validação de CNPJ e bloqueio de duplicidade por CNPJ.
3. Após salvar: entidade selecionada no formulário pai; dados já preenchidos preservados.
4. Produto sem NCM pode ser usado em proposta/pedido, com alerta antes da NF-e (não inventa NCM).

**Não gera:** financeiro (CP/CR), estoque, expedição, NF-e, apuração ou vínculo fiscal automático.

Componentes: `ClienteComercialField`, `ProdutoComercialField`, `FornecedorPedidoCompraField`, `FornecedorOpcaoField`.

> **ERP 4.0.13.6.1:** cadastro rápido **suspenso temporariamente na UI** (autocomplete puro) para estabilizar Pedido/Proposta/Compra. Endpoints de cadastro permanecem; reintrodução em fase isolada.

---

## 23. Estabilização Pedido / Faturamento / NF-e (ERP 4.0.13.6.1)

Hotfix de regressões pós-4.0.13.6:

| Regra | Comportamento |
|-------|----------------|
| Pedido aberto | Itens e quantidade editáveis; total recalcula com desconto |
| Pedido faturado | Itens read-only; aviso de bloqueio |
| Valor faturado | Soma qty faturada × preço **menos desconto proporcional** |
| Faturamento inconsistente | `inconsistencias` no resumo; bloqueia nova NF-e na UI |
| Estorno | `POST .../estornar/` quando NF-e **não** autorizada; reverte qty faturada |
| Vínculo órfão | `POST .../reparar-vinculo-nfe/` ou estorno |
| DANFE conferência | Layout restaurado (commit `08a7170`) |

**Não gera:** financeiro, estoque, expedição, transmissão SEFAZ, alteração de XML autorizado ou apuração.

### Quantidade editável no Pedido de Venda

| Situação | Quantidade |
|----------|------------|
| Pedido aberto/aprovado/pendente, item sem faturamento | Editável (decimal conforme unidade) |
| Pedido faturado ou cancelado | Read-only + aviso «Pedido faturado. Itens bloqueados…» |
| Item parcialmente faturado | Quantidade mínima = quantidade já faturada |

Regras backend: `conversao_item_comercial.py` (quantidade > 0); `pedido_venda_bloqueio.py` (bloqueio pós-faturamento); conversão proposta→pedido preserva quantidade original.

---

## 23. Layout DANFE de conferência (ERP 4.0.13.5.3 / 4.0.13.6.13A)

O DANFE oficial (conferência, rascunho, preview, homologação autorizada e reimpressão) usa **exclusivamente BrazilFiscalReport (BFR)** via `danfe_render.py` → `gerar_danfe_bfr_oficial`.

| Aspecto | Comportamento |
|---------|----------------|
| Renderizador | **BFR** (`DANFE_RENDERER_OFICIAL=BFR`) — único caminho oficial |
| Estrutura | Canhoto → cabeçalho → destinatário → Fatura/Duplicata → impostos → transportador → produtos → dados adicionais |
| Duplicatas | Tabela Nº / Vencimento / Valor (4.0.13.3); overflow em dados adicionais quando >10 parcelas |
| Marca d'água | «DANFE DE CONFERÊNCIA — SEM VALOR FISCAL» via `DanfeNexus` |
| Fallback HTML/WeasyPrint | **Bloqueado** (`DANFE_ALLOW_HTML_FALLBACK=false`) — não gera PDF alternativo |
| Falha BFR | Erro 503 + log `[DANFE_BFR_ERROR]`; emissão bloqueada se `DANFE_BLOCK_EMISSION_IF_BFR_FAILS=true` |
| PDF comercial PV | Permanece separado (ReportLab) — sem bloco NF-e/DANFE |

**Não faz:** transmitir NF-e, alterar XML autorizado, gerar financeiro, movimentar estoque, usar HTML/WeasyPrint como fallback silencioso.

Arquivos oficiais: `nfe_integracao/danfe_brazil_fiscal_report.py`, `danfe_render.py`, `danfe_bfr_log.py`.

Renderizadores legados removidos (4.0.13.6.13A): templates HTML `modelo55_conferencia.*`, `danfe_modelo55_html.py`, `danfe_modelo55_conferencia.py`, `danfe_moc_matriz_a4_retrato.py`.

---

## 17. Próximas fases recomendadas

1. **4.1.x** — Conciliação parcial NF-e Entrada ligada a alocações.
2. **4.2.x** — Módulo Expedição (tipos/status documentados acima).
3. **4.3.x** — Financeiro: CR da NF-e Saída produção; CP da NF-e Entrada.

---

## 18. Organização DF-e (ERP 4.0.10.1)

### Classificação oficial

| Categoria | Uso |
|-----------|-----|
| **OPERACIONAL** | NF-e/CT-e geridos no fluxo vivo do ERP (emissão, conferência, futura conciliação). |
| **BASE_DFE_IMPORTADA** | XML importado para apuração, contábil, BI, precificação e histórico comercial — **sem** estoque, financeiro, expedição ou pedido automáticos. |
| **HOMOLOGACAO** | Teste SEFAZ, sem valor fiscal. |
| **RECEBIDO_DFE_FUTURO** / **FUTURO_DFE_RECEBIDO** | Reservado ao Monitor DF-e (distribuição SEFAZ) — não implementado. |
| **CONFERIDO** (estado) | NF-e entrada importada revisada — apta a promoção futura; não gera financeiro/estoque automaticamente. |

### Regra absoluta — homologação

Documentos de homologação **nunca** entram em:

- apuração fiscal;
- base contábil oficial;
- financeiro;
- precificação oficial;
- BI fiscal oficial.

Helpers: `apps/fiscal/dfe_classificacao.py` (`pode_entrar_apuracao`, `pode_alimentar_precificacao`, `pode_gerar_efeito_operacional`).

### Base importada × operacional

A base DF-e importada **alimenta** fiscal, contábil, gerencial e precificação. **Não** gera, por padrão, estoque, contas a pagar/receber, faturamento, expedição ou conciliação automática.

Detalhamento: `docs/base-dfe-importada.md`.

### ERP 4.0.10.2.1 — separação UX importação

- **Base importada** = único ponto de “Selecionar XMLs” (NF-e entrada/saída, CT-e).
- **NF-e Entrada operacional** = entradas conferidas/promovidas + **entrada própria** (diferente de XML de fornecedor). XML de **entrada própria já emitida** pela empresa (ex.: devolução/recusa) importa por ação dedicada «Importar entrada própria já emitida» — status importada/pendente de conferência, **sem** financeiro, estoque ou expedição automáticos.
- **CT-e Entrada operacional** = acompanhamento operacional; **não** é emissão manual de CT-e nem importador XML.
- **CT-e importado (base)** = XML na base; alimenta apuração/BI/precificação quando produção/autorizado.
- **CT-e conferido** = revisado na base (`status_conferencia=CONFERIDO`, `apto_operacional=true`); aparece em CT-e Entrada; **sem** financeiro, expedição ou rateio automático.
- **CT-e divergente / ignorado** = permanecem na base importada; não entram na listagem operacional até correção ou nova ação.

### ERP 4.0.10.2 — conferência e precificação

- Listagens da base importada retornam `classificacao_dfe` (sem XML na listagem).
- Precificação/gerencial (`queryset_faturamento_nf_saida_historica`, `queryset_compras_nf_entrada_historica`, `queryset_cte_historico_logistico`) filtram homologação e exigem cStat 100.
- **Conferir entrada:** revisão segura; salvar CONFERIDA não aplica estoque nem financeiro.

### ERP 4.0.10.2.2 — conferência CT-e importado

- **Conferir CT-e** na base importada: checklist + observações; status `CONFERIDO` com `apto_operacional=true`.
- **CT-e Entrada** lista apenas conferidos (produção, autorizado, não cancelado/divergente/ignorado).
- Conferência **não** gera financeiro, expedição, rateio, estoque nem altera apuração.

### Futuro Monitor DF-e

Consulta automática à distribuição DF-e (NSU, manifestação, download XML) — apenas documentado; implementação em fase posterior.

---

## Referências

- `AtendimentoEstoque` — fase 3.8–3.10 (modo ANTECIPADO NF saída)
- `docs/base-dfe-importada.md` — base XML importada
- `docs/roadmap-nexus-erp.md` — histórico de versões
- `docs/design-system-nexus.md` — tokens de status operacionais
- `docs/base-dfe-importada.md` — base DF-e importada e regras fiscais

## 19. Campos comerciais padronizados (ERP 4.0.13.6.2)

- Quantidades e unidades:
  - `quantidade_comercial`
  - `unidade_comercial`
  - `quantidade_faturada`
  - `quantidade_pendente`
- Valores:
  - `preco_unitario_comercial`
  - `desconto_valor`
  - `total_linha` (somente calculado)
- Regras operacionais:
  - Pedido **aberto** permite editar item no painel expandido.
  - Pedido **faturado** bloqueia edição de item para preservar histórico comercial/fiscal.
  - Faturamento considera apenas faturamentos válidos.
  - PDF comercial do pedido usa totais comerciais calculados a partir dos itens.

### Extensão na 4.0.13.6.3

- `Propostas` e `Pedidos de Compra` passam a seguir a mesma base visual/comportamental:
  - campos numéricos padronizados para quantidade, preço, desconto e percentual;
  - unidade via seletor;
  - totais exibidos como calculados/read-only.

## 27. DANFE de conferência — layout duplicatas e totais (ERP 4.0.13.6.7)

- DANFE de conferência exibe fatura resumida e duplicatas em grade legível (1–10 parcelas no bloco principal).
- Acima de 10 duplicatas, continuação listada em Informações Complementares.
- Labels fiscais longos no quadro de totais usam quebra controlada; layout não altera XML nem emissão.

## 32. Produtos compostos, equivalências e montagens (ERP 4.0.13.7 / 4.0.13.7.1)

Conceitos independentes e integráveis:

- **Produto simples** — comprado/vendido como item único.
- **Produto componente** — parte de outro produto.
- **Produto composto / montado** — formado por componentes (pode ou não gerar estoque acabado nesta fase).
- **Kit comercial** — vendido como unidade comercial; pode baixar componentes diretamente em fase futura.
- **Montagem** — simples, roscada, soldada, com serviço interno ou terceirizada (`ProcessoMontagem` cadastral).
- **Equivalência simples** — um item do fornecedor equivale a um produto interno.
- **Equivalência composta** — vários itens do fornecedor, juntos, equivalem a um produto interno.

Um mesmo produto final pode ter **múltiplas formas de origem** (comprar pronto, montar internamente, montar por terceiro, kit, equivalência na NF-e). Não há campo único rígido “é composto”.

**Conferência NF-e entrada** — seção “Equivalências e Composições”:

- Sugere equivalência simples, composta ou montagem planejada (confiança 0–100).
- Permite agrupamento manual de itens → produto interno.
- Usuário confirma ou rejeita; pode salvar regra para próximas notas.
- Registra rastreabilidade (NF-e, itens originais, produto interno, usuário, regra, motivo).
- **Não** movimenta estoque, **não** gera financeiro, **não** altera XML de entrada.

Aviso operacional: *“Equivalência confirmada para conferência. Movimentação de estoque ou montagem real será feita em fase própria.”*

**Fase futura** — ordem de montagem com consumo de componentes e geração de produto acabado.

### Relação com Famílias/Figuras (ERP 4.0.13.7.1)

- **Famílias/Figuras** continuam sendo a base de produtos técnicos (código de figura, regra dimensional, templates).
- Composição, montagem e equivalência são **camada complementar** — produto final e componentes referenciam produtos reais da estrutura atual.
- Testes automatizados usam dados sintéticos **somente no banco isolado** (`test_*`); não devem criar registros visíveis no app de desenvolvimento.

### Limpeza de produtos artificiais (ERP 4.0.13.7.2)

- Produtos de teste acidentalmente persistidos (lista fechada de códigos + descrição «Fam») são removidos via comando administrativo com dry-run.
- Famílias, figuras, templates `{figura}`, `{schedule}`, etc. **não são alterados** por essa limpeza.

## 31. Higienização XML de transmissão (ERP 4.0.13.6.13)

- Preview/conferência ≠ transmissão: preview pode ter `NFePREVIEW` e avisos; transmissão não.
- `dhEmi` com timezone explícito (`-03:00`); IE/CNPJ/CEP sem máscara no XML.
- `indFinal` e `indPres` confirmados na conferência antes de gerar XML de transmissão.
- XML de transmissão preserva snapshot fiscal (ICMS/PIS/COFINS/Reforma/transporte/duplicatas).

## 30. Performance e UX da conferência NF-e (ERP 4.0.13.6.12)

- Abertura da conferência carrega apenas dados necessários para a primeira tela — **sem** gerar XML, DANFE ou checklist completo automaticamente.
- **Salvar alterações** persiste complementos; **não** valida tudo automaticamente.
- **Validar dados salvos** usa snapshot persistido; **não** recalcula fiscal sem necessidade.
- XML pré-autorização pode ser cacheado (`xml_preliminar`); invalidado quando complementos/fiscal/transporte mudam.
- Checklist leve (operacional) vs completo (pré-transmissão com Reforma no XML).
- Validação **não altera** ICMS/PIS/COFINS, Reforma, transporte, duplicatas ou fatura.

## 29. Base IBS/CBS parametrizada (ERP 4.0.13.6.11)

- Base IBS/CBS configurável na regra fiscal (`modo_base_ibs_cbs`); padrão = base cheia (comportamento anterior).
- Snapshot audita: base original, deduções (ICMS/PIS/COFINS/IPI/ISS), fórmula, fonte e status.
- Tela, XML e checklist usam o **mesmo snapshot**; não alteram vProd, vNF, ICMS, PIS, COFINS, duplicatas ou transporte.
- Regra com fonte `pendente` gera alerta em homologação e bloqueio em produção.
- Cenários comparativos A–D disponíveis no diagnóstico técnico do snapshot.
- NT 2025.002-RTC indica base excluindo tributos substituídos — modo `BASE_OFICIAL_2026` aplica essa referência; exige confirmação contábil para produção.

## 28. Transporte na conferência NF-e (ERP 4.0.13.6.10)

- Aba Transporte possui **salvamento explícito** (`PATCH /api/nf-saidas/{id}/`); validar conferência lê dados persistidos.
- Alterações locais não salvas **não** devem ser sobrescritas ao validar — UI exige salvar ou usar «Salvar e validar».
- `modFrete = 9` (sem ocorrência de transporte) **não** pode coexistir com transportadora, volumes, pesos, placa ou valor de frete.
- XML preliminar/preview/emissão respeita transporte salvo; com `modFrete=9` omite `transporta`/`vol`/`veicTransp`.
- Transporte **não** gera financeiro, estoque, expedição, transmissão NF-e nem altera apuração/ICMS/PIS/COFINS/Reforma.

## 27. Reforma Tributária em todos os XMLs da NF-e (ERP 4.0.13.6.9)

- Reforma calculada no snapshot **precisa** aparecer nos grupos oficiais `IBSCBS` (item) e `IBSCBSTot` (total) em **todos** os XMLs gerados antes da autorização.
- Camada central: `apps/fiscal/reforma_tributaria/xml.py` + `build_total_nfe_bindings` / `_build_det` em `nfe_saida_xml_nfelib.py`.
- Fluxos cobertos: XML preliminar, preview/download, checklist, persistido pré-autorização, transmissão homologação/produção e reprocessamento — **mesma serialização**.
- Snapshot visual na aba Reforma **não basta**; validação bloqueia se Reforma calculada estiver ausente no XML (`REFORMA_AUSENTE_XML`).
- XML autorizado já existente **não é reescrito** (documento fiscal histórico).
- `cMun` do destinatário deve ser coerente com cidade/UF (ex.: Belém/PA → `1501402`); endereço inconsistente bloqueia geração do XML.

## 26. Reforma Tributária no snapshot da NF-e rascunho (ERP 4.0.13.6.6)

- CST e classificação tributária vêm da regra fiscal de saída; alíquotas IBS/CBS são normalizadas (vírgula pt-BR → decimal).
- **Atualizar fiscal** calcula base, alíquota e valor IBS estadual / CBS no `snapshot_fiscal.reforma_tributaria`.
- Status **OK** na conferência só quando configuração e valores calculados são coerentes; alíquota com valor zerado gera alerta.
- Não gera financeiro, estoque, expedição nem apuração; XML/DANFE autorizado não é alterado nesta fase.

## 25. Atualizar fiscal da NF-e rascunho (ERP 4.0.13.6.5)

- O botão **Atualizar fiscal** usa o **cenário padrão de saída** (mesma fonte da tela Regras Fiscais), não apenas a tabela fiscal legada de propostas.
- Busca por NCM normalizado + UF origem + UF destino + operação `VENDA`.
- Se destino fiscal é PA, aplica regra SP→PA; não faz fallback para SP→SP.
- Snapshot fiscal só é gerado quando a regra compatível é encontrada; dados comerciais do item permanecem preservados.

## 24. Endereço fiscal do cliente e diagnóstico de regra na NF-e (ERP 4.0.13.6.4)

- Cliente pode ser usado comercialmente mesmo com cadastro incompleto.
- NF-e exige endereço fiscal coerente (CEP, cidade, UF alinhados à consulta ViaCEP).
- Regra fiscal de saída usa **UF destino real** do cliente — não assume SP por ser a empresa emissora.
- Regra SP→SP **não** deve ser aplicada se o destino fiscal for outro estado ou estiver inconsistente.
- Snapshot fiscal do item só é gerado quando existe regra compatível com origem/destino/NCM.
- `Atualizar fiscal` informa diagnóstico: endereço inconsistente **ou** falta de regra (`NCM · origem · destino`).

## 33. Financeiro base operacional (ERP 4.0.14)

Módulo financeiro manual e controlado — **sem geração automática** de títulos a partir de NF-e, pedido ou faturamento nesta fase.

### Cadastros mínimos

| Cadastro | Uso |
|----------|-----|
| Conta / Caixa / Banco | Onde o dinheiro entra ou sai na baixa — cadastro financeiro real; tipo **Banco** pode guardar banco, agência e conta; tipo **Caixa/Carteira/Outro** não exige dados bancários |
| Forma de pagamento | Dinheiro, Pix, boleto, etc. |
| Categoria financeira | Classificação receita/despesa |

### Contas a Receber e Contas a Pagar

- Título com cliente (receber) ou fornecedor (pagar), vencimento, valor original, saldo em aberto e status operacional.
- Status: Em aberto, Vencido, Parcialmente recebido/pago, Recebido/Pago, Cancelado.
- **Vencido** é status operacional (vencimento &lt; hoje e saldo &gt; 0), não erro técnico.

### Parcelas

- Um título pode ter uma ou várias parcelas; soma das parcelas deve coincidir com o total (tolerância de centavos).
- Duplicatas fiscais da NF-e **não** são alteradas; vínculo futuro apenas por ação explícita do usuário.

### Baixa e estorno

- Baixa total ou parcial; juros, multa, desconto e tarifa opcionais.
- Baixa **não** é apagada; estorno exige motivo e reabre o saldo.
- Mensagens: «Recebimento registrado com sucesso», «Baixa estornada. O saldo do título foi reaberto.»

### Origem rastreável

Campos operacionais: `origem_tipo`, `origem_id`, `origem_descricao`, `origem_numero`, `origem_data`.  
UI exibe, por exemplo: «Origem: Faturamento FAT-xxxx» ou «Origem: NF-e nº 000000003» — **sem** `content_type`, `object_id` ou payload na tela principal.

### Integração futura com NF-e / faturamento

- Ação futura controlada: «Gerar contas a receber» a partir de NF-e autorizada ou faturamento, com confirmação do usuário.
- Cancelamento de NF-e **não** apaga financeiro automaticamente; alerta operacional para revisão dos títulos vinculados.
- Automação financeira (geração/baixa/conciliação) fica para fase posterior, após validação da base.

API: `apps.financeiro` — rotas `/api/financeiro/*` (contas, formas, categorias, centros-custo, contas-receber, contas-pagar, baixas, resumo).

### Despesas e tributos a pagar (complemento 4.0.14)

**Contas a Pagar** aceita lançamentos manuais com tipo:

| Tipo | Uso |
|------|-----|
| Fornecedor | Conta vinculada a fornecedor |
| Despesa operacional | Descrição obrigatória; fornecedor opcional |
| Serviço | Descrição ou fornecedor |
| Tributo / Imposto | ICMS, PIS, COFINS, IPI, ISS, IBS, CBS, IR, CSLL, INSS, FGTS, Outros |
| Outros | Descrição obrigatória |

Campos: descrição, competência, vencimento, valor, categoria, centro de custo (opcional), forma/conta previstas, guia e código de receita (tributos).

**Tributos:** lançamento **manual** — não calcula impostos a partir de NF-e, XML, Reforma ou apuração fiscal. Origem futura preparada (`APURACAO_FISCAL`).

**Parcelamento de tributos:** lista de parcelas (vencimento + valor); soma validada com tolerância de centavos; baixa e estorno **por parcela** (histórico registra número da parcela).

UI: *Nova despesa*, *Novo tributo a pagar*, *Nova conta a pagar*, *Parcelar*, *Valor em aberto*.

### Correção 4.0.14.0.1 — sem cadastro financeiro de condição de pagamento

- O Financeiro **não** possui cadastro próprio de condição de pagamento.
- Condição de pagamento pertence ao documento comercial/de origem (proposta, pedido, faturamento, NF-e/duplicatas).
- No Financeiro, o controle é por **título, parcela, vencimento, baixa, estorno e saldo**.
- Parcelamento permanece no próprio título financeiro (manual ou vindo do documento de origem), sem consultar cadastro financeiro de condição.

## 29. Camada operacional da interface (ERP 4.0.13.8)

- Telas principais exibem **ações de negócio** (vender, faturar, emitir NF-e, ver DANFE, baixar XML), não artefatos técnicos.
- Detalhes técnicos (XML preliminar, assinado, lote, retorno SEFAZ, renderer, schema, trace) ficam em **Avançado / Suporte técnico**, fechado por padrão.
- O usuário não escolhe tipo de XML interno — **Ver DANFE** é ação única; o sistema decide qual documento gerar.
- **Baixar XML** na área principal refere-se ao XML autorizado; demais XMLs permanecem em Avançado.
- Status define ações disponíveis: rascunho (validar, emitir), autorizada (DANFE, XML, cancelar), rejeitada (corrigir, reenviar).
- Linguagem técnica (enum interno, payload, snapshot) é traduzida para linguagem operacional na UI.
- Componentes: `AdvancedSupportSection`, `OperationalMessage`, dicionário `operationalUi.ts`.
- **Sem alteração** de cálculo fiscal, XML de transmissão, DANFE/BFR, estoque ou financeiro nesta fase.

## ERP 4.0.14.1 — Formas fixas, créditos e abatimentos

- Forma de pagamento no Financeiro é lista fixa sistêmica, não cadastro.
- Devolução é tratada como tipo de movimento financeiro (ex.: abatimento por devolução), não como forma de pagamento.
- Crédito de cliente/fornecedor é gerado manualmente e controlado no Financeiro.
- Crédito pode ser aplicado em títulos em aberto, com rastreabilidade de eventos.
- Abatimento direto por devolução é ação explícita, manual e auditável.
- Nesta fase não há integração automática com NF-e de devolução.

## ERP 4.0.14.1.1 — Conta financeira tipo Banco

- Conta/Caixa é cadastro financeiro real usado nas baixas.
- Tipo **Banco** exige o campo **banco** (agência e conta opcionais nesta fase).
- Tipo **Caixa**, **Carteira** ou **Outro** não exige dados bancários na validação.
- Contas antigas tipo Banco sem banco continuam editáveis; listagem exibe «Não informado» até correção manual.

## ERP 4.0.14.1.2 — Labels de conta financeira tipo Banco

- Em conta tipo **Banco**, o campo **nome** representa descrição/apelido operacional (ex.: «Conta principal», «Conta recebimentos»).
- O campo **banco** representa a instituição bancária (ex.: Itaú, Bradesco).
- Formulário ordenado: Banco → Apelido → Agência → Conta, para evitar duplicidade Itaú/Itaú.

## ERP 4.0.14.1.3 — Busca de fornecedor no Financeiro

- Fornecedor em contas a pagar usa busca por razão social, nome fantasia ou CNPJ (`FornecedorSearchSelect`).
- Fornecedor é **obrigatório** na conta a pagar de fornecedor; **opcional** em despesa operacional.
- O financeiro **não cria fornecedor automaticamente** — link para cadastro em `/fornecedores`.

## ERP 4.0.14.1.4 — Cliente em Contas a Receber

- Contas a Receber usa busca de cliente por razão social, nome fantasia, CNPJ ou CPF.
- **Nova conta a receber** cria título financeiro manual; **Baixar recebimento** registra entrada de dinheiro (baixa).
- O financeiro **não cria cliente automaticamente** — link para cadastro em `/clientes`.

## ERP 4.0.14.1.5 — Detalhe financeiro por status

- Mensagens e ações do detalhe (drawer) são determinadas por status do título, saldo em aberto e movimentos não estornados.
- Título **em aberto** permite registrar baixa, editar dados e cancelar (quando sem baixas).
- Título **parcialmente** recebido/pago mantém saldo em aberto e permite baixar o restante ou estornar.
- Título **quitado** (recebido/pago) exige estorno de baixa para alteração sensível de valores.
- Título **cancelado** não aceita novas baixas, crédito ou abatimento.
- API expõe flags derivadas (`pode_baixar`, `pode_editar`, etc.) sem alterar regras de baixa/estorno/crédito.

## ERP 4.0.14.2 — Créditos, abatimentos e aplicação operacional

- **Crédito de cliente** — valor a favor do cliente; aplicação manual em Contas a Receber do mesmo cliente.
- **Crédito de fornecedor** — valor a favor da empresa junto ao fornecedor; aplicação manual em Contas a Pagar do mesmo fornecedor.
- **Abatimento por devolução** — reduz saldo do título em aberto; forma «Sem movimentação financeira»; não gera crédito separado.
- **Uso de crédito** — movimento `USO_CREDITO`; reduz saldo do crédito e do título; histórico nos dois lados.
- **Estorno** — uso de crédito devolve saldo ao crédito e reabre título; abatimento reabre saldo do título.
- **Sem integração automática** com NF-e, pedido, XML ou devolução fiscal nesta fase.
- Tela **Financeiro > Créditos** para cadastro, consulta, aplicação e cancelamento de créditos não utilizados.

## ERP 4.0.14.2.1 — Acabamento operacional de créditos e exclusão segura

- **Crédito manual sem movimento** (origem Manual ou Ajuste, disponível, sem aplicação/estorno) pode ser **editado integralmente** ou **excluído** — apenas para correção de erro de cadastro.
- **Crédito com histórico** (aplicação, estorno ou cancelamento) **não pode ser excluído**; edição limitada a documento, motivo complementar e observações.
- **Cancelamento de crédito** exige motivo, preserva registro e eventos no histórico.
- **Título manual sem movimento** pode ser **excluído** quando saldo integral, sem baixa, crédito ou abatimento.
- **Título com origem externa** (NF-e, pedido, faturamento, apuração, importação) ou **com movimentação** **não pode ser excluído** — usar cancelamento/estorno conforme o caso.
- **Exclusão** (crédito ou título) sempre exige motivo; **nunca** apaga registros que já possuem histórico financeiro relevante.

## ERP 4.0.14.2.2 — Exclusão segura após estorno

- **Exclusão segura** considera **movimento financeiro ativo**, não apenas a existência de histórico.
- **Movimento estornado** não bloqueia exclusão de lançamento manual quando o saldo foi **integralmente reaberto** e não há efeito ativo.
- **Registros com origem externa** (NF-e, pedido, faturamento, apuração, importação) **nunca** são excluídos pelo Financeiro.
- **Registros com movimento ativo** devem ser estornados antes da exclusão.
- **Cancelamento** preserva histórico quando a exclusão não se aplica.

## ERP 4.0.14.3 — Contas a Receber a partir de NF-e autorizada

- **Produção:** após autorização SEFAZ persistida (`AUTORIZADA_PRODUCAO` + protocolo + XML + número/série), o Nexus **gera Contas a Receber automaticamente**, reutilizando o serviço financeiro (parcelas/duplicatas, origem `NFE_SAIDA`, idempotência).
- **Homologação:** **não** gera financeiro.
- **Falha financeira** não desfaz a autorização fiscal — aviso operacional e ação manual **Gerar contas a receber** permanece para regularizar.
- Wizard manual permanece como **recuperação** (preview, edição de parcelas, classificação) quando a geração automática falhar ou para NF-e já autorizadas sem título.
- Cada título tem **origem rastreável** (`NFE_SAIDA`, número, chave, pedido/faturamento).
- **Duplicatas fiscais** da NF-e viram **parcelas financeiras** operacionais — sem alterar XML/DANFE/duplicatas fiscais.
- **Não duplicar**: mesma NF-e não gera segundo título; reprocessamento retorna o existente; UI mostra **Ver contas a receber**.
- Título com origem NF-e **não pode ser excluído** pelo Financeiro.
- Se a NF-e for **cancelada depois**, o financeiro **permanece** — alerta operacional nos títulos vinculados.
- **Não** gera CR ao faturar pedido, antes da autorização SEFAZ, nem em rascunho/rejeição/autorização interna.
- **Não** cria baixa, boleto, Pix ou movimentação bancária automática.

## ERP 4.0.14.4 — Geração manual de Contas a Pagar a partir de NF-e Entrada

- O financeiro **não é gerado automaticamente** ao importar XML, vincular pedido de compra, conferir entrada ou confirmar equivalência.
- O usuário aciona **Gerar contas a pagar** na conferência da NF-e Entrada, revisa parcelas sugeridas (duplicatas/fatura do XML) e **confirma**.
- Cada título gerado tem **origem rastreável** (`NFE_ENTRADA`, número, chave, pedido de compra vinculado como contexto).
- **Duplicatas/fatura** da NF-e Entrada viram **parcelas financeiras** operacionais — **sem alterar** XML da entrada.
- **Não duplicar**: mesma NF-e Entrada não gera segundo título; ação muda para **Ver contas a pagar**.
- Título com origem NF-e Entrada **não pode ser excluído** pelo Financeiro (baixa/estorno/cancelamento conforme regras).
- Se a NF-e Entrada for **cancelada depois**, o financeiro **permanece** — alerta operacional nos títulos vinculados.
- **Pedido de Compra vinculado** é apenas contexto de conferência — não altera pedido, estoque ou gera financeiro automático.

## ERP 4.0.14.8 — Preparação para produção

### Numeração CR/CP

- Contas a Receber: `CR-AAAA-000001` (sequencial de 6 dígitos, reinício anual).
- Contas a Pagar: `CP-AAAA-000001` (sequencial independente de CR).
- NF-e permanece apenas na **origem rastreável** — não substitui o número do título.

### Vencimento obrigatório

- Todo título válido exige vencimento (título ou parcelas).
- Relatórios e PDFs usam vencimento da parcela relevante; «—» só para legado inconsistente («Vencimento não informado.»).

### Usuários vinculados a colaboradores

- **Colaborador** = pessoa da operação; **Usuário** = credencial de acesso ao sistema (login Django).
- **Funções internas** (Vendedor, Comprador, Fiscal, Financeiro, Estoque, Qualidade, Admin) indicam participação operacional — **não substituem** o perfil/grupo de acesso.
- **Perfil de acesso** = grupo Django (`Administrador`, `Financeiro`, `Fiscal`, `Compras`, `Comercial`, `Estoque`, `Produtos`, `Consulta`). Todo usuário **ativo** deve ter perfil definido.
- Criação de usuário pela tela **Cadastros > Colaboradores > Editar > Acesso ao sistema**: e-mail e perfil obrigatórios; senha **nunca** em texto — link de redefinição/convite quando suportado.
- Vincular usuário existente, definir perfil, desativar acesso e reenviar convite — sem apagar colaborador nem usuário.
- Um colaborador ativo → no máximo um usuário ativo vinculado; prontidão acusa usuário ativo sem perfil com orientação para a tela de Colaboradores.

## ERP 4.0.14.9.1 — Acesso ao sistema na tela de Colaboradores

- Modal em três seções: **Dados do colaborador**, **Funções internas**, **Acesso ao sistema**.
- Coluna **Acesso** na listagem: Sem acesso / Usuário ativo / Sem perfil / Usuário inativo.
- Endpoints: `POST .../criar-usuario/`, `.../vincular-usuario/`, `.../definir-perfil-acesso/`, `.../desativar-acesso/`, `GET .../perfis-acesso/`.
- Sugestão de perfil a partir das funções internas (confirmação explícita do operador).
- `verificar_prontidao_producao` orienta correção em Colaboradores quando houver usuário sem grupo.

## ERP 4.0.14.10.2 — Gestão de perfil de acesso do usuário no colaborador

- Funções internas do colaborador **não substituem** perfil de acesso — perfil vem de grupos Django.
- Superusuário ativo conta como acesso válido na prontidão (sem exigir grupo).
- Usuário ativo precisa ter perfil **ou** ser superusuário; e-mail técnico/local bloqueia produção.
- Gestão em **Cadastros > Colaboradores > Editar > Acesso ao sistema > Editar acesso**.
- Endpoint `PATCH /api/colaboradores/{id}/acesso/` para perfil, e-mail, status e staff.

## ERP 4.0.14.10.1 — Regra fiscal de entrada como validação de uso

- Regra fiscal de **saída/venda** permanece crítica para prontidão geral de produção.
- Regra fiscal de **entrada incompleta** gera **aviso** na prontidão — não bloqueia limpeza nem prontidão geral se a saída estiver OK.
- `validar_regra_fiscal_entrada_para_uso()` bloqueia apenas o fluxo de NF-e Entrada fiscal (preparar/finalizar entrada).
- Importar XML, visualizar NF-e, salvar conferência com pendências e **gerar Contas a Pagar** permanecem independentes da regra de entrada.
- Relatório pré-produção: `fiscal.criticos`, `fiscal.avisos_entrada`, `fiscal.bloqueios_por_fluxo.nfe_entrada`.

## ERP 4.0.14.10 — Regras fiscais mínimas para produção

- `validar_regras_fiscais_minimas()` — empresa com regime/CNPJ/UF, regra de venda ativa, CFOP, CST/CSOSN, produtos com NCM.
- Prontidão fiscal integrada a `verificar_prontidao_producao`; relatório JSON com seção `fiscal`.
- Regras fiscais **não** são criadas por migration/seed — cadastro manual com contador.
- Regras fiscais preservadas na limpeza (`regras_fiscais`, `regras_fiscais_saida`, `regras_fiscais_entrada`).
- Não altera emissão NF-e, XML, DANFE, BFR ou motor fiscal validado.

## ERP 4.0.14.9.4.1 — Correção de nome exibido no Header/UserMenu/Minha conta

- Bug: header mostrava `username` (`admin`) apesar do colaborador vinculado — cache/resposta antiga ou fallback incorreto no frontend.
- Correção: helper central `getUsuarioNomeExibicao`; API garante `nome_exibicao` e `colaborador_nome`; cache invalidado no login e após alterações em Colaboradores.
- Header e Minha conta usam nome humano; login permanece secundário.

## ERP 4.0.14.9.4 — Minha conta, nome exibido e cabeçalho refinado

- **Nome exibido** no header e Minha conta prioriza o colaborador vinculado; login (`username`) permanece visível como dado técnico.
- Empresa no cabeçalho usa razão social completa quando há espaço; truncamento só em telas estreitas; tooltip com CNPJ.
- **Minha conta** reorganizada em blocos operacionais; usuário comum edita e-mail e telefone; perfil/grupo/login são administrados em Colaboradores.
- E-mail técnico/local (ex.: `admin@localhost`) gera aviso em Minha conta e item **crítico** na prontidão de produção.
- Testes: `test_minha_conta_401494.py`, `header401494.test.tsx`, `minhaConta401494.test.tsx`.

## ERP 4.0.14.9.3 — Cabeçalho operacional

- Busca global simples (`GET /api/busca-global/`) em clientes, fornecedores, produtos, documentos e financeiro.
- Empresa no cabeçalho é **apenas identificação visual** — sem multiempresa nesta versão.
- Menu do usuário: Minha conta, Alterar senha; perfil somente leitura.
- Multiempresa / matriz / filial / multi-CNPJ → fase futura (ERP 4.1.x).

## ERP 4.0.14.9.2 — Senha inicial e redefinição

- Admin cria usuário com **senha inicial** na tela de Colaboradores (e-mail, nome, perfil, senha, confirmação).
- Senha salva com hash Django; **nunca** exibida ou retornada após salvar.
- Usuário acessa com senha definida; pode trocar em **Minha conta > Alterar senha** (senha atual obrigatória).
- Apenas Admin redefine senha de outro usuário (`POST .../redefinir-senha/`).
- Sem convite por e-mail nem obrigatoriedade de troca no primeiro acesso.
- Se único Admin esquecer senha: `python manage.py changepassword admin` (ou `docker compose exec backend ...`).
- Prontidão valida perfil, senha utilizável e e-mail válido.

## Módulo futuro — Fechamento fiscal/contábil e DF-e (ERP 4.1+)

Planejado **após produção com dados reais**. Não implementado no ERP 4.0.14.x.

### Limpeza segura para produção

- `python manage.py verificar_prontidao_producao` — somente leitura.
- `python manage.py preparar_limpeza_producao --dry-run` — lista preservados e candidatos.
- Execução real: `--executar --backup-confirmado --confirmar APAGAR_DADOS_TESTE`.
- **Produtos sempre preservados**; documentos possivelmente reais bloqueiam limpeza.

### Checklist de produção (documentado, não automático)

- DEBUG=False, ambiente fiscal, certificado, numeração fiscal, backup, dados de teste limpos, usuários/permissões, relatório de prontidão sem críticos.

## ERP 4.0.14.9 — Pré-produção e checklist final

### Processo

1. `python manage.py verificar_prontidao_producao` — críticos / avisos / ok (somente leitura).
2. `python manage.py preparar_limpeza_producao --dry-run` — preservados, candidatos, bloqueios.
3. `python manage.py gerar_relatorio_pre_producao` — JSON em `reports/pre_producao_*.json`.
4. Backup manual do banco e arquivos.
5. Limpeza real **somente via terminal**, se autorizado:
   `preparar_limpeza_producao --executar --backup-confirmado --confirmar APAGAR_DADOS_TESTE`
6. Pós-limpeza: repetir prontidão e dry-run.

### Dados preservados (sempre)

Produtos, famílias/figuras, NCM, regras fiscais, empresa emitente, colaboradores, usuários, grupos, categorias/centros/contas (cadastro).

### Candidatos à limpeza

Operacionais de teste/homologação: NF-e, pedidos, propostas, faturamentos, financeiro (CR/CP/baixas/créditos), estoque operacional, conferências.

### Bloqueios de execução

Produtos na lista de limpeza; documentos possivelmente reais; prontidão com críticos; ambiente produção; sem backup ou confirmação textual.

## ERP 4.0.14.6 — Relatórios financeiros operacionais

- Área **Financeiro > Relatórios** com seis relatórios: Contas a Receber, Contas a Pagar, fluxo previsto, receitas/despesas por categoria, por cliente e por fornecedor.
- Relatórios são **somente leitura** (consolidação e filtros); não alteram títulos, baixas, estornos ou NF-e.
- **Fluxo previsto** usa títulos em aberto por vencimento; não é conciliação bancária nem saldo real de conta.
- **Receitas e despesas por categoria** não é DRE contábil.
- Filtros refletidos na URL; agrupamentos opcionais em CR/CP.

## ERP 4.0.14.7 — Motor central de relatórios PDF

- Pacote `apps.relatorios` gera PDF operacional via ReportLab (isolado de DANFE/BFR/XML).
- Financeiro é o primeiro módulo com exportação PDF (`GET /api/financeiro/relatorios/<tipo>/pdf/`).
- PDF usa os **mesmos filtros** da tela (query string); relatórios permanecem somente leitura.
- Layout padrão: cabeçalho (empresa, período, filtros, usuário), resumo, tabela, totais, rodapé com aviso operacional.
- DANFE e emissão fiscal **não** utilizam este motor.

## ERP 4.0.14.6.1 — Consistência dos relatórios financeiros

- Por padrão, relatórios **priorizam saldos ativos**: em aberto, vencidos e parcialmente recebidos/pagos.
- Títulos **quitados/recebidos/pagos** e **cancelados** são histórico e só aparecem com `incluir_quitados` / `incluir_cancelados`.
- **Linhas zeradas** (cliente/fornecedor/categoria sem saldo, vencido ou movimento no período) ficam ocultas; `incluir_sem_saldo` exibe registros sem saldo relevante quando o histórico está incluído.
- Cards de **total em aberto** e **total vencido** não somam cancelados nem quitados integralmente, mesmo que a tabela liste histórico por filtro.
- Relatório por categoria distingue **valor original** (soma dos títulos filtrados), **em aberto** (saldo pendente), **baixado no período** (baixas no intervalo) e **total considerado** (conforme filtros).
- Status **Vencido** na UI é operacional (vencimento &lt; hoje com saldo em aberto), sem alterar status persistido no banco.

## ERP 4.0.14.5 — Visão geral financeira e alertas operacionais

- A rota **Financeiro** exibe resumo: a receber/pagar (hoje, vencido, 7 dias, em aberto, recebido/pago no período).
- **Saldo previsto** = total a receber em aberto − total a pagar em aberto (operacional, não conciliação bancária).
- **Alertas**: vencidos, vencendo hoje, origem fiscal cancelada, sem categoria, sem conta prevista, créditos disponíveis.
- Títulos com NF-e de origem cancelada exibem alerta — não apagam/cancelam/estornam automaticamente.
- Filtros em CR/CP com atalhos a partir dos cards da visão geral.

## ERP 4.0.14.4.1 — Financeiro independente de pendências operacionais

- A obrigação financeira da NF-e Entrada vem do **documento fiscal do fornecedor** — não depende de estoque aplicado ou produto vinculado.
- **Pendências operacionais** (produto, equivalência, estoque, pedido) **não bloqueiam** geração manual de Contas a Pagar.
- Bloqueios financeiros reais: fornecedor ausente, valor inválido, cancelamento, duplicidade, XML inválido.
- Geração com pendências exige **confirmação explícita** no wizard — estoque e conferência continuam pendentes.
