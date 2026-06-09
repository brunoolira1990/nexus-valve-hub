# Base DF-e Importada — Nexus ERP 4.0.10.x

Documento de referência para XMLs importados manualmente (NF-e entrada/saída, CT-e) e sua relação com apuração, contábil, BI e precificação.

---

## 1. O que é a Base DF-e Importada

Conjunto de documentos fiscais eletrônicos obtidos por **importação de XML** (sistema anterior, fornecedor, transportadora), persistidos para:

- apuração fiscal gerencial;
- base contábil e relatórios;
- BI e indicadores;
- precificação comercial (custo, preço praticado, frete médio);
- histórico comercial (compra/venda).

**Não** dispara automaticamente: estoque, contas a pagar/receber, pedidos, faturamento, expedição ou conciliação operacional.

Classificação técnica: `BASE_DFE_IMPORTADA` em `apps/fiscal/dfe_classificacao.py`.

---

## 1.1 Ponto único de importação XML (ERP 4.0.10.2.1)

A importação de XML ocorre **somente** nas telas de base importada:

| Tipo | Importar XML | Operacional |
|------|----------------|-------------|
| NF-e fornecedor | **Base NF-e Entrada Importada** | NF-e Entrada (conferência/emissão própria) |
| NF-e saída sistema anterior | **Base NF-e Saída Importada** | NF-e Saída (emissão ERP) |
| CT-e recebido | **Base CT-e Importada** | CT-e Entrada (uso operacional futuro) |

Telas operacionais **não** duplicam o importador: exibem link “Ir para Base … Importada” e empty states que orientam o usuário.

- **NF-e Entrada:** “Emitir entrada própria” permanece na tela operacional; XML de fornecedor → base importada.
- **CT-e Entrada:** não é emissão manual de CT-e; XML → base importada.

Promoção de documento importado para operacional será ação explícita futura (fora desta fase).

---

## 2. NF-e Entrada importada

- Tela: **Base de NF-e Entrada Importada** (`/nfe-entrada-historica-importada`)
- Modelo: `NFeEntradaHistoricaImportada`
- Uso: custo de compra, impostos de entrada, fornecedor/produto, apuração PIS/COFINS/ICMS

---

## 3. NF-e Saída importada

- Tela: **Base de NF-e Saída Importada** (`/nfe-historica-importada`)
- Modelo: `NFeSaidaHistoricaImportada`
- Uso: histórico de vendas emitidas fora do ERP, margem, preço praticado, apuração de saída

---

## 4. CT-e importado

- Tela: **Base de CT-e Importada** (`/cte-historico-importado`)
- Modelo: `CTeHistoricoImportado`
- Uso: frete médio, custo logístico, análise por transportadora, CBS/IBS em apuração quando presente no XML

### 4.1 Conferência de CT-e importado (ERP 4.0.10.2.2)

Na base importada, o usuário revisa o CT-e e marca **Conferido**, **Divergente** ou **Ignorado operacionalmente**.

**A conferência não gera:**

- contas a pagar ou lançamento financeiro;
- expedição ou rateio de frete;
- movimentação de estoque;
- alteração na apuração fiscal;
- alteração em precificação ou emissão NF-e.

**O que a conferência faz:**

- registra usuário, data, checklist e observações;
- com status **Conferido** + `apto_operacional=true`, o CT-e aparece em **CT-e Entrada** (`/cte-entrada`) para uso operacional futuro;
- documentos **Divergente** ou **Ignorado** permanecem na base importada (apuração/BI/precificação quando fiscalmente válidos), mas não entram na listagem operacional.

Estados: `IMPORTADO`, `PROCESSADO`, `PREPARADO`, `CONFERIDO`, `DIVERGENTE`, `IGNORADO`, `CANCELADO`.

Endpoints:

- `POST /api/cte-historicos-importados/{id}/conferir/`
- `POST /api/cte-historicos-importados/{id}/marcar-divergente/`
- `POST /api/cte-historicos-importados/{id}/ignorar-operacional/`

Homologação (`tpAmb=2`) não pode ser conferida para uso operacional.

Serviço: `apps/fiscal/cte_historico_conferencia.py`. Testes: `test_cte_historico_conferencia_401022.py`, `dfeOrganizacao401022.test.tsx`.

---

## 5. Uso em apuração fiscal

A **Apuração Fiscal** (`/apuracao-fiscal`) consolida:

- base importada (XML) — fonte “Base DF-e importada”;
- NF-e operacional produção (ERP) — fonte “Operacionais produção”;
- ambos na fonte “Todos válidos”.

**Sempre excluídos:** homologação (`tpAmb=2`), rascunho, rejeitada, erro de transmissão, documentos sem valor fiscal.

Canceladas: fora do resumo normal, salvo filtro `incluir_canceladas`.

---

## 6. Uso contábil

Base importada alimenta visões gerenciais e preparação de EFD on-demand (sem SPED TXT oficial nesta versão). Homologação nunca entra na base válida.

---

## 7. Uso em precificação

Propostas e análises podem consultar histórico de compra/venda e frete a partir da base importada, desde que `pode_alimentar_precificacao(documento)` seja verdadeiro (produção + autorizado).

---

## 8. Uso em BI

Dashboards e painéis consolidados podem agregar valores da base importada; homologação permanece fora de indicadores fiscais oficiais.

---

## 9. Conferência de entrada (4.0.10.2)

A ação **Conferir entrada** na Base NF-e Entrada Importada abre revisão segura (emitente, destinatário, itens, CFOP/NCM/impostos).

- Marcar **Conferida** ou **Preparada** revisa dados e prepara vínculos futuros.
- **Não** gera contas a pagar, não movimenta estoque e não concilia atendimento automaticamente.
- Estoque físico e demais efeitos operacionais exigem ações explícitas posteriores (`preparar-estoque`, `aplicar-estoque`), fora do escopo automático da importação.

Estados de conferência na base: `IMPORTADA`, `PREPARADA`, `CONFERIDA`, `DIVERGENTE`, `IGNORADA`.

API de listagem expõe `classificacao_dfe` (categoria, flags, badges) sem XML bruto na listagem.

---

## 10. Diferença para documento operacional

| | Base importada | Operacional (ERP) |
|---|----------------|---------------------|
| Origem | XML externo | Fluxo vivo (emissão/conferência) |
| Apuração (produção) | Sim | Sim (NF emitida válida) |
| Estoque/financeiro auto | Não | Futuro por regra de negócio |
| Promover para operacional | Ação futura explícita | Já é operacional |

---

## 11. Homologação fora da base válida

NF-e emitida em homologação no ERP, ou XML com `tpAmb=2`, é categoria `HOMOLOGACAO`:

- badge “Homologação / Sem valor fiscal / Fora da apuração” na listagem NF-e Saída;
- excluída em `build_apuracao_fiscal` via queryset + `pode_entrar_apuracao`.

---

## 12. Futuro — Monitor DF-e / Documentos Recebidos

Módulo planejado (não implementado na 4.0.10.2):

- consulta Distribuição DF-e (NSU, certificado A1);
- NF-e/CT-e emitidos contra o CNPJ da empresa;
- manifestação (ciência, confirmação, desconhecimento, operação não realizada);
- status: detectado → XML disponível → manifestado → importado para base → promovido operacional.

Diferente da importação manual atual: o monitor será **automático**; a base importada continua válida para histórico e anos anteriores.

---

## 13. Regras de segurança

Helpers em `dfe_classificacao.py`:

- `eh_documento_homologacao` / `eh_documento_producao`
- `eh_documento_autorizado` / `tem_valor_fiscal`
- `pode_entrar_apuracao` — gate único para apuração
- `pode_alimentar_precificacao` — exclui homologação na base e operacional
- `pode_gerar_efeito_operacional` — `false` para base importada e homologação
- `metadados_classificacao_dfe` — badges para API/UI
- `filtrar_queryset_precificacao_*` — produção + cStat 100

Testes: `test_dfe_organizacao_40101.py`, `test_dfe_organizacao_40102.py`, `test_dfe_organizacao_401021.py`, `test_cte_historico_conferencia_401022.py`, `dfeOrganizacao40101.test.tsx`, `dfeOrganizacao40102.test.tsx`, `dfeOrganizacao401021.test.tsx`, `dfeOrganizacao401022.test.tsx`.

---

## 14. Vínculo operacional (ERP 4.0.12)

Em `AlocacaoAtendimento`, o usuário pode referenciar opcionalmente:

- `nf_entrada_historica_item` — item de NF-e entrada na base importada/conferida;
- `cte_historico_importado` — CT-e conferido na base importada.

O vínculo serve **apenas para rastreabilidade e conferência operacional**; não promove o documento para operacional, não gera contas a pagar, não movimenta estoque e não altera apuração. Ver `docs/modelo-operacional-nexus.md` (seção 19).

### ERP 4.0.13 — busca assistida na alocação

Na gestão de `AlocacaoAtendimento`, o usuário **busca e seleciona** NF-e entrada importada/conferida e CT-e conferido (e pedido de compra/fornecedor) por autocomplete — sem digitar IDs internos.

- Homologação **não** aparece nas opções padrão de NF-e/CT-e.
- CT-e divergente/ignorado **não** aparece na busca padrão.
- Payload de opções **não** inclui XML completo.
- Vínculo ao salvar **não** promove automaticamente para operacional.
