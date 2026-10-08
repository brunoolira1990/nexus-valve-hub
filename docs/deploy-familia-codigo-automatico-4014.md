# Deploy — Geração automática / manual de codigo_figura (ERP 4.0.14.x)

## Decisão do operador — política de produção

**Confirmado:**

| Item | Decisão |
|------|---------|
| Política | `FAMILIA_CODIGO_POLITICA_PREFIXO=PREFIXO_GLOBAL_UNICIDADE` |
| Código manual | Continua permitido |
| Unicidade | NNNN+sufixo de **família de figura** ocupa o prefixo numérico |
| Sufixo no `codigo_figura` | **Válido** quando o template **não** o acrescenta |
| Alerta | Somente se o código-base repetir complemento já inserido pelo template |
| `VALOR_COMPLETO` / `PREFIXO_GLOBAL_SEQUENCIAL` | **Não** usar em produção; **sem** migration 0028 |

### Exemplos reais (produção — classificação contextual)

| Código | Classificação | Motivo |
|--------|---------------|--------|
| `0023OD` | Técnico com sufixo **válido** | Template não acrescenta OD |
| `0075OD` | Técnico com sufixo **válido** | Template não acrescenta OD |
| `6119` | Família NNNN **válida** | Template (`BASE_OD_MM_ESPESSURA`) acrescenta OD no produto (`6119OD…`) |
| `18900001-04DC` | Manual/fabricante | Sem formação por família; **fora** do diagnóstico de prefixo NNNN |

Lista informada pelo operador: **54** NNNN; maior NNNN **8010**; próximo código automático **provável 8011** (condicionado à auditoria direta do banco antes da migration 0027).

Em produção:

```env
FAMILIA_CODIGO_POLITICA_PREFIXO=PREFIXO_GLOBAL_UNICIDADE
```

Efeito sob unicidade: `0023OD` ocupa prefixo `0023`; `0075OD` ocupa `0075`; o gerador automático pulará esses prefixos. `MANUAL_FABRICANTE` não participa do conjunto de prefixos de figura (ex.: `18900001-04DC` não bloqueia `1890`).

**Orientação de UI:** informar o complemento no código da família somente quando o modelo de formação selecionado **não** o acrescentar automaticamente. Não há proibição genérica de OD/STD/40/N/NS/S.

---

## Contrato da API — criação de Família/Figura

Campo de entrada write-only (não persistido):

```json
{
  "modo_codigo": "AUTOMATICO" | "MANUAL",
  "codigo_figura": "..."
}
```

| `modo_codigo` | `codigo_figura` | Comportamento |
|---------------|-----------------|---------------|
| `AUTOMATICO` | omitido (ignorado se enviado) | Backend reserva NNNN via contador |
| `MANUAL` | obrigatório | Salva o código informado; **não** altera o contador |
| ausente | omitido | **Fallback `AUTOMATICO`** (compatível com a UI antiga) |
| ausente | preenchido | **Erro 400** em `modo_codigo` — não interpreta silenciosamente |

PATCH/PUT: `codigo_figura` e `modo_codigo` são ignorados (código imutável após criação).

### Aviso — complementar no código da família (contextual)

Informe o complemento no `codigo_figura` **somente** quando o modelo de formação selecionado **não** o acrescentar automaticamente (ex.: OD em `BASE_OD_MM_ESPESSURA` / `BASE_OD_POLEGADA_ESPESSURA`).

Códigos como `0023OD` e `0075OD` são válidos quando o template da família **não** acrescenta OD. A família `6119` com template que acrescenta OD está correta sem OD no código-base.

### Normalização do código manual

O código **não** é salvo byte a byte. Aplica-se a normalização operacional existente:

1. `strip()` de espaços externos
2. conversão para **maiúsculas** (`to_operational_upper`)
3. rejeição se vazio após trim
4. rejeição se length > 32
5. rejeição de caracteres de controle / quebras de linha (ord < 32)
6. unicidade avaliada **após** a normalização

Não há regex restritiva adicional; códigos manuais técnicos legítimos (que não sejam complementos de template) continuam válidos.

### Consumidores internos do `POST /api/familias-produto/`

Pesquisa versionada no repositório (frontend, services, testes, scripts, commands):

| Consumidor | Envia `modo_codigo`? | Observação |
|------------|----------------------|------------|
| `frontend/src/lib/familiaCodigo.ts` → `montarPayloadFamiliaSalvar` | **Sim** (sempre na criação) | `AUTOMATICO` ou `MANUAL`; não envia `codigo_figura` no automático |
| `frontend/src/pages/Produtos.tsx` | **Sim** (via helper) | Único consumidor de UI |
| `frontend/src/services/api/produtos.ts` `familiasProdutoService.create` | Encaminha payload | Sem montagem própria de código |
| `backend/.../test_familia_codigo_automatico.py` | **Sim** nos fluxos de contrato; 1 teste de fallback legado | Sem payload com `codigo_figura` órfão |
| Seeds / admin / management commands | N/A | Não há POST HTTP; ORM `objects.create` / `update_or_create` |
| Scripts / integrações versionadas | Nenhum encontrado | — |

**Impacto em clientes legados (fallback mantido):**

| Payload legado | Comportamento | Justificativa |
|----------------|---------------|---------------|
| Sem `modo_codigo`, sem `codigo_figura` | `AUTOMATICO` | Compatível com UI anterior à escolha explícita |
| Sem `modo_codigo`, com `codigo_figura` | HTTP 400 | Evita descartar silenciosamente o código enviado |
| Com `modo_codigo` explícito | Conforme contrato | Consumidores internos atualizados |

Fallback **não** foi removido: UI atual já envia `modo_codigo`; remover o fallback quebraria clientes externos não versionados neste repositório sem aviso.

### Políticas de referência (histórico)

| Política | Ocupação do candidato NNNN | Uso neste ERP |
|----------|---------------------------|---------------|
| **PREFIXO_GLOBAL_UNICIDADE** | Sufixo ocupa base (`6119OD` bloqueia `6119`) | **Produção** |
| **VALOR_COMPLETO** | Só NNNN exato | Não usar em produção |
| **PREFIXO_GLOBAL_SEQUENCIAL** | Piso = maior prefixo + 1 | Não usar; sem 0028 |

**Dev/homolog:** fallback `VALOR_COMPLETO` com alerta (somente desenvolvimento).
**Produção:** variável ausente/inválida → bloqueio; valor correto = `PREFIXO_GLOBAL_UNICIDADE`.

### Impacto na migration 0027

| Política | Migration 0027 |
|----------|----------------|
| PREFIXO_GLOBAL_UNICIDADE | **Permanece inalterada**; runtime pula prefixos ocupados |
| VALOR_COMPLETO | Não aplicável em produção |
| PREFIXO_GLOBAL_SEQUENCIAL | Exigiria 0028 — **não criar** |

---

## Migrate automático no repositório

`docker-compose.yml` e `docker-compose.prod.yml` executam `python manage.py migrate` no startup do backend.

**Não assumir** que produção usa esse Compose — confirmar com a operação.

---

## Gates obrigatórios (nenhum backend com 0027 pendente sobe pelo fluxo normal antes de)

1. Backup confirmado
2. `auditar_codigo_figura_familia` executado em produção
3. `FAMILIA_CODIGO_POLITICA_PREFIXO` definida explicitamente
4. Parecer APTO para a política escolhida
5. Mecanismo de deploy confirmado (manual vs migrate no startup)

---

## CENÁRIO 1 — Migration manual

1. Backup
2. Auditoria read-only
3. Definir política no `.env` de produção
4. Decisão APTO/BLOQUEADO
5. Bloquear criação de famílias (janela)
6. `python manage.py migrate produtos 0027 --noinput`
7. `manage.py check` + auditoria pós-migration
8. Retomar operação

---

## CENÁRIO 2 — Migrate automático no startup

**Não reiniciar** backend com 0027 pendente antes dos gates.

Diagnóstico one-off (adaptar ao ambiente):

```bash
docker compose run --rm --no-deps backend \
  python manage.py auditar_codigo_figura_familia
```

Somente após APTO: subir backend normalmente.

---

## Rollback coordenado (código + banco)

1. Interromper novas criações de famílias
2. Reverter **versão da aplicação** (imagem/deploy anterior)
3. Se necessário: `python manage.py migrate produtos 0026`
4. Reiniciar backend na versão antiga
5. `manage.py check`
6. Validar consulta/edição de família existente
7. **Não** excluir/renumerar famílias criadas no período

Reverter só migration mantendo código novo → app tenta acessar tabela inexistente. Rollback deve ser **coordenado**.

---

## Smoke test visual / funcional (2026-07-13 — local/homolog isolado)

Ambiente: Docker local. Browser MCP indisponível nesta sessão; verificação combinada:

- UI contract no código (`Produtos.tsx` + `familiaCodigo.test.ts`)
- Smoke API funcional com dados sintéticos prefixo `SMOKE4014X` (criados e **excluídos** ao final; sem dados reais)

| # | Passo | Resultado |
|---|-------|-----------|
| 1 | Produtos > Famílias — AUTOMATICO padrão | OK — `modo_codigo_figura: 'AUTOMATICO'` em `emptyFamiliaQuick`; radio “Gerar automaticamente” checked por padrão |
| 2 | Mensagem geração automática | OK — `MENSAGEM_CODIGO_FIGURA_AUTO` exibida no modo automático |
| 3 | Criar família automática / código retornado | OK — API `modo_codigo=AUTOMATICO` → NNNN (ex. sintético `9410`) |
| 4 | Criar manual código técnico sintético | OK — `modo_codigo=MANUAL`, `codigo_figura='  smk8od  '` |
| 5 | Normalização maiúsculas | OK — persistido `SMK8OD` |
| 6 | Duplicidade | OK — HTTP 400 “Já existe uma Família/Figura com este código.” |
| 7 | Edição somente leitura | OK — PATCH com outro código preserva `SMK8OD` |
| 8 | Produto/prévia dimensional (família auto NPS) | OK — `montar_codigo_interno` → `{NNNN}.05` |
| 9 | Família manual disponível para vínculo | OK — registro `SMK8OD` válido após normalização |
| 10 | Restaurar ambiente | OK — famílias sintéticas `SMOKE4014X*` excluídas |

---

## Validação manual anterior (ambiente isolado)

Executada em **2026-07-13** no ambiente local Docker (`homologacao`), via suíte `FamiliaCodigoAutomaticoApiTests` + testes unitários equivalentes aos passos de UI. Nenhuma escrita em produção.

| # | Passo | Resultado |
|---|-------|-----------|
| 1 | Criar família sem código (API `POST /familias-produto/` sem `codigo_figura`) | OK — `201`, código gerado |
| 2 | Confirmar código automático | OK — `7000` com contador em 7000 |
| 3 | Segunda família avança | OK — contador incrementa (`7001` após ocupar 7000 manualmente) |
| 4 | Editar descrição — código imutável | OK — PATCH com `codigo_figura: 9999` ignorado; código preservado |
| 5 | Criar manualmente próximo candidato | OK — `FamiliaProduto.objects.create(codigo_figura='7000')` |
| 6 | API pula ocupado | OK — POST automático retorna `7001` |
| 7 | Produto vinculado | OK — `montar_codigo_interno` → `{codigo_figura}.05` |
| 8 | Prévia dimensional | OK — `montar_codigo_interno` e template NPS inalterados (sem alteração em `montar_codigo_interno`) |
| 9 | Esgotamento com contador 10000 | OK — `400` com mensagem contendo "esgotada" |
| 10 | Restaurar ambiente de teste | OK — banco de testes isolado (`--keepdb`); sem alteração em dados de homolog/prod |

**Nota:** passos 1–9 cobertos por `test_familia_codigo_automatico.py` (API + unitários). UI visual contract coberto no frontend (`familiaCodigo.test.ts`).

---

## Baseline — seis falhas em `test_equivalencia_composicao_generica.py`

Comparação **HEAD (`1c36fcd`)** vs **working tree com família automática** — mesmos resultados.

| Teste | Baseline | Atual | Mensagem resumida |
|-------|----------|-------|---------------------|
| `DescricaoNormalizacaoGenericaTests.test_normaliza_polegadas_material_classe` | FAIL | FAIL | `'4P' not found in '... INOX304 4'` |
| `EquivalenciaCompostaGenericaTests.test_confirmar_registra_rastreabilidade_sem_estoque` | ERROR | ERROR | `IntegrityError`: `codigo_figura=(FCMP-) already exists` |
| `EquivalenciaCompostaGenericaTests.test_rejeicao_registra_historico` | ERROR | ERROR | idem `FCMP-` |
| `EquivalenciaCompostaGenericaTests.test_sugestao_composta_por_regra_cadastrada` | ERROR | ERROR | idem `FCMP-` |
| `EquivalenciaSimplesGenericaTests.test_equivalencia_simples_por_codigo` | ERROR | ERROR | idem `FCMP-` |
| `MontagemRoscaGenericaTests.test_montagem_roscada_nao_exige_servico` | ERROR | ERROR | idem `FCMP-` |

**Conclusão: SEM REGRESSÃO** — falhas pré-existentes (helper `_criar_prod` gera `codigo_figura` colidente `F{codigo[:4]}`).
