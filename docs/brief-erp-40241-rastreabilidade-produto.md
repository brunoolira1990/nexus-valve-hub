# [Rastreabilidade do Produto — continuação do Centro de Informações] — ERP 4.0.15.2.41

**Classificação:** melhoria  
**Prioridade:** alta  
**Impacto produção:** baixo  
**Risco técnico:** baixo  

**Áreas afetadas:**
- Produtos
- Qualidade
- Estoque
- Fiscal (consulta)
- Comercial (consulta)

**Dependências:**
- Centro de Informações do Produto entregue na ERP 4.0.15.2.39
- Validação técnica do painel na ERP 4.0.15.2.40
- APIs existentes: `listar_corridas_disponiveis_produto`, conferência NF entrada, CQ, CF, corridas

---

## Contexto

As entregas **4.0.15.2.36 a 4.0.15.2.40** implementaram o **Centro de Informações** na aba **Painel operacional** (comercial, fiscal, qualidade resumida).

A aba **Rastreabilidade** do modal de produto permanece em **placeholder** (`ProdutoRastreabilidadeTab.tsx`), exibindo apenas aviso de fase futura e resumo da última corrida.

O objetivo desta fase é **completar a visão industrial do produto** — rastreio corrida/lote, certificados e documentos vinculados — **sem criar novas regras de negócio** e **sem alterar** estoque, fiscal, CQ ou corridas.

---

## Objetivo

Implementar a aba **Rastreabilidade** do produto como extensão do Centro de Informações, consolidando em uma única visão:

- Corridas/lotes do produto
- Certificados de qualidade (CQ) por corrida
- Certificados de fornecedor (CF) vinculados à entrada
- Clientes e NF-e de saída associados à corrida (quando rastreável)
- NF-e de entrada que originaram ou referenciam a corrida

Tudo **somente leitura**, usando dados já persistidos no ERP.

---

## Escopo

### Backend

**Arquivos principais:**
- `backend/apps/produtos/painel_operacional.py` (ou `painel_rastreabilidade.py` extraído)
- `backend/apps/produtos/views.py` — nova action no `ProdutoViewSet`
- Serializers/types apenas se necessário para contrato estável

**Endpoint sugerido:**

```
GET /api/produtos/{id}/painel/rastreabilidade/
```

Alternativa aceitável: campo `rastreabilidade` no payload de `painel/resumo/`, desde que o carregamento da aba continue **sob demanda** (não penalizar quem só abre Painel operacional).

**Blocos de resposta:**

| Bloco | Conteúdo | Fontes de dados (existentes) |
|-------|----------|------------------------------|
| `corridas` | Lista consolidada de corridas/lotes do produto | `listar_corridas_disponiveis_produto`, `Corrida`, `EstoqueCorrida` |
| `certificados_qualidade` | CQs do produto com corrida/lote por item | `CertificadoQualidade` + `ItemCertificadoQualidade` |
| `certificados_fornecedor` | CFs com itens do produto (corrida, NF entrada) | `CertificadoFornecedorEntrada` + `ItemCertificadoFornecedorEntrada` |
| `nfs_entrada` | NF-e entrada / conferência com referência a corrida ou lote | `ItemNFeEntrada`, `ItemNFeEntradaConferencia`, `Corrida.nf_entrada` |
| `nfs_saida` | NF-e saída e pedidos com corrida no item (quando houver) | `ItemNFeSaida`, `ItemPedidoVenda.corrida` |
| `clientes_por_corrida` | Agregação cliente × corrida a partir de saídas/CQs | Derivação dos blocos acima |

**Limite inicial por lista:** 20 registros (configurável via constante, alinhado ao painel que usa 10).

**Reutilizar:**
- `listar_corridas_disponiveis_produto` (mesma carga de `GET certificados-qualidade/corridas-disponiveis/`)
- Helpers de formatação já usados em `painel_operacional.py` (`_iso_date`, `_fmt_money`, etc.)
- `select_related` / `prefetch_related` para evitar N+1

### Frontend

**Arquivos principais:**
- `frontend/src/components/produtos/ProdutoRastreabilidadeTab.tsx` — substituir placeholder
- `frontend/src/types/index.ts` — interfaces `ProdutoPainelRastreabilidade`
- `frontend/src/services/api/produtos.ts` — `getPainelRastreabilidade(id)`
- `frontend/src/lib/produtoPainelOperacional.ts` — links para documentos (estender se necessário)

**UI sugerida (subseções ou acordeão):**

1. **Corridas e lotes** — tabela: corrida, lote, saldo, fornecedor, origem técnica, NF entrada, status CF
2. **Certificados de qualidade** — número, cliente, corrida, data, status, link CQ
3. **Certificados de fornecedor** — número, fornecedor, corrida, NF entrada, link CF
4. **NF-e entrada** — número, fornecedor, data, corrida/lote quando conhecido
5. **NF-e saída / clientes** — número, cliente, pedido, corrida quando vinculada

**Comportamento:**
- Carregar somente quando a aba **Rastreabilidade** estiver ativa (mesmo padrão do Painel operacional)
- Produto não salvo → mensagem “Salve o produto…”
- Estados: loading, erro, vazio por bloco
- Remover bloco tracejado “fase futura” após implementação

### O que NÃO fazer

- Não criar migrations
- Não criar tabelas novas
- Não alterar models
- Não alterar estoque (`EstoqueCorrida`, aplicação física)
- Não alterar fiscal (emissão, conferência, apuração)
- Não alterar CQ/CF (emissão, cancelamento, regras de rastreabilidade obrigatória)
- Não alterar corridas (cadastro técnico)
- Não alterar cadastro de produto (save)
- Não criar movimentação de estoque
- Não criar gráficos
- Não duplicar o Painel operacional — rastreabilidade é **visão por corrida/lote**, não repetir histórico comercial/fiscal já existente no painel

---

## Diferença Painel operacional × Rastreabilidade

| Aspecto | Painel operacional (2.39) | Rastreabilidade (2.41) |
|---------|---------------------------|-------------------------|
| Foco | Últimos movimentos e indicadores | Cadeia corrida → entrada → CQ → saída |
| Organização | Por tipo (compra, venda, fiscal) | Por **corrida/lote** e certificados |
| Público | Comercial, compras, gestão | Qualidade, estoque, auditoria industrial |
| Sobreposição | Resumo de corridas (10) e CQs (10) | Detalhe expandido + vínculos cruzados |

---

## Critérios de aceite

- [ ] Produto continua salvando normalmente
- [ ] Nenhuma regra de negócio alterada
- [ ] Aba Rastreabilidade carrega sob demanda sem impactar outras abas
- [ ] Corridas/lotes do produto exibidos com saldo e origem
- [ ] CQs do produto listados com corrida quando disponível
- [ ] CFs do produto listados com corrida e NF entrada quando disponível
- [ ] NF-e entrada relacionadas exibidas quando rastreáveis
- [ ] NF-e saída / clientes exibidos quando corrida vinculada no item ou CQ
- [ ] Links navegam para telas existentes (mesmas limitações do painel 2.40 documentadas)
- [ ] Sem N+1 grave no endpoint (auditar com `DEBUG` + contagem de queries)
- [ ] Performance aceitável (~mesmo patamar do painel: &lt; 100 ms em produto médio)

---

## Validação manual sugerida

1. Selecionar produto com **corrida em estoque** e CF/CQ emitidos
2. Abrir aba **Rastreabilidade** e conferir:
   - corrida aparece com saldo igual a `/estoque`
   - CQ listado bate com `/certificados` filtrado pelo produto
   - CF bate com `/certificados-fornecedor`
   - NF entrada da corrida bate com conferência ou NF operacional
3. Selecionar produto **sem rastreabilidade** → blocos vazios com mensagem amigável
4. Salvar/editar produto em outra aba → comportamento inalterado

---

## Confirmações obrigatórias na entrega

- [ ] Nenhuma migration criada
- [ ] Nenhuma regra de negócio alterada
- [ ] Apenas leitura e consolidação de dados
- [ ] Estoque não alterado
- [ ] Financeiro não alterado
- [ ] Fiscal não alterado
- [ ] CQ não alterado
- [ ] Corridas não alteradas

---

## Entrega técnica sugerida

| Item | Sugestão |
|------|----------|
| Branch | `feat/produto-rastreabilidade-40241` |
| Commit | `feat(produtos): rastreabilidade do produto na ficha` |
| Testes | Opcional: teste leve em `apps.produtos.tests` para payload e produto sem histórico |
| Docs | Atualizar `roadmap-nexus-erp.md` e `especificacao-nexus-erp.md` |

---

## Próximas evoluções (fora deste escopo)

- Deep links para pedido compra, CQ e corrida por ID
- Visão gráfica da cadeia corrida → cliente
- Relatório ponta a ponta (Estoque 3.13)
- Deduplicação inteligência de compras no painel (2.40 ressalva)
- Tela central de produtos fora do modal

---

*Brief elaborado em 24/06/2026 — continuação natural da linha 4.0.15.2.36–2.40.*
