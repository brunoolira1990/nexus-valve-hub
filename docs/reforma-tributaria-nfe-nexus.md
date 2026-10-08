# Reforma Tributária — NF-e modelo 55 (Nexus ERP)

Documento técnico de pesquisa e decisão para ERP 4.0.13.4.  
**Regra Nexus:** nenhuma tag de Reforma Tributária entra no XML/DANFE de emissão sem constar aqui com base oficial.

---

## 1. Fontes oficiais consultadas

| Título | Versão / ref. | Data consulta | Origem | Aplicabilidade |
|--------|---------------|---------------|--------|----------------|
| Nota Técnica NF-e/NFC-e — Reforma Tributária do Consumo (RTC) | **2025.002** (evolução v1.00 → v1.36+) | 2026-05-23 | [Portal Nacional da NF-e](https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=BMPFMBoln3w=) — aba Documentos | Layout XML NF-e 55 / NFC-e 65 — IBS, CBS, IS |
| Lei Complementar nº 214/2025 | — | 2026-05-23 | Planalto / referência na NT 2025.002 | Base legal IBS/CBS/IS |
| Emenda Constitucional nº 132/2023 | — | 2026-05-23 | Referência indireta (NT e imprensa especializada) | Marco da reforma do consumo |
| Pacote de Schemas XML NF-e/NFC-e | Pacote liberação **010** (NT 2025.002 + NTs correlatas) | 2026-05-23 | Portal NF-e → Documentos → **Esquemas XML** | Validação XSD em homologação/produção |
| `DFeTiposBasicos_v1.00.xsd` | 1.00 | 2026-05-23 | NT 2025.002 item 5 | Tipos complexos IBS/CBS compartilhados entre DF-e |
| Informe Técnico RT 2024.001 / tabelas CST e cClassTrib | — | 2026-05-23 | Portal NF-e → Documentos → Diversos | Codificação CST e classificação tributária IBS/CBS/IS |

**Observação:** versões exatas da NT e do pacote de schemas devem ser confirmadas no Portal no momento de cada release. A NT 2025.002 **substitui** a NT 2024.002 no âmbito NF-e/NFC-e.

---

## 2. Nota Técnica aplicável

| Campo | Conteúdo |
|-------|----------|
| **Número** | NT **2025.002** — Adequação dos leiautes à Reforma Tributária do Consumo (RTC) |
| **Documentos** | NF-e (mod. **55**), NFC-e (mod. 65) |
| **Vigência homologação** | Campos disponíveis; validações quando informados; cronograma oficial cita **06/10/2025** início de obrigatoriedade em produção para contribuintes Regime Normal (CRT=3), com evolução por versões da NT |
| **Vigência produção** | Operação efetiva a partir de **01/01/2026** (regras de validação IBS/CBS); IS conforme cronograma da NT |
| **Obrigatoriedade 2025** | Preenchimento **facultativo**; validações **somente se campos informados** |
| **Obrigatoriedade 2026+** | Regras de validação IBS/CBS tornam-se **obrigatórias** quando aplicável |
| **Campos novos (item)** | Grupo **IBSCBS** (referência a tipos em `DFeTiposBasicos`): **CST** (`CST` IBS/CBS), **cClassTrib**, bases, alíquotas e valores IBS (UF/município), CBS, IS quando aplicável |
| **Campos novos (total)** | Grupo **IBSCBSTot** — totalizadores CBS, IBS UF, IBS municipal, IS |
| **Eventos** | NT prevê eventos específicos para apuração assistida (fora do escopo de emissão Nexus nesta fase) |
| **Schemas** | `nfe_v4.00.xsd` + inclusão `DFeTiposBasicos_v1.00.xsd`; pacote ZIP no Portal |

---

## 3. Impactos no XML (NF-e 55)

### Novos grupos (confirmados pela NT 2025.002)

| Grupo | Nível | Descrição |
|-------|-------|-----------|
| `IBSCBS` | Item (`det`) | Tributação IBS/CBS/IS por item — CST, cClassTrib, bases, alíquotas, valores, regimes especiais |
| `IBSCBSTot` | Total (`total`) | Totalizadores da reforma |
| Tipos em `DFeTiposBasicos_v1.00.xsd` | Referência | Padronização entre DF-e |

### Campos preparatórios Nexus (regras fiscais / snapshot — já existentes)

Alinhados a `REFORMA_TRIBUTARIA_KEYS` em `regras_fiscais/reforma_tributaria_config.py`:

- `cst_ibs_cbs`, `classificacao_tributaria`
- `aliquota_cbs`, `aliquota_ibs_estadual`, `aliquota_ibs_municipal`
- `reducao_cbs`, `reducao_ibs`, `diferimento_*`, `credito_presumido_*`

### O que **não** implementar nesta fase (4.0.13.4)

- Serialização `IBSCBS` / `IBSCBSTot` no XML de emissão (`REFORMA_TRIBUTARIA_NFE_INCLUIR_XML=false`)
- Alteração de XML já autorizado
- Tags sem mapeamento 1:1 com schema oficial validado

---

## 4. Impactos no DANFE

| Aspecto | Situação oficial / Nexus |
|---------|---------------------------|
| Exigência de exibição | NT 2025.002 foca **layout XML**; orientação DANFE específica deve ser confirmada no Manual de Especificações / MOC quando publicado para RTC |
| Nexus hoje | DANFE de **conferência** exibe resumo textual quando snapshot tem reforma (`reforma_conferencia_texto`) |
| Decisão 4.0.13.4 | **Não** alterar layout principal do DANFE BFR/HTML de emissão (`REFORMA_TRIBUTARIA_NFE_INCLUIR_DANFE=false`) |
| Homologação | Seção informativa futura somente após NT + schema + paridade XML↔DANFE |

---

## 5. Impactos na validação SEFAZ

| Regra | Detalhe |
|-------|---------|
| Homologação | Campos RTC validados **se informados**; ambiente de testes |
| Produção | Obrigatoriedade progressiva; **bloqueada no Nexus** até fase dedicada |
| Compatibilidade | XML **sem** grupos RTC continua válido enquanto facultativo |
| Rejeição | Campos RTC preenchidos incorretamente podem gerar rejeição — motivo para feature flag desligada |
| Schema | Validar contra pacote oficial do Portal antes de ativar `INCLUIR_XML` |

---

## 6. Decisão técnica Nexus (ERP 4.0.13.4)

### Implementar agora

1. Este documento e registro de fontes.
2. Pacote isolado `apps/fiscal/reforma_tributaria/` (config, cálculo neutro, stubs XML/DANFE, validações).
3. Feature flags (`REFORMA_TRIBUTARIA_NFE_*`) — **modo `pesquisa` por padrão**.
4. API/UI: seção **Reforma Tributária** no detalhe NF-e com estados (não aplicável / preparação / homologação / produção bloqueada).
5. Listagem compacta NF-e Saída (badges agrupados) — independente da reforma.
6. Testes: flags desligadas preservam XML; documentação existe; listagem enxuta.

### Preparado, não ativo

- `calcular_reforma_tributaria_nfe_item()` — estrutura neutra, alíquotas de config/regra, **sem** gravar em XML.
- Builders XML/DANFE retornam `None` salvo flags + modo `homologacao`.
- Reutilização de `get_reforma_tributaria_snapshot` / conferência 3.5.

### Fase futura (após validação schema + homologação controlada)

- Ativar `REFORMA_TRIBUTARIA_NFE_INCLUIR_XML` em homologação.
- Mapear bindings nfelib `IBSCBS` conforme versão do pacote instalado.
- DANFE espelhando XML.
- Testes XSD e transmissão homologação com RTC.

### Riscos

| Risco | Mitigação |
|-------|-----------|
| NT/schema em evolução | Documento versionado; flags; não fixar tags no código core |
| Rejeição SEFAZ | XML RTC desligado por padrão |
| Confusão DANFE vs Pedido | Reforma só NF-e/DANFE; PDF comercial do pedido sem RTC |
| Alíquotas “mágicas” | Config/regra fiscal; nunca hardcode de alíquota efetiva |

### Pendências

- [ ] Baixar e fixar versão exata da NT 2025.002 vigente no ambiente SEFAZ de homologação.
- [ ] Validar bindings nfelib vs `DFeTiposBasicos_v1.00.xsd`.
- [ ] Confirmar layout DANFE oficial para RTC quando publicado.
- [ ] Cronograma exato de obrigatoriedade por CRT/UF.

### Premissas

- Duplicatas (`cobr`/`dup`) e ICMS/PIS/COFINS atuais **não são alterados** nesta fase.
- Homologação permanece **fora da apuração** e **sem financeiro automático**.
- Nenhuma nova NF-e de homologação com RTC é **obrigada** enquanto flags estiverem em `pesquisa`/`preparacao`.

### API/UI (ERP 4.0.13.4.1)

| Endpoint | Campo | Comportamento |
|----------|-------|---------------|
| `GET /api/nf-saidas/{id}/` | `reforma_tributaria` | Payload de preparação (`status`, `status_label`, `config`, `alerta_homologacao`, `itens`, `totais`). Com flags desligadas: `status=nao_aplicavel`, sem valores inventados. |
| `GET /api/nf-saidas/` | `listagem_resumo` | Listagem enxuta (sem XML/itens); badge fiscal agrupado, atendimento máx. 2 badges + ocultos, `reforma_tributaria_status`. |
| XML/DANFE emissão | — | **Sem** grupos RTC nesta fase (`INCLUIR_XML` / `INCLUIR_DANFE` = false). |

### Checklist pré-homologação (ERP 4.0.13.5)

Enquanto RTC estiver em preparação, o checklist `validar_prontidao_nfe_homologacao` **impede inclusão indevida de tags no XML** quando flags RTC estiverem ativas sem implementação oficial. A validação é read-only: não transmite, não altera XML autorizado.

---

## 7. Feature flags (settings)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `REFORMA_TRIBUTARIA_NFE_ENABLED` | `false` | Master switch |
| `REFORMA_TRIBUTARIA_NFE_MODO` | `pesquisa` | `pesquisa` \| `preparacao` \| `homologacao` |
| `REFORMA_TRIBUTARIA_NFE_AMBIENTE_HOMOLOGACAO` | `true` | Permite experimentação só homologação |
| `REFORMA_TRIBUTARIA_NFE_INCLUIR_XML` | `false` | Grupos RTC no XML |
| `REFORMA_TRIBUTARIA_NFE_INCLUIR_DANFE` | `false` | Seção RTC no DANFE |

---

## 8. Referência rápida — diferença de documentos

| Documento | Contém Reforma / fiscal? |
|-----------|---------------------------|
| PDF comercial Pedido de Venda | **Não** |
| DANFE NF-e | Sim (quando flags + XML) |
| XML NF-e | Sim (grupos oficiais) |
| Modal/drawer NF-e no ERP | Sim (seção técnica) |
| Contas a receber | **Não** nesta fase |

---

## 9. Base IBS/CBS 2026 — modos parametrizados (ERP 4.0.13.6.11)

| Modo | Fórmula | Uso |
|------|---------|-----|
| `BASE_CHEIA_OPERACAO` | vProd | Padrão Nexus (legado); valor integral da operação |
| `BASE_SEM_ICMS` | vProd - vICMS | Cenário comparativo B |
| `BASE_SEM_ICMS_PIS_COFINS` | vProd - vICMS - vPIS - vCOFINS | Cenário comparativo C |
| `BASE_SEM_ICMS_PIS_COFINS_IPI` | + vIPI, vISS | Cenário D |
| `BASE_OFICIAL_2026` | Referência NT 2025.002 / LC 214 | Exclui tributos substituídos — **confirmar com contador** |
| `BASE_CUSTOMIZADA` | Flags manuais na regra | Deduzir ICMS/PIS/COFINS/IPI/ISS individualmente |

**Fonte da regra** (`fonte_regra_base_ibs_cbs`): `pendente` | `oficial` | `contador` | `comparativo_erp` | `manual`.

**Produção:** bloqueia se fonte = `pendente`. **Homologação:** alerta.

Implementação: `apps/fiscal/reforma_tributaria/base_ibs_cbs.py` → snapshot → XML via `reforma_tributaria/xml.py`.

**Não altera:** vProd, vNF, ICMS, PIS, COFINS, duplicatas, transporte, financeiro, estoque.
