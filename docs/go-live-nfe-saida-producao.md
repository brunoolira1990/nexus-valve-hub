# Go-live NF-e Saída — produção SEFAZ (Nexus ERP)

Documento formal de **planejamento e ativação futura** da emissão de NF-e de venda em **produção SEFAZ** pelo Nexus ERP.

| Campo | Valor |
|-------|-------|
| **Versão ERP** | 4.0.15.x |
| **Escopo** | NF-e Saída (modelo 55) — emissão própria de venda |
| **Status** | Homologação madura · **Fases 3B + 3C concluídas** · **Saneamento pré-T0 em andamento** · **Fase 3D T0 ABORTADA** · Produção **desligada** |
| **Última revisão** | 2026-06-02 (saneamento pré-T0) |
| **Diagnóstico base** | Suítes 402 (26 OK), 4015 produção, conferência UI; **nenhuma NF-e produção real transmitida** |

> **Regra Nexus:** este documento **não autoriza** ligar produção SEFAZ automaticamente. A **primeira emissão real** exige janela controlada (Fase 3D operacional), checklist assinado, contador/fiscal presente e ação explícita de ligar `NFE_PRODUCAO_HABILITADA=true`.

---

## 1. Resumo executivo

O Nexus ERP possui pipeline **completo e testado** para emissão de NF-e de saída em **homologação SEFAZ** (ERP 4.0.2+): conferência, validação, reserva de numeração, XML oficial, assinatura A1, transmissão, protocolo, `xml_autorizado` e DANFE via BrazilFiscalReport (BFR).

A emissão em **produção SEFAZ** possui **backend Fase 3B** (flag, endpoints, serviços separados, testes mockados) e **UI Fase 3C** (painel produção na conferência, confirmação dupla, permissões restritas), porém permanece **desligada por padrão** (`NFE_PRODUCAO_HABILITADA=false`). O go-live real depende de flag explícita, Fase 3D, validação fiscal/contábil e plano de rollback.

**Parecer atualizado (2026-06 — pós Fase 3C, prep 3D):**

| Situação | Resultado |
|----------|-----------|
| Emitir NF-e venda em produção SEFAZ **hoje** (flag default) | **BLOQUEADO** |
| Testar pipeline produção em ambiente controlado (flag + mock) | **APTO** |
| Software pronto para janela de 1ª emissão real (3B+3C+runbook) | **APTO COM PENDÊNCIAS** |
| Janela de go-live operacional (1ª NF real) | **APTO COM PENDÊNCIAS** — depende de checklist fiscal/operacional e presença contador/fiscal |

---

## 2. Homologação vs produção

| Aspecto | Homologação SEFAZ | Produção SEFAZ |
|---------|-------------------|----------------|
| **Finalidade** | Testes sem valor fiscal; fora da apuração | Documento fiscal válido; entra na apuração |
| **`tpAmb` no XML** | `2` | `1` |
| **Numeração ERP** | Série `0` (padrão por empresa) | Série `1` (padrão por empresa) |
| **Status SEFAZ esperado** | `AUTORIZADA_HOMOLOGACAO` | `AUTORIZADA_PRODUCAO` (**Fase 3B**) |
| **Endpoint de emissão** | `POST /api/nf-saidas/{id}/emitir-homologacao/` | `POST /api/nf-saidas/{id}/emitir-producao/` (**bloqueado sem flag**) |
| **Checklist pré-emissão** | `40135` homologação | `GET .../validar-emissao-producao/` (**Fase 3B**) |
| **Transmissão** | `transmitir_nfe_homologacao()` — ativo | `transmitir_nfe_producao()` — **só com flag true** |
| **UI conferência** | Botões «Emitir em homologação» | Painel «PRODUÇÃO SEFAZ — documento fiscal real» (**Fase 3C** — bloqueado sem flag/permissão) |
| **Efeitos ERP** | Sem estoque/financeiro real (`MSG_SEM_EFEITOS_REAIS`) | **Não definido** nesta fase — fora do escopo 3B–3D inicial |
| **Apuração fiscal** | Excluída (`dfe_classificacao` homologação) | Entra na apuração operacional |
| **Reforma Tributária (RTC)** | Pesquisa/preparação; alertas no checklist | `producao_bloqueada: True` até validação oficial |
| **Distinção visual** | Badges «Homologação», «Sem valor fiscal», «Fora da apuração» | Tokens `producao`, `autorizada_producao` existem na listagem; emissão prod ausente |

---

## 3. Estado atual (o que já existe)

### 3.1 Homologação — madura

Fluxo backend (`nfe_emissao/servico.py` → `emitir_nfe_homologacao`):

1. Validação pré-emissão (`validar_pre_emissao_homologacao`)
2. Reserva atômica de numeração (`reservar_numeracao_nfe`, ambiente homologação)
3. Geração XML oficial (`gerar_xml_oficial_emissao`, `tpAmb=2`)
4. Assinatura A1 PyNFe (`nfe_emissao/assinatura.py`)
5. Transmissão SEFAZ homologação (`transmitir_nfe_homologacao`)
6. Persistência protocolo/cStat/`xml_autorizado` (`aplicar_resultado.py`)
7. DANFE BFR do XML autorizado (`danfe_render.py`, endpoint `danfe-homologacao`)

**UI:** modal de conferência (`NFeSaidaConferenciaModal.tsx`) com permissões `pode_emitir_homologacao` / `pode_tentar_emitir_homologacao`; checklist pré-homologação (`40135`).

**Testes de referência:**

- `test_nfe_saida_402_emissao_homologacao.py` — 26 testes OK
- `test_nfe_saida_40135_checklist_homologacao.py`
- `test_nfe_saida_402_pos_autorizacao_homolog.py`

### 3.2 Produção — Fase 3B implementada (desligada por padrão)

| Camada | Arquivo | Comportamento atual |
|--------|---------|---------------------|
| Flag | `settings.NFE_PRODUCAO_HABILITADA` | Default **`false`** (`.env.example`) |
| Gate | `nfe_emissao/config_producao.py` | `exigir_producao_habilitada()` |
| Numeração | `nfe_emissao/numeracao.py` | Reserva produção **só com flag true** |
| Validação | `nfe_emissao/validacao_producao.py` | `validar_pre_emissao_producao()`, checklist read-only |
| Transmissão | `nfe_emissao/transmissao_producao.py` | `transmitir_nfe_producao()` — PyNFe `homologacao=False`, exige `tpAmb=1` |
| Orquestração | `nfe_emissao/servico_producao.py` | `emitir_nfe_producao()` — confirmação explícita no payload |
| Resultado | `nfe_emissao/aplicar_resultado.py` | `aplicar_resultado_sefaz_producao()` → `AUTORIZADA_PRODUCAO` |
| API | `views.py` | `POST emitir-producao/`, `GET validar-emissao-producao/` |
| Homolog (inalterado) | `transmissao.py`, `servico.py` | Continua bloqueando `tpAmb=1` e ambiente produção |

**Confirmação obrigatória no payload (`emitir-producao`):**

```json
{
  "confirmar_emissao_producao": true,
  "confirmar_ambiente": "PRODUCAO_SEFAZ"
}
```

**Respostas de bloqueio:**

- Flag ausente/false → HTTP **403** — «Emissão NF-e produção não habilitada.»
- Sem confirmação → HTTP **400**

**Testes:** `test_nfe_saida_producao_4015.py` (17), `test_nfe_saida_producao_4015_conferencia_ui.py` (4), `nfeSaidaEmissaoProducaoUi4015.test.tsx` (10).

**Limitações Fase 3B/3C:**

- Sem transmissão real em CI/testes
- Sem estoque/financeiro/apuração automática pós-autorização produção
- Sem DANFE endpoint dedicado produção (BFR do `xml_autorizado` — endpoint homolog não serve prod)
- Sem cancelamento/CC-e/inutilização
- Banner topbar `NEXUS_APP_AMBIENTE=producao` — pendente (opcional Fase 3D)

**Homologação permanece intacta** — `emitir-homologacao` inalterado; regressão na suíte 402.

### 3.3 Prontidão geral ERP (não específica SEFAZ prod)

Comando `python manage.py verificar_prontidao_producao` (`apps/core/prontidao_producao.py`) avalia ERP 4.0.14.9 — cadastros, financeiro mínimo, usuários — **não substitui** checklist SEFAZ produção deste documento.

**Pendências observadas no ambiente de diagnóstico:**

- Usuário ativo sem perfil/grupo (crítico)
- `DEBUG=True` pendente para produção
- Regra fiscal de entrada incompleta (não bloqueia saída diretamente, mas indica maturidade fiscal geral)
- Backup e limpeza de dados de teste não confirmados

---

## 4. Bloqueios técnicos atuais (referência)

Mensagens explícitas no código — **não alterar sem fase autorizada**:

```
Emissão em produção não está habilitada nesta fase.
  → nfe_emissao/numeracao.py (reservar_numeracao_nfe)
  → nfe_emissao/validacao.py (validar_pre_emissao_homologacao)

Transmissão em produção bloqueada nesta fase.
  → nfe_emissao/transmissao.py (transmitir_nfe_homologacao)

XML com tpAmb=1 (produção) não pode ser transmitido nesta fase.
  → nfe_emissao/transmissao.py
```

**Variáveis de ambiente relevantes (nomes apenas — valores reais fora deste doc):**

| Variável | Papel |
|----------|-------|
| `NFE_AMBIENTE` | Default documentado: `homologacao` (`.env.example`) |
| `NEXUS_APP_AMBIENTE` | Banner visual dev / homologação / produção |
| `DANFE_RENDERER_OFICIAL` | Default `BFR` — renderer exclusivo |
| `DANFE_BLOCK_EMISSION_IF_BFR_FAILS` | Bloqueia emissão se BFR falhar |
| `DANFE_ALLOW_HTML_FALLBACK` | Default `false` |
| `REFORMA_TRIBUTARIA_NFE_*` | RTC em pesquisa; produção RTC bloqueada |
| `FISCAL_NFE_SERIE_PRELIMINAR` | Série preliminar (não produção) |

**Flag implementada (Fase 3B):** `NFE_PRODUCAO_HABILITADA` — gate explícito; **default false**.

---

## 5. Pendências antes do go-live

### 5.1 Técnicas (implementação)

- [x] Flag `NFE_PRODUCAO_HABILITADA` com default `false` **(Fase 3B)**
- [x] Endpoint `POST /api/nf-saidas/{id}/emitir-producao/` **(Fase 3B — bloqueado sem flag)**
- [x] `GET /api/nf-saidas/{id}/validar-emissao-producao/` **(Fase 3B)**
- [x] Serviço `emitir_nfe_producao()` espelhando homologação com `tpAmb=1` **(Fase 3B)**
- [x] Função `transmitir_nfe_producao()` separada **(Fase 3B)**
- [x] Desbloqueio condicional em numeração/validação/transmissão com flag **(Fase 3B)**
- [x] Testes automatizados mock SEFAZ **`test_nfe_saida_producao_4015.py` (Fase 3B)**
- [x] Permissões `pode_emitir_producao` na conferência **(Fase 3C)**
- [x] UI com confirmação dupla e distinção visual irreversível **(Fase 3C)**
- [ ] Comando checklist dedicado SEFAZ produção (complementar a `verificar_prontidao_producao`)

### 5.2 Operacionais / fiscais

- [ ] Decisão formal da direção + contador/fiscal responsável
- [ ] Certificado A1 válido (CNPJ, vencimento, senha) — validar via `/nfe-sefaz` e `validar-certificado-nfe`
- [ ] Empresa emitente: CNPJ, IE, regime (CRT), endereço, município/UF, CEP consistentes
- [ ] Série e próximo número **produção** conferidos com última NF emitida na SEFAZ
- [ ] Credenciamento NF-e produção no estado (quando aplicável)
- [ ] Smoke test: 1 NF homolog com dados reais antes de qualquer prod
- [ ] Plano de cancelamento/inutilização documentado com contador
- [ ] Backup completo do banco imediatamente antes do 1º teste produção
- [ ] Usuários com perfis corretos; `DEBUG=False`; hosts/CORS/CSRF de produção
- [ ] Posicionamento sobre Reforma Tributária (RTC) no XML produção

### 5.3 Riscos conhecidos

1. **Numeração desalinhada** — série 1 no ERP divergente do cadastro SEFAZ → rejeição ou duplicidade
2. **Certificado inválido** — falha na 1ª transmissão real
3. **Confusão homolog/prod** — operador emite no ambiente errado sem UI clara
4. **RTC** — tags de Reforma Tributária em produção bloqueadas até decisão oficial
5. **Efeitos colaterais ERP** — homolog não movimenta estoque/financeiro; produção real exigirá fase posterior explícita
6. **Rollback incompleto** — nota autorizada em prod não se desfaz só revertendo `.env`

---

## 6. Arquitetura esperada (fases 3B / 3C / 3D)

### Fase 3B — Backend produção SEFAZ (sem UI) — **CONCLUÍDA**

**Entregue em ERP 4.0.15.x:** flag, endpoints, serviços separados, testes mockados. Produção permanece **desligada por padrão**.

| Componente | Status |
|------------|--------|
| Flag `NFE_PRODUCAO_HABILITADA` | **OK** |
| `emitir-producao` + confirmação payload | **OK** |
| `validar-emissao-producao` | **OK** |
| `transmitir_nfe_producao()` | **OK** |
| `aplicar_resultado_sefaz_producao()` | **OK** |
| Testes `test_nfe_saida_producao_4015.py` | **OK** (16) |
| UI produção | **OK — Fase 3C** |

---

### Fase 3C — UI e governança operacional — **CONCLUÍDA**

**Entregue em ERP 4.0.15.x:** painel produção na conferência NF-e Saída, confirmação dupla, permissões restritas (grupo `fiscal` **excluído**). Produção permanece **desligada por padrão**.

| Componente | Status |
|------------|--------|
| `permissoes_producao.py` — `usuario_pode_emitir_nfe_producao()` | **OK** (ver §6.1) |
| `conferencia_producao.py` — checklist + `emissao_producao` na conferência | **OK** |
| `NFeSaidaEmissaoProducaoPanel.tsx` — badge vermelho, modal dupla confirmação, `GET validar-emissao-producao` | **OK** |
| Payload `confirmar_emissao_producao` + `confirmar_ambiente=PRODUCAO_SEFAZ` | **OK** |
| Testes backend `test_nfe_saida_producao_4015_conferencia_ui.py` | **OK** (7) |
| Testes frontend `nfeSaidaProducaoUi4015.test.tsx` | **OK** (15) |
| Homologação UI | **Intacta** |

#### 6.1 Permissão `pode_emitir_producao` (Fase 3C)

**Onde está definida:** `backend/apps/fiscal/nfe_emissao/permissoes_producao.py` — função `usuario_pode_emitir_nfe_producao()`.

**Quem pode emitir produção:**

| Perfil | Produção SEFAZ |
|--------|----------------|
| `superuser` | Sim |
| Grupo `admin` | Sim |
| Grupo `administrador` | Sim |
| Grupo `fiscal_nfe_producao` | Sim (fiscal **explicitamente** autorizado) |
| Grupo `fiscal` (genérico) | **Não** |
| Demais usuários | **Não** |

**Regra:** permissão de **homologação** (`pode_emitir_homologacao`) **não** implica `pode_emitir_producao`. São independentes.

**Campos expostos na conferência (`permissoes` + `emissao_producao`):**

- `producao_habilitada` — espelha flag `NFE_PRODUCAO_HABILITADA`
- `usuario_pode_emitir_producao` — perfil do usuário logado
- `pode_emitir_producao` — flag + perfil + checklist + NF pronta (default **false**)
- `motivos_bloqueio_producao` — lista de motivos quando bloqueado
- `status_producao_label` — rótulo amigável do status SEFAZ produção

**Como testar usuário sem permissão:**

1. Usuário no grupo `fiscal` (sem `fiscal_nfe_producao`) → `pode_emitir_producao=false`, mensagem de permissão na UI.
2. Backend: `python manage.py test apps.fiscal.tests.test_nfe_saida_producao_4015_conferencia_ui --keepdb`
3. Frontend: `npm run test -- --run nfeSaidaProducaoUi4015`

**Confirmação dupla (UI):** checkbox «Entendo que esta NF-e será transmitida…» + digitar `PRODUCAO SEFAZ` → payload `{ confirmar_emissao_producao: true, confirmar_ambiente: "PRODUCAO_SEFAZ" }`. O endpoint `emitir-producao` continua validando flag e confirmação independentemente da UI.

---

### Fase 3B — Backend produção SEFAZ (sem UI) — especificação original

| Componente | Especificação |
|------------|---------------|
| **Flag** | `NFE_PRODUCAO_HABILITADA` em `settings.py` (default `false`); documentada em `.env.example` |
| **Gate** | Helper `producao_sefaz_habilitada()` consultado em numeração, validação, transmissão e views |
| **Validação** | `validar_pre_emissao_producao()` — espelho de homolog, exige `ambiente_emissao=PRODUCAO`, conferência pronta, certificado A1, numeração prod configurada |
| **Numeração** | `reservar_numeracao_nfe(..., ambiente=PRODUCAO)` — desbloqueado só com flag; série prod (ex.: `1`); validação de série fiscal real (não série `0` homolog) |
| **XML** | `gerar_xml_transmissao_producao` → `tpAmb=1`; reutilizar `gerar_xml_oficial_emissao` |
| **Assinatura** | Mesmo fluxo A1 (`assinatura.py`) |
| **Transmissão** | `transmitir_nfe_producao()` — PyNFe **sem** override `homologacao=True`; UF da empresa emitente |
| **Resultado** | `aplicar_resultado_autorizacao_producao()` — status `AUTORIZADA_PRODUCAO`, `xml_autorizado`, protocolo; **sem** efeitos estoque/financeiro nesta fase |
| **Endpoint** | `POST /api/nf-saidas/{id}/emitir-producao/` — retorno alinhado a `montar_resposta_emissao_homologacao` |
| **Logs/eventos** | `NFeSaidaEvento`: `EMISSAO_PRODUCAO_INICIADA`, `NUMERACAO_RESERVADA`, `XML_GERADO`, `ASSINATURA_OK`, `TRANSMISSAO_SEFAZ`, `AUTORIZADA_PRODUCAO`, `ERRO_TRANSMISSAO_SEFAZ` |
| **Testes** | Mock SEFAZ; assert bloqueio com flag off; assert rejeição `tpAmb=1` enquanto flag off |

**Critério de conclusão 3B:** testes passando; flag off mantém bloqueio atual; nenhuma rota UI nova.

---

### Fase 3C — UI e governança operacional

**Objetivo:** permitir emissão produção apenas para perfis autorizados, com confirmação dupla e distinção visual clara.

| Componente | Especificação |
|------------|---------------|
| **Permissões API** | `pode_emitir_producao`, `pode_tentar_emitir_producao`, `motivo_emitir_producao_bloqueado` em `nfe_saida_conferencia.py` |
| **Conferência modal** | Botão «Emitir em produção SEFAZ» separado de homolog; cor/ícone distintos (ex.: vermelho vs amarelo) |
| **Confirmação dupla** | Modal 1: aviso legal + resumo NF (cliente, valor, série/nº previsto); Modal 2: digitar confirmação (`PRODUÇÃO` ou CNPJ emitente) |
| **Banner ambiente** | `NEXUS_APP_AMBIENTE=producao` + badge persistente «AMBIENTE PRODUÇÃO» no topbar |
| **Listagem** | Filtro produção já existe; reforçar coluna ambiente pós-emissão |
| **DANFE** | Endpoint `danfe-producao` ou reutilizar BFR com XML autorizado prod; marca d'água **sem** «homologação» |
| **Download** | `download_xml_autorizado` — funcional para prod quando autorizada |
| **Checklist pré-prod** | Estender checklist `40135` ou criar `checklist-producao` read-only antes do botão habilitar |
| **Auditoria** | Registrar usuário, IP (se disponível), timestamp nos eventos |

**Critério de conclusão 3C:** operador não consegue emitir prod sem dupla confirmação; homolog permanece intacto.

---

### Fase 3D — Primeira emissão produção SEFAZ em janela controlada

**Status:** janela T0 **ABORTADA** (2026-06-02) · **1ª emissão real não executada** · flag permanece **`false`** · ver **§3D.9**

**Objetivo:** transmitir a **primeira NF-e de venda** (modelo 55, tpAmb=1) com validade fiscal, em ambiente controlado, com contador/fiscal e responsável técnico presentes.

**Quem deve estar presente na janela T0:**

| Papel | Responsabilidade |
|-------|------------------|
| **Operador emissor** | Usuário com grupo `fiscal_nfe_producao` (ou admin) — único autorizado a clicar «Emitir em produção SEFAZ» |
| **Contador / fiscal** | Validar XML, impostos, CFOP, numeração, DANFE; orientar em rejeição/cancelamento/inutilização |
| **Responsável técnico** | Flag, backup, logs, rollback técnico, consulta status SEFAZ em timeout |
| **Decisor operacional** (opcional) | Autorizar ligar/desligar flag após smoke test |

---

#### 3D.1 Pré-requisitos obrigatórios (antes de qualquer janela)

Todos os itens abaixo devem estar **OK** ou com **aceite formal por escrito** do contador/decisor.

| # | Item | Como validar |
|---|------|--------------|
| 1 | `NFE_PRODUCAO_HABILITADA=false` até T0 | Confirmar `.env` / variável de ambiente — **não alterar antes da janela** |
| 2 | Backup completo do banco | Snapshot/restore testado; registrar data/hora/responsável |
| 3 | Certificado A1 válido | `GET /api/empresas/{id}/validar-certificado-nfe/` — CNPJ do cert = CNPJ emitente; validade ≥ 30 dias |
| 4 | Empresa emitente revisada | CNPJ, IE, CRT/regime, endereço, município/UF/CEP/IBGE no cadastro |
| 5 | Numeração produção | `NFeNumeracaoConfiguracao` ambiente produção — série e `proximo_numero` conferidos com contador/portal SEFAZ |
| 6 | Cliente real da NF | CNPJ/CPF, IE (se aplicável), endereço fiscal, município/UF/CEP consistentes |
| 7 | Produtos / itens | NCM, unidade, CFOP, CST/CSOSN/impostos conforme regra fiscal de saída |
| 8 | Pedido / faturamento / NF rascunho | Conferência completa; status «Pronta para emissão» |
| 9 | DANFE BFR | Smoke em **homologação** com mesmos dados; renderer BFR OK |
| 10 | Permissão produção | Apenas o emissor da janela no grupo `fiscal_nfe_producao` (remover de demais usuários) |
| 11 | Contador/fiscal | Disponível presencial ou remoto em tempo real na janela |
| 12 | Responsável técnico | Disponível para flag, logs e rollback |
| 13 | Tipo de operação | **Venda normal** — não remessa, triangular, devolução, entrada própria ou operação especial |
| 14 | Cancelamento/inutilização | Procedimento **fora do Nexus** (portal SEFAZ/contador) acordado — ERP ainda não implementa cancel/CC-e/inutilização |

---

#### 3D.2 Checklist técnico antes da janela (T-1 ou T0 manhã)

Executar e **registrar resultado** (data, responsável, OK/FALHA):

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py verificar_prontidao_producao
docker compose exec backend python manage.py test apps.fiscal.tests.test_nfe_saida_producao_4015 --keepdb
docker compose exec backend python manage.py test apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao --keepdb
docker compose exec frontend npm run build
```

| Comando | Critério de sucesso | Bloqueante? |
|---------|---------------------|-------------|
| `manage.py check` | 0 issues | **Sim** |
| `test_nfe_saida_producao_4015` | Todos OK (mock SEFAZ) | **Sim** |
| `test_nfe_saida_402_emissao_homologacao` | Todos OK | **Sim** |
| `npm run build` | Build concluído | **Sim** |
| `verificar_prontidao_producao` | Sem críticos | **Parcial** — ver tabela abaixo |

**Críticos conhecidos em `verificar_prontidao_producao` (ambiente dev):**

| Item | Bloqueante para 1ª NF saída prod? | Ação |
|------|-----------------------------------|------|
| Usuário ativo sem perfil/grupo | **Sim** em produção real | Corrigir antes da janela |
| `DEBUG=True` | **Sim** em produção real | `DEBUG=False` no ambiente operacional |
| Backup não confirmado | **Sim** | Executar backup e registrar |
| Regra fiscal entrada incompleta | **Não** para NF-e **saída** venda | Aceite formal se operação for só saída |
| Nenhum título financeiro | **Não** | Informativo |

**Registro Fase 3D-prep (2026-06-02):**

| Verificação | Resultado |
|-------------|-----------|
| `manage.py check` | OK (0 issues) |
| `verificar_prontidao_producao` | **Crítico:** 1 usuário sem perfil; **Pendente:** DEBUG, backup |
| `npm run build` | OK |
| `test_nfe_saida_producao_4015` | OK em execuções anteriores (17 testes); **reexecutar obrigatoriamente na janela T0** |
| `test_nfe_saida_402_emissao_homologacao` | OK em execuções anteriores (26 testes); **reexecutar na janela T0** |

---

#### 3D.3 Checklist fiscal antes da emissão (T0 — na conferência da NF)

Preencher **na UI de conferência** e com contador:

- [ ] Série produção e próximo número = esperado pelo contador/SEFAZ
- [ ] Nenhuma NF emitida **fora do Nexus** com número que colida
- [ ] Natureza da operação (`natOp`) correta
- [ ] CFOP por item conferido
- [ ] ICMS, PIS, COFINS, IPI (e demais) conferidos item a item
- [ ] Duplicatas/cobrança no XML/DANFE, se aplicável
- [ ] Operação = **venda normal** (não remessa/triangular/devolução/entrada própria)
- [ ] Checklist produção na UI (`GET validar-emissao-producao`) **sem pendências bloqueantes**
- [ ] Contador confirma procedimento de **cancelamento** (24h) ou **inutilização** via SEFAZ/contador, se necessário

---

#### 3D.4 Passo a passo da janela T0

**Antes de ligar a flag**

1. Executar backup completo — anotar timestamp e local.
2. Confirmar que **somente** o emissor designado possui `fiscal_nfe_producao`.
3. Revisar checklist §3D.1, §3D.2 e §3D.3 — **assinar** (operador + fiscal + técnico).
4. Comunicar início da janela à equipe (homologação continua disponível para testes paralelos).

**Ligar produção (somente após checklist assinado)**

5. Definir `NFE_PRODUCAO_HABILITADA=true` **apenas** no ambiente da janela (nunca em dev compartilhado sem isolamento).
6. Reiniciar backend: `docker compose restart backend` (ou equivalente no deploy).
7. Validar na UI de uma NF qualquer: bloco produção exibe «Produção SEFAZ» (não emitir ainda se checklist NF específica incompleto).

**Emissão da 1ª NF**

8. Abrir a NF-e Saída escolhida (pedido/faturamento já revisados).
9. Aba **Validação** → revisar checklist produção (pendências, alertas, emitente, cliente, valor, numeração).
10. Confirmar série/número previstos, itens, CFOP, impostos e total com contador.
11. Clicar **«Emitir em produção SEFAZ»** (botão vermelho — distinto de homologação).
12. No modal: ler avisos legais → marcar checkbox → digitar `PRODUCAO SEFAZ` → confirmar.
13. Aguardar retorno (não clicar novamente — UI bloqueia clique duplo).

**Registro obrigatório pós-transmissão**

| Campo | Valor registrado |
|-------|------------------|
| Data/hora | |
| Usuário emissor | |
| NF-e Saída (id / pedido) | |
| cStat | |
| xMotivo | |
| Protocolo | |
| Chave de acesso | |
| Série / número | |

14. Baixar **XML autorizado** (`download xml autorizado` na UI ou endpoint).
15. Gerar/abrir **DANFE** a partir do XML autorizado (BFR) — validar layout com contador.
16. Registrar conclusão da janela e decisão: manter flag ON para próximas NFs ou desligar após smoke.

---

#### 3D.5 Condutas por resultado

| Resultado | Conduta | Não fazer |
|-----------|---------|-----------|
| **Autorizada** (cStat 100) | Salvar XML; validar DANFE; registrar protocolo/chave; contador valida apuração | Assumir estoque/financeiro automático no ERP (fora do escopo) |
| **Rejeitada** (cStat ≠ 100) | Registrar xMotivo; **parar**; analisar com contador; corrigir causa; nova tentativa só após validação | Reenviar em loop sem entender o motivo |
| **Erro técnico** (sem protocolo claro) | Verificar na SEFAZ/portal se NF foi autorizada **antes** de reenviar | Duplicar emissão sem checagem |
| **Timeout / lote 104 sem protocolo** | Consultar status do lote/recibo na SEFAZ; aguardar orientação técnica | Nova transmissão imediata |
| **Numeração incorreta** | **Parar** operação; acionar contador; avaliar inutilização na SEFAZ | Ajustar número manualmente no ERP sem alinhar SEFAZ |
| **Nota autorizada por engano** | Acionar contador **imediato**; cancelamento (24h) ou CC-e futura; registrar incidente | Restaurar backup apagando a autorização SEFAZ |
| **Flag ligada indevidamente** | `NFE_PRODUCAO_HABILITADA=false` + restart backend; verificar se houve transmissão | Ignorar — operadores podem emitir documento real |

---

#### 3D.6 Rollback operacional seguro

| Ação | Quando | Cuidado |
|------|--------|---------|
| Desligar `NFE_PRODUCAO_HABILITADA=false` | Fim da janela, flag indevida, ou após smoke único | Reiniciar backend após alterar |
| Remover `fiscal_nfe_producao` de usuários | Após janela | Reduz risco de emissão acidental |
| Retornar banner/ambiente visual para homologação | Ambientes com `NEXUS_APP_AMBIENTE` | Evitar confusão operacional |
| **Restaurar backup do banco** | Erro grave **sem** NF autorizada na SEFAZ | **Nunca** se NF já autorizada na SEFAZ sem decisão fiscal — divergência ERP × SEFAZ |
| Registrar incidente | Qualquer rejeição, timeout, autorização por engano | Incluir cStat, chave, protocolo, prints |

> **Aviso fiscal crítico:** nota **autorizada na SEFAZ** não se «apaga» com rollback de banco ou revert de commit. O procedimento é **fiscal** (cancelamento, inutilização, carta de correção), não técnico.

---

#### 3D.7 Fora do escopo desta Fase 3D

Não acoplar à 1ª emissão real:

- Entrada Própria · Remessa · Triangular · Devolução fornecedor
- Cancelamento / CC-e / Inutilização **via Nexus**
- Estoque automático · Financeiro automático · Apuração automática nova

---

#### 3D.8 Cronograma sugerido (referência)

1. **T-7 dias:** backup; certificado; numeração prod vs SEFAZ; `verificar_prontidao_producao` sem críticos
2. **T-1 dia:** smoke homolog com dados reais da NF escolhida; revisar runbook com contador
3. **T0:** backup → checklist assinado → flag ON → 1 NF produção real
4. **T0+15 min:** cStat 100, XML, DANFE, eventos `NFeSaidaEvento`
5. **T+24h:** revisão contábil; decisão flag ON contínuo ou OFF até próxima janela

**Plano de rollback resumido:**

| Cenário | Ação |
|---------|------|
| Flag ligada antes da hora | `NFE_PRODUCAO_HABILITADA=false` + restart backend |
| NF rejeitada | Corrigir pendências; não incrementar numeração manualmente sem SEFAZ |
| NF autorizada por engano | Contador: cancelamento (24h) ou inutilização |
| Numeração inconsistente | Parar; comparar ERP vs portal SEFAZ |
| Certificado comprometido | Substituir A1; flag off até validação |
| Banco corrompido **sem** autorização SEFAZ | Restore backup pré-janela com decisão formal |

**Rollback não cobre:** desfazer NF já autorizada na SEFAZ.

---

#### 3D.9 Registro operacional — janela T0 (2026-06-02)

| Campo | Valor |
|-------|-------|
| **Parecer** | **ABORTADA** — pré-requisito bloqueante pendente |
| **Data** | 2026-06-02 |
| **Flag ligada?** | **Não** (`NFE_PRODUCAO_HABILITADA=false`) |
| **NF-e transmitida?** | **Não** |
| **cStat / protocolo / chave** | — (sem transmissão) |

**Motivo do aborto:**

- `DEBUG=True` no ambiente verificado
- 1 usuário ativo sem perfil/grupo (`verificar_prontidao_producao`)
- Backup formal não confirmado
- Certificado A1 e numeração produção não validados com contador/SEFAZ
- Contador/fiscal e autorização formal da direção não confirmados
- Checklist §11 não assinado
- Validação técnica final incompleta (4015/conferência UI e build pendentes na janela)

**Validação técnica parcial registrada:**

| Verificação | Resultado |
|-------------|-----------|
| `manage.py check` | OK |
| `verificar_prontidao_producao` | Crítico: usuário sem perfil; pendente DEBUG, backup |
| `test_nfe_saida_402_emissao_homologacao` | OK (26 testes) |

**Próxima janela:** corrigir **todas** as pendências abaixo → reassinar checklist §11 → reexecutar §3D.2 e §3D.4.

**Emissão produção permanece BLOQUEADA** até saneamento completo. Nova tentativa **somente** após declaração formal **«T0 liberada»** (direção + fiscal + técnico), com backup e checklist §11 assinados.

**Pendências bloqueantes para reagendar T0:**

| # | Pendência | Responsável |
|---|-----------|-------------|
| 1 | ~~Corrigir usuário ativo sem perfil/grupo~~ | **Resolvido** — §13.1 (`nfe402` desativado) |
| 2 | Confirmar `DEBUG=False` no ambiente operacional | Técnico |
| 3 | Registrar backup formal (data/hora/local) | Técnico |
| 4 | Validar certificado A1 com contador/fiscal | Fiscal |
| 5 | Validar série e próximo número produção com contador/SEFAZ | Fiscal |
| 6 | Confirmar contador/fiscal presente na janela | Operacional |
| 7 | Confirmar autorização formal da direção | Direção |
| 8 | Preencher e assinar checklist §11 | Operador + fiscal + técnico |
| 9 | Reexecutar testes finais §3D.2 **em sequência** (sem paralelismo) | Técnico |

**Próximo estado esperado:** `T0 liberada` — apenas quando itens 1–9 estiverem **todos** concluídos. Até lá: `NFE_PRODUCAO_HABILITADA=false`; **não iniciar nova tentativa de T0**.

---

## 7. Checklist operacional pré go-live

Use esta lista **manualmente** com fiscal/contador antes de `NFE_PRODUCAO_HABILITADA=true`.

### 7.1 Certificado e empresa emitente

- [ ] Certificado A1 instalado no cadastro da empresa emitente (arquivo + senha)
- [ ] Validade do certificado ≥ 30 dias (`GET /api/empresas/{id}/validar-certificado-nfe/`)
- [ ] CNPJ do certificado = CNPJ da empresa emitente
- [ ] Inscrição Estadual ativa e consistente com SEFAZ
- [ ] Regime tributário (CRT) correto no cadastro
- [ ] Endereço completo: logradouro, número, bairro, município, UF, CEP, código IBGE
- [ ] Logo emitente (opcional) configurada para DANFE BFR

### 7.2 Numeração e SEFAZ

- [ ] Configuração `NFeNumeracaoConfiguracao` ambiente **produção**, série fiscal real (ex.: `1`)
- [ ] `proximo_numero` = último número SEFAZ + 1 (confirmado no portal ou última NF impressa)
- [ ] Série autorizada na SEFAZ para o CNPJ emitente
- [ ] Nenhuma lacuna/inutilização pendente que conflite com próximo número
- [ ] Homologação usa série **diferente** (ex.: `0`) — sem risco de colisão

### 7.3 XML, DANFE e validação fiscal

- [ ] Checklist `40135` OK em homolog com **mesmos dados** que serão usados em prod
- [ ] DANFE BFR renderiza corretamente do XML autorizado homolog
- [ ] Impostos (ICMS, PIS, COFINS, IPI) conferidos item a item pelo fiscal
- [ ] CFOP e natureza da operação validados
- [ ] Duplicatas/cobrança no XML alinhadas ao acordado comercial (sem gerar CR automático)
- [ ] Posição sobre Reforma Tributária (RTC) definida — default atual: **sem tags RTC em produção**

### 7.4 Contador / fiscal

- [ ] Responsável fiscal nomeado e disponível na janela T0
- [ ] Procedimento de **cancelamento** (24h) documentado
- [ ] Procedimento de **inutilização** de numeração documentado
- [ ] Procedimento de **carta de correção** (fase futura) comunicado
- [ ] Validação de que NF homolog **não entra** na apuração; NF prod **entra**

### 7.5 Infraestrutura e prontidão ERP

- [ ] `python manage.py check` sem issues
- [ ] `python manage.py verificar_prontidao_producao` sem itens críticos
- [ ] `DEBUG=False`; `SECRET_KEY` forte; `ALLOWED_HOSTS` / CORS / CSRF corretos
- [ ] Backup completo validado (restore testado em ambiente separado, se possível)
- [ ] Usuários emissores com perfil/grupo correto
- [ ] Equipe treinada: diferença visual homolog vs prod

### 7.6 Pós 1ª NF produção

- [ ] cStat `100` e protocolo registrados em `NFeSaida`
- [ ] `xml_autorizado` baixável e arquivado
- [ ] DANFE BFR impresso/arquivado
- [ ] Conferência contábil da NF no ERP externo/contabilidade
- [ ] Eventos `NFeSaidaEvento` revisados (trilha de auditoria)

---

## 8. O que fica fora deste go-live

Os itens abaixo **não fazem parte** das fases 3B/3C/3D de NF-e Saída produção e não devem ser acoplados ao primeiro go-live:

| Item | Motivo |
|------|--------|
| **Entrada Própria** (emissão tpNF=0) | Escopo 4.0.15.x separado; homolog entrada ainda incompleta (sem transmissão) |
| **Remessa** | Modelo operacional não iniciado |
| **Operação triangular** | Fora do módulo NF-e saída atual |
| **Estoque automático** pós-autorização prod | Homolog explicitamente sem efeitos; prod requer decisão e fase própria |
| **Financeiro automático** (CR a partir de NF) | Financeiro 4.0.14 é manual; geração a partir de NF é fase futura |
| **Apuração automática nova** | Apuração existente exclui homolog; integração prod com apuração = fase posterior |
| **Cancelamento / CC-e / inutilização via ERP** | Previsto pós go-live emissão |
| **Contingência SEFAZ** | Não implementado |
| **RTC tags em XML produção** | Bloqueado em `reforma_tributaria/config.py` até validação oficial |

---

## 9. Referências no repositório

| Tema | Caminho |
|------|---------|
| Emissão homolog | `backend/apps/fiscal/nfe_emissao/servico.py` |
| Transmissão | `backend/apps/fiscal/nfe_emissao/transmissao.py` |
| Numeração | `backend/apps/fiscal/nfe_emissao/numeracao.py`, `numeracao_defaults.py` |
| Validação | `backend/apps/fiscal/nfe_emissao/validacao.py` |
| XML produção (stub) | `backend/apps/fiscal/nfe_xml_transmissao.py` |
| API NF-e Saída | `backend/apps/fiscal/views.py` (`emitir-homologacao`) |
| Conferência / permissões | `backend/apps/fiscal/nfe_saida_conferencia.py` |
| Checklist homolog | `backend/apps/fiscal/nfe_saida_checklist_homologacao.py` |
| DANFE BFR | `backend/apps/fiscal/danfe_render.py` |
| Certificado / status SEFAZ | `backend/apps/fiscal/nfe_integracao/adapters/` |
| UI conferência | `frontend/src/components/fiscal/NFeSaidaConferenciaModal.tsx` |
| UI listagem | `frontend/src/pages/NFeSaida.tsx` |
| Prontidão ERP geral | `backend/apps/core/prontidao_producao.py` |
| Reforma Tributária | `docs/reforma-tributaria-nfe-nexus.md` |
| Roadmap | `docs/roadmap-nexus-erp.md` §7 NF-e saída |
| Organização DF-e / apuração | `docs/base-dfe-importada.md` |

---

## 10. Confirmações de entrega

### Fase 3D-prep (runbook)

- [x] Apenas documentação/runbook — nenhuma alteração funcional
- [x] Fase 3B e 3C refletidas como concluídas
- [x] Produção SEFAZ **não** foi ligada (`NFE_PRODUCAO_HABILITADA=false`)
- [x] Nenhuma NF-e produção real foi transmitida
- [x] Secrets / `.env` real **não** alterados
- [x] Backend de emissão e UI Fase 3C **não** alterados
- [x] Estoque, financeiro e apuração **não** alterados

### Registro operacional — T0 abortada (2026-06-02)

- [x] Status **ABORTADA** registrado em §3D.9
- [x] Produção SEFAZ permanece **desligada**
- [x] Nenhuma emissão produção realizada; nenhum impacto fiscal
- [x] Pendências bloqueantes listadas (§3D.9)
- [x] Próximo estado documentado: **«T0 liberada»** somente após saneamento completo
- [x] Não ligou produção · não transmitiu NF-e real · não alterou secrets/env · não alterou código fiscal

---

## 11. Checklist final do operador (imprimir antes da janela T0)

Preencher manualmente. **Não ligar a flag** até todos os itens obrigatórios estarem marcados.

### Identificação da janela

| Campo | Preencher |
|-------|-----------|
| Data/hora prevista T0 | |
| NF-e Saída (id) / Pedido | |
| Empresa emitente | |
| Série produção / próximo número | |
| Cliente | |
| Valor total (R$) | |
| Operador emissor | |
| Contador/fiscal | |
| Responsável técnico | |
| Autorização formal da direção (sim/não + referência) | |

### Registro de backup (obrigatório antes de T0)

| Campo | Preencher |
|-------|-----------|
| Data/hora do backup | |
| Responsável | |
| Ambiente (dev/staging/prod) | |
| Tipo (snapshot/pg_dump/outro) | |
| Identificação do artefato (caminho/retenção — **não versionar**) | |
| Validação mínima (restore testado / checksum / outro) | |

> **Não** copiar dump ou backup para o repositório Git.

#### Registro operacional efetuado (jun/2026)

| Campo | Valor registrado |
|-------|------------------|
| **Data/hora do backup** | **Confirmado pelo operador** — completar data/hora exata na tabela acima se diferente |
| **Responsável** | **Bruno Lira** |
| **Ambiente** | Servidor operacional (Nexus App produção operacional) |
| **Tipo** | pg_dump / snapshot (conforme procedimento do operador) |
| **Identificação do artefato** | Armazenamento seguro off-repo — **não versionar** |
| **Validação mínima** | Confirmada pelo operador |
| **NF-e produção no backup** | Nenhuma transmitida; flag `NFE_PRODUCAO_HABILITADA=false` |

### Pré-requisitos (obrigatório)

- [x] `NFE_PRODUCAO_HABILITADA=false` confirmado **agora**
- [x] Backup completo realizado e registrado (responsável Bruno Lira — ver registro operacional acima)
- [ ] Certificado A1 válido (CNPJ compatível)
- [ ] Série/número produção conferidos com contador/SEFAZ
- [ ] Cliente e produtos revisados (NCM, CFOP, impostos)
- [ ] NF «Pronta para emissão»; checklist produção UI sem bloqueios
- [ ] DANFE BFR validado em homologação com mesmos dados
- [x] Apenas emissor designado com `fiscal_nfe_producao` — **`fiscal01`** (único usuário no grupo)
- [ ] Contador/fiscal e técnico confirmados presentes
- [ ] Operação = venda normal (não remessa/triangular/devolução/entrada própria)

### Técnico (obrigatório)

- [ ] `manage.py check` OK
- [ ] `test_nfe_saida_producao_4015` OK
- [ ] `test_nfe_saida_402_emissao_homologacao` OK
- [ ] `npm run build` OK
- [ ] `verificar_prontidao_producao` — **sem críticos** (aceite formal se exceção): _______________
- [ ] `DEBUG=False` confirmado no ambiente operacional da janela
- [ ] Testes finais §13.7 executados **em sequência** (sem paralelismo)

### Assinaturas (checklist assinado → permitido ligar flag)

> **Pendente até assinatura real** — não marcar como concluído antecipadamente.

| Papel | Nome | Assinatura | Data/hora |
|-------|------|------------|-----------|
| Operador | | | |
| Contador/fiscal | | | |
| Responsável técnico | | | |
| Direção (autorização) | | | |

### Pós-emissão (preencher após T0)

| Campo | Valor |
|-------|-------|
| cStat | |
| xMotivo | |
| Protocolo | |
| Chave | |
| Resultado | [ ] Autorizada [ ] Rejeitada [ ] Erro/timeout |
| Flag pós-janela | [ ] ON [ ] OFF |
| Incidente registrado? | [ ] Não [ ] Sim — descrição: |

---

## 12. Próximo passo operacional

**Estado atual (pós T0 abortada):** produção SEFAZ **desligada**; aguardar nova janela após correção das pendências §3D.9.

Antes de reagendar T0:

1. Corrigir usuário sem perfil/grupo.
2. Confirmar `DEBUG=False` no ambiente operacional.
3. Registrar backup formal (data/hora/responsável).
4. Validar certificado A1 e numeração produção com contador/SEFAZ.
5. Preencher e **assinar** checklist §11 (operador + fiscal + técnico).
6. Confirmar autorização formal da direção e presença de contador/fiscal.
7. Reexecutar testes §3D.2 **em sequência** (sem paralelismo).
8. Só então: `NFE_PRODUCAO_HABILITADA=true` + restart → §3D.4.

**Parecer para nova janela:** **APTO COM PENDÊNCIAS** — ver §13 (saneamento pré-T0).

---

## 13. Saneamento pré-T0 (2026-06-02)

**Objetivo:** resolver bloqueios técnicos/operacionais da T0 abortada **sem** ligar produção, **sem** transmitir NF-e real.

**Garantias mantidas:** `NFE_PRODUCAO_HABILITADA=false` · nenhuma NF-e produção · `.env` real não commitado · sem exposição de secrets/certificado.

### 13.1 Usuário ativo sem perfil/grupo — **RESOLVIDO**

| Campo | Valor |
|-------|-------|
| Origem | Resíduo de teste `test_nfe_saida_402_emissao_homologacao` com `--keepdb` |
| id | 6 |
| username | `nfe402` |
| email (mascarado) | `nf***@test.com` |
| status | estava ativo, sem grupo |
| Ação | **Desativado** (`is_active=false`) — não recebeu `fiscal_nfe_producao` |
| Fluxo alternativo | Cadastros > Colaboradores > Acesso ao sistema (para usuários reais) |

**Evidência:** `verificar_prontidao_producao` — críticos: **(nenhum)** após saneamento.

> Reativar `nfe402` só se necessário para dev/testes locais; usuários reais devem ter perfil via Colaboradores.

### 13.2 DEBUG=False — **PENDENTE (operacional)**

| Item | Detalhe |
|------|---------|
| Onde é lido | `backend/nexus_erp/settings.py` ← variável de ambiente `DEBUG` |
| Origem no Docker | `docker-compose.yml` → `env_file: .env` (backend e frontend) |
| Default documentado | `.env.example` → `DEBUG=True` (desenvolvimento) |
| Ambiente atual (dev Docker) | `DEBUG=True` — **esperado para dev** |
| Ação para janela T0 | No **ambiente operacional** da emissão: definir `DEBUG=False` no `.env` **local do servidor** (não commitar) → `docker compose restart backend` |
| Verificação | `python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"` → deve imprimir `False` |

**Nenhum valor de `.env` real foi exposto ou commitado.**

### 13.3 Backup formal — **PENDENTE (bloqueante)**

Registrar na tabela **§11 — Registro de backup** antes de T0. Campos obrigatórios: data/hora, responsável, ambiente, tipo, identificação do artefato, validação mínima.

### 13.4 Certificado A1, empresa e numeração — **PENDENTE (bloqueante fiscal)**

Validação **somente** com contador/fiscal presente. Itens em §3D.1, §3D.3 e §7.1–7.2. **Não** alterar série/número sem confirmação formal. **Não** expor certificado ou senha.

### 13.5 Checklist §11 — **COMPLETO, NÃO ASSINADO**

Checklist imprimível com campos de janela, backup, autorização direção e assinaturas. Permanece **pendente de assinatura real** do operador/fiscal/técnico/direção.

### 13.6 Autorização e presença fiscal — **PENDENTE (bloqueante operacional)**

Contador/fiscal e autorização formal da direção: confirmar presencialmente antes de «T0 liberada».

### 13.7 Testes finais — ver registro abaixo

Executar **em sequência** (sem paralelismo entre suítes):

```bash
docker compose exec backend python manage.py check
docker compose exec backend python manage.py verificar_prontidao_producao
docker compose exec backend python manage.py test \
  apps.fiscal.tests.test_nfe_saida_producao_4015 \
  apps.fiscal.tests.test_nfe_saida_producao_4015_conferencia_ui --keepdb
docker compose exec backend python manage.py test \
  apps.fiscal.tests.test_nfe_saida_402_emissao_homologacao --keepdb
docker compose exec frontend npm run build
```

| Verificação | Resultado saneamento |
|-------------|---------------------|
| `manage.py check` | OK |
| `verificar_prontidao_producao` | OK — sem críticos |
| `test_nfe_saida_producao_4015` + conferência UI | OK (23/23) |
| `test_nfe_saida_402_emissao_homologacao` | OK (26) |
| `npm run build` | OK |

#### 13.7.1 Registro de execução (2026-06-02)

| Verificação | Resultado |
|-------------|-----------|
| `manage.py check` | OK |
| `verificar_prontidao_producao` | OK — sem críticos |
| `npm run build` | OK |
| `test_nfe_saida_402_emissao_homologacao` | OK (26) |
| `test_nfe_saida_producao_4015` + conferência UI | **OK (23/23)** — 2026-06-02, após estabilização de grupos em `nfe_4015_test_support.py` (deadlock `Group.get_or_create` eliminado; execução isolada, ~117 s) |

**Nota técnica (deadlock):** múltiplos `setUp` concorrentes chamavam `Group.objects.get_or_create(name='admin')` em `--keepdb`, gerando contenção na unique key `auth_group_name_key`. Correção: helper idempotente (`filter` → `create` com fallback `IntegrityError`) + `NFe4015GruposMixin.setUpClass` pré-cria grupos uma vez por classe.

### 13.8 Parecer saneamento pré-T0

| Dimensão | Resultado |
|----------|-----------|
| Crítico usuário sem perfil | **Resolvido** |
| DEBUG=False (ambiente operacional T0) | **Pendente** |
| Backup formal | **Pendente** |
| Certificado / numeração (fiscal) | **Pendente** |
| Checklist §11 assinado | **Pendente** |
| Autorização direção + fiscal presente | **Pendente** |
| Testes finais completos | **OK** — 4015 (23/23), 402 (26/26), build OK |

**Parecer final:** **APTO COM PENDÊNCIAS** — apto para reagendar T0 **somente** após itens pendentes + declaração **«T0 liberada»**. Produção SEFAZ **permanece desligada**.

### 13.9 Fechamento pré-T0 técnico (2026-06-02) — **aprovado**

| Evidência | Resultado |
|-----------|-----------|
| `test_nfe_saida_producao_4015` + conferência UI | OK (23/23) |
| `test_nfe_saida_402_emissao_homologacao` | OK (26/26) |
| `manage.py check` | OK |
| `verificar_prontidao_producao` | OK — sem críticos |
| `npm run build` | OK |
| `NFE_PRODUCAO_HABILITADA` | `false` — produção SEFAZ **desligada** |
| NF-e produção transmitida | **Nenhuma** |
| Código fiscal funcional alterado | **Não** |

**Status:** **APTO COM PENDÊNCIAS**. **Não** declarar **«T0 liberada»** até conclusão das pendências operacionais/fiscais abaixo.

**Pendências restantes (operacionais/fiscais):**

1. `DEBUG=False` no ambiente real de T0
2. Backup formal registrado (§11)
3. Certificado A1 validado
4. Série e próximo número de produção validados com contador/SEFAZ
5. Grupo `fiscal_nfe_producao` criado/atribuído **somente** ao responsável autorizado
6. Contador e fiscal presentes na janela
7. Autorização formal da direção
8. Checklist §11 assinado (operador + fiscal + técnico + direção)

**Impacto fiscal neste fechamento:** nenhum. Homologação e guards de produção intactos.

### 13.10 Aguardando fechamento operacional/fiscal

**Estado atual:** técnico fechado; **aguardando** fechamento operacional/fiscal para declarar **«T0 liberada»**.

**Alteração técnica pendente (NF-e Saída produção):** **nenhuma**.

**Gate obrigatório — não ligar `NFE_PRODUCAO_HABILITADA=true` antes de:**

1. `DEBUG=False` no ambiente real
2. Backup formal registrado
3. Certificado A1 validado
4. Série e próximo número de produção validados (contador/SEFAZ)
5. Fiscal e contador presentes na janela
6. Autorização formal da direção
7. Checklist §11 assinado

Até lá: `NFE_PRODUCAO_HABILITADA=false`, sem transmissão NF-e produção, sem impacto fiscal.

---

## 14. Deploy controlado — homologação fiscal (jun/2026)

> **Não é go-live produção SEFAZ.** Registro de atualização operacional com emissão produção **desligada**.

| Campo | Valor |
|-------|--------|
| **Versão ERP** | 4.0.15.x |
| **Branch** | `producao-local` |
| **Commit implantado** | `2ab0009` — *ERP 4.0.15.x: corrigir NF-e saída CST20 cBenef DANFE e SEFAZ status* |
| **Commit anterior** | `74eb586` |
| **Data deploy + validação servidor** | **13/06/2026** |
| **Ambiente validado** | Servidor operacional (smoke manual curto) |
| **Resultado** | **Aprovado em homologação** |
| **`NFE_PRODUCAO_HABILITADA`** | `false` (inalterado) |
| **NF-e produção transmitida** | Nenhuma |
| **Impacto estoque/financeiro/apuração** | Nenhum |

### 14.1 Correções incluídas no pacote

| Correção | Escopo |
|----------|--------|
| CST 20 → grupo **ICMS20** | XML oficial (`nfe_saida_xml_nfelib.py`, `nfe_icms_calculo.py`) |
| Redução BC da regra fiscal | Snapshot + modal «Atualizar fiscal» |
| **cBenef SP** — literal `SEM CBENEF` | `nfe_cbenef_sp.py`, regra fiscal, validação pré-emissão |
| Validação preventiva SP + CST 20 + redução sem cBenef específico | `validacao_nfe_saida.py`, `nfe_cbenef_sp.py` |
| **DANFE** — ocultar `SEM CBENEF` visualmente | `ocultar_sem_cbenef_para_danfe()` em `sanitizar_xml_para_bfr()` |
| Pedido de compra no XML/DANFE | `danfe_xml_adicionais.py` |
| Consulta SEFAZ dev/local | `pynfe_adapter.py`, parser, UX `/nfe-sefaz` |

### 14.2 Validação local (pré-deploy — NF homologação id=17)

| Item | Resultado |
|------|-----------|
| Status | `AUTORIZADA_HOMOLOGACAO` (cStat 100) |
| XML `<cBenef>SEM CBENEF</cBenef>` | Presente |
| XML ICMS20 / CST 20 / pRedBC 51,1100 / vBC 2444,50 / vICMS 440,01 | OK |
| DANFE PDF sem texto `SEM CBENEF` | OK |
| Pedido de compra no item (`55005050` / item `01`) | OK |
| infCpl (pedido + endereço entrega) | OK |
| `manage.py check` | OK |

### 14.3 Procedimento de deploy no servidor (executado)

**Pré-requisitos atendidos:** backup do banco; `.env` real **não** versionado; certificado/senha **fora** do git.

```bash
# No servidor (diretório do projeto) — executado em 13/06/2026
git fetch origin
git checkout producao-local
git pull origin producao-local   # 2ab0009

# Confirmar flag (não alterar para true)
grep -E '^NFE_PRODUCAO_HABILITADA=' .env   # false

docker compose build backend frontend
docker compose up -d backend frontend
docker compose exec -T backend python manage.py migrate --noinput
docker compose exec -T backend python manage.py check
```

### 14.4 Validação pós-deploy no servidor (13/06/2026)

**Tipo:** smoke manual curto — operador.

| Item | Resultado servidor |
|------|-------------------|
| App atualizado | OK (`2ab0009` em `producao-local`) |
| NF-e Saída homologação | Validada |
| Pendência cBenef (rejeição 930) | Resolvida com `SEM CBENEF` na regra fiscal |
| XML `<cBenef>SEM CBENEF</cBenef>` | Mantido no XML autorizado |
| DANFE sem `SEM CBENEF` visual | OK |
| Pedido de compra no XML/DANFE | OK |
| NF-e homologação | Autorizada/validada no servidor |
| Painel emissão produção | Desabilitado (flag off) |
| `NFE_PRODUCAO_HABILITADA` | `false` |
| NF-e produção transmitida | Nenhuma |

**Smoke executado:**

1. Login no app — OK.
2. `/nfe-sefaz` → consulta status produção (somente serviço) — OK.
3. NF-e Saída → painel produção **desabilitado** — OK.
4. NF homologação autorizada → regerar DANFE → sem `SEM CBENEF` visual; pedido de compra e infCpl intactos — OK.

### 14.5 Confirmações deste deploy

- [x] Commit `2ab0009` implantado no servidor operacional
- [x] Smoke manual curto aprovado (13/06/2026)
- [x] Validação em **homologação** — não é go-live fiscal
- [x] Produção SEFAZ permaneceu desligada (`NFE_PRODUCAO_HABILITADA=false`)
- [x] Nenhuma NF-e produção transmitida
- [x] `SEM CBENEF` mantido no XML fiscal; oculto apenas no DANFE
- [x] Nenhum secret / certificado / `.env` real exposto em commit ou documentação
- [x] Nenhuma alteração de numeração, estoque, financeiro ou apuração

### 14.6 Pendência futura — gate T0 produção SEFAZ

A emissão **produção** SEFAZ real continua **bloqueada**. Ativação consciente de `NFE_PRODUCAO_HABILITADA=true` depende de:

1. Backup formal registrado (§11)
2. `DEBUG=False` no ambiente operacional
3. Certificado A1 validado com contador/fiscal
4. Série e próximo número de produção validados (contador/SEFAZ)
5. Permissão `fiscal_nfe_producao` atribuída somente ao responsável autorizado
6. Contador/fiscal presentes na janela
7. Autorização formal da direção
8. Checklist §11 assinado

Até declarar «T0 liberada»: **sem** ligar flag, **sem** transmissão NF-e produção, **sem** impacto fiscal em produção.

---

## 15. Gate T0 Produção SEFAZ — Auditoria de prontidão

> **Não é go-live fiscal.** Registro de auditoria read-only para avaliar prontidão da 1ª NF-e produção SEFAZ.

| Campo | Valor |
|-------|--------|
| **Versão ERP** | 4.0.15.x |
| **Data da auditoria** | 13/06/2026 |
| **Escopo** | `manage.py check`, `verificar_prontidao_producao`, shell Django read-only, consulta SEFAZ produção (somente status), certificado, numeração, permissões, NF-e candidata |
| **Ambiente auditado** | Container Docker local (banco do projeto) — complementa homologação validada no servidor (`2ab0009`, §14) |
| **Resultado final** | **APTO COM PENDÊNCIAS** |
| **Decisão** | **NÃO AUTORIZADO** ligar `NFE_PRODUCAO_HABILITADA=true` |
| **`NFE_PRODUCAO_HABILITADA`** | `false` (inalterado) |
| **NF-e produção transmitida** | Nenhuma |
| **Número produção reservado** | Nenhum |
| **Alteração `.env`/certificado/numeração/regra fiscal** | Nenhuma |

### 15.1 Escopo executado / não executado

**Executado (somente leitura):**

- `docker compose exec -T backend python manage.py check`
- `docker compose exec -T backend python manage.py verificar_prontidao_producao`
- Auditoria T0 via `manage.py shell` (ambiente, certificado, SEFAZ, numeração, permissões, NF candidata)
- Consulta status serviço SEFAZ **produção** SP (sem emissão)

**Não executado:**

- Ligar `NFE_PRODUCAO_HABILITADA=true`
- Transmitir ou emitir NF-e produção
- Alterar `.env`, certificado, numeração, regra fiscal ou código
- Rodar suíte longa, deploy ou SSH
- Expor senha, caminho de certificado ou secrets

### 15.2 Pontos positivos

| Item | Resultado |
|------|-----------|
| Certificado A1 | Configurado; **válido até 2027-01-21** |
| CNPJ certificado × emitente | Compatível (empresa id=1 — NEXUS) |
| SEFAZ produção SP | **cStat 107** — Serviço em Operação |
| `manage.py check` | 0 issues |
| `verificar_prontidao_producao` | **Sem críticos** |
| Homologação servidor | Commit `2ab0009` validada anteriormente (§14) |
| Flag produção | Bloqueio correto — `NFE_PRODUCAO_HABILITADA=false` |
| Grupo `fiscal` genérico | Não concede emissão produção (comportamento esperado) |

### 15.3 Bloqueios atuais (impedem T0 agora)

| # | Bloqueio |
|---|----------|
| 1 | `NFE_PRODUCAO_HABILITADA=false` — bloqueio intencional até go-live formal |
| 2 | `DEBUG=true` no ambiente auditado — servidor operacional precisa ser confirmado com `DEBUG=false` |
| 3 | `NEXUS_APP_AMBIENTE` não definido no container auditado |
| 4 | `NFE_AMBIENTE` não definido no container auditado |
| 5 | Backup formal não registrado (§11) |
| 6 | Checklist §11 não assinado |
| 7 | Grupo `fiscal_nfe_producao` **inexistente** no banco |
| 8 | Responsável dedicado de emissão produção ainda não atribuído |
| 9 | Numeração produção (série **1**, próximo número **1**) **não validada** com contador/fiscal |
| 10 | **Nenhuma NF-e real pronta** para T0 |
| 11 | NF **17** — homologação autorizada; **não reutilizar** para produção |
| 12 | NF **id=15** — rascunho/fixture; conferência incompleta; endereço fiscal inconsistente |

### 15.4 NF-e candidata T0 (análise read-only)

**NF 17 (referência homologação):**

- Status: `AUTORIZADA_HOMOLOGACAO`
- Uso T0: **proibido** — documento de homologação, não 1ª produção real

**NF id=15 (melhor candidata disponível na auditoria):**

| Campo | Valor |
|-------|--------|
| Status | `RASCUNHO` |
| Conferência | `EM_CONFERENCIA` (não «Pronta para emissão») |
| Cliente | Cliente 402 (fixture) |
| Bloqueio fiscal | Cidade «Rio» diverge do CEP «Rio de Janeiro» |
| `montar_validacao_emissao_producao` | **Não pronta** |

Pendências automáticas da pré-validação: `producao_desabilitada`, `conferencia_nao_pronta`, `validacao_fiscal` (endereço).

### 15.5 Numeração produção (somente leitura — empresa id=1)

| Campo | Valor |
|-------|--------|
| Modelo | 55 |
| Série | 1 |
| Próximo número | 1 |
| Último autorizado | — |
| Ativa | Sim |

Nenhum número foi reservado nem alterado nesta auditoria. Validação contador/SEFAZ **pendente**.

### 15.6 Permissões (somente leitura)

| Item | Resultado |
|------|-----------|
| Grupo `fiscal_nfe_producao` | Não existe |
| Usuários com permissão produção hoje | `admin` (superuser), `comercial04` (grupo `admin`) |
| Perfis autorizados pelo sistema | `admin`, `administrador`, `fiscal_nfe_producao` |

**Pendência:** criar `fiscal_nfe_producao` e atribuir **somente** ao responsável autorizado — não usar `admin` operacional na janela T0.

### 15.7 Pendências antes do T0

1. Confirmar `DEBUG=false` no servidor operacional real
2. Revisar `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `CORS` do servidor
3. Registrar backup formal com data e responsável (§11)
4. Validar série e próximo número produção com contador e SEFAZ
5. Criar grupo/permissão `fiscal_nfe_producao`
6. Atribuir permissão somente ao responsável autorizado
7. Preparar **NF-e real nova** (não reutilizar NF 17)
8. Conferir cliente, endereço, CNPJ/IE, município/UF
9. Conferir produtos, NCM, CFOP, CST, cBenef, PIS/COFINS, valores
10. Deixar NF-e candidata como «Pronta para emissão»
11. Executar `GET .../validar-emissao-producao/` sem pendências fiscais
12. Garantir contador/fiscal presente na janela
13. Obter autorização formal da direção
14. Assinar checklist §11
15. **Só então** considerar ligar `NFE_PRODUCAO_HABILITADA=true`

### 15.8 Sequência futura sugerida (T0)

1. Fechar pendências do §11 e §14.6
2. Confirmar servidor real com `DEBUG=false`
3. Validar numeração produção com contador
4. Criar permissão dedicada `fiscal_nfe_producao`
5. Preparar NF-e real candidata T0
6. Validar emissão produção **sem transmitir** (`validar-emissao-producao`)
7. Fazer backup formal
8. Ter contador/fiscal e direção acompanhando a janela
9. Ligar flag **somente** na janela T0 controlada
10. Emitir **uma única** NF-e produção — 1ª emissão real

### 15.9 Confirmações desta auditoria

- [x] Status documentado: **APTO COM PENDÊNCIAS**
- [x] Produção fiscal **NÃO autorizada** nesta tarefa
- [x] `NFE_PRODUCAO_HABILITADA=false` — inalterado
- [x] Nenhuma NF-e produção transmitida
- [x] Nenhum número produção reservado
- [x] Nenhuma alteração em `.env`, certificado, numeração ou regra fiscal
- [x] Nenhum secret/senha/caminho de certificado exposto
- [x] Bloqueios e pendências registrados
- [x] Sequência T0 futura documentada

---

## 16. Operação T0 — Fechamento pendências pré-produção (sem emitir)

> **Não é emissão produção.** Read-only + registro operacional. Flag **permaneceu desligada**.

| Campo | Valor |
|-------|--------|
| **Data** | 13/06/2026 |
| **Commits de referência** | `2ab0009` (fiscal), `f3a6e60` (docs Gate T0) |
| **Resultado desta operação** | **BLOQUEADO** para T0 — **APTO COM PENDÊNCIAS** na base técnica |
| **`NFE_PRODUCAO_HABILITADA`** | `false` (inalterado) |
| **NF-e produção transmitida** | Nenhuma |
| **Número produção reservado** | Nenhum |

### 16.1 Escopo executado / não executado

**Executado (somente leitura):**

- `manage.py check` — 0 issues
- `verificar_prontidao_producao` — sem críticos
- Releitura ambiente, certificado, SEFAZ produção, numeração, permissões, NF candidata (container local)
- Atualização status checklist §11 abaixo

**Não executado (aguarda operador ou bloqueado):**

- SSH / confirmação `.env` do **servidor operacional real**
- Registro de backup formal (operador não informou evidência)
- Criação grupo `fiscal_nfe_producao` (responsável autorizado não informado)
- Preparação NF-e real candidata T0 (novo pedido/faturamento)
- `emitir-producao` / ligar flag / reservar número / alterar `.env`

### 16.2 Status checklist §11 (evidência em 13/06/2026 — ver atualização §17)

| Item §11 | Status | Evidência / observação |
|----------|--------|------------------------|
| `NFE_PRODUCAO_HABILITADA=false` | **OK** | Confirmado |
| Backup formal registrado | **OK** | Responsável Bruno Lira — §11 + §17.1 |
| Certificado A1 válido | **OK** | Válido até 2027-01-21; CNPJ compatível |
| SEFAZ produção SP cStat 107 | **OK** | Consulta somente status (13/06/2026) |
| `DEBUG=False` servidor operacional | **OK** | Confirmado pelo operador (jun/2026) |
| Numeração produção (série 1 / nº 1) | **PENDENTE** | Confirmação contador/fiscal ausente |
| Grupo `fiscal_nfe_producao` | **OK** | Criado; único usuário: `fiscal01` — §17.3 |
| NF-e candidata T0 pronta | **PENDENTE** | NF 17 = homolog; NF 15 = fixture |
| `verificar_prontidao_producao` sem críticos | **OK** | Executado |
| Contador/fiscal presente | **PENDENTE** | Janela T0 |
| Autorização formal direção | **PENDENTE** | Janela T0 |
| Checklist §11 assinado | **PENDENTE** | Assinaturas operador/fiscal/técnico/direção |

### 16.3 Parte 1 — Ambiente (container auditado)

| Variável | Valor auditado | Bloqueio T0? |
|----------|----------------|--------------|
| `DEBUG` | `true` | **Sim** — se servidor operacional igual, bloqueia T0 |
| `NEXUS_APP_AMBIENTE` | não definido | Pendente no servidor |
| `NFE_AMBIENTE` | não definido | Documental |
| `NFE_PRODUCAO_HABILITADA` | `false` | OK (intencional) |
| `ALLOWED_HOSTS` | 4 entradas | Revisar no servidor |
| `CSRF_TRUSTED_ORIGINS` | 0 | Revisar no servidor |
| `CORS_ALLOWED_ORIGINS` | 4 | Revisar no servidor |

**Ação operador no servidor (sem expor secrets):**

```bash
grep -E '^(DEBUG|NEXUS_APP_AMBIENTE|NFE_AMBIENTE|NFE_PRODUCAO_HABILITADA)=' .env
docker compose exec -T backend python manage.py shell -c "from django.conf import settings; print('DEBUG', settings.DEBUG)"
```

### 16.4 Parte 2 — Backup formal

| Status | **Registrado** (jun/2026) |
|--------|---------------------------|
| Responsável | **Bruno Lira** |
| Detalhe | §11 «Registro operacional efetuado» + §17.1 |
| NF-e produção no backup | Nenhuma; flag off |

### 16.5 Parte 3 — Numeração produção (somente leitura)

| Campo | Valor (empresa id=1) |
|-------|----------------------|
| Modelo | 55 |
| Ambiente | produção |
| Série | 1 |
| Próximo número | 1 |
| Último autorizado | — |
| Ativa | Sim |

Nenhum número reservado nem alterado. **Confirmação contador/fiscal pendente.**

### 16.6 Parte 4 — Permissão `fiscal_nfe_producao`

| Item | Status |
|------|--------|
| Grupo existe | **Sim** — criado jun/2026 |
| Único usuário | **`fiscal01`** |
| Detalhe completo | §17.2 e §17.3 |

### 16.7 Parte 5 — NF-e candidata T0

| NF | Uso T0 |
|----|--------|
| **17** | Homologação autorizada — **proibida** para produção |
| **15** | Fixture/rascunho — `EM_CONFERENCIA`, endereço inconsistente — **não pronta** |

**Próximo passo:** criar NF-e **nova** a partir de pedido/faturamento real → conferência completa → «Pronta para emissão» → `GET .../validar-emissao-producao/` sem pendências (sem transmitir).

### 16.8 Pendências fechadas nesta operação

- [x] Reconfirmado `NFE_PRODUCAO_HABILITADA=false`
- [x] Reconfirmado certificado válido e SEFAZ 107
- [x] Reconfirmado `manage.py check` e `verificar_prontidao_producao`
- [x] Numeração produção documentada (somente leitura)
- [x] Status checklist §11 atualizado com evidência real

### 16.9 Pendências restantes (bloqueiam T0)

1. Completar data/hora exata do backup na tabela §11 (se necessário)
2. Contador/fiscal validar série 1 / próximo número 1
3. Preparar NF-e real candidata T0
4. Assinar checklist §11 + autorização direção
5. Janela T0 com contador/fiscal presente

> Permissão `fiscal_nfe_producao` e usuário `fiscal01` concluídos — ver §17.

### 16.10 Confirmações desta operação

- [x] Não ligou `NFE_PRODUCAO_HABILITADA=true`
- [x] Nenhuma NF-e produção transmitida
- [x] Nenhum número reservado
- [x] Não alterou `.env`, certificado, numeração, regra fiscal, código fiscal
- [x] Não expôs secrets/certificado/senha
- [x] Não rodou suítes longas (4015/402)

---

## 17. T0 — Acesso `fiscal01` e permissão `fiscal_nfe_producao` (jun/2026)

> **T0 permanece BLOQUEADO** para emissão produção. Permissão de perfil criada; flag e janela formal ainda pendentes.

| Campo | Valor |
|-------|--------|
| **Data registro** | jun/2026 |
| **Resultado** | **BLOQUEADO** para T0 (emissão produção) |
| **`NFE_PRODUCAO_HABILITADA`** | `false` (inalterado) |
| **NF-e produção transmitida** | Nenhuma |
| **Número produção reservado** | Nenhum |

### 17.1 Backup formal (§11)

| Campo | Valor |
|-------|--------|
| **Responsável** | **Bruno Lira** |
| **Data/hora** | Confirmada pelo operador — completar data exata na tabela §11 se necessário |
| **Status** | **Registrado** (sem artefato no Git) |

### 17.2 Usuário operacional T0 — `fiscal01`

| Campo | Valor |
|-------|--------|
| Username | `fiscal01` |
| E-mail | `fiscal01@nexusvalvulas.com.br` |
| Colaborador | **Bruno Prado de Lira** |
| `is_staff` | `false` |
| `is_superuser` | `false` |
| Grupos | `fiscal`, `fiscal_nfe_producao` |
| Conta `admin` | Staff/superuser técnico — **não** vinculado ao colaborador Bruno |

### 17.3 Grupo `fiscal_nfe_producao`

| Item | Valor |
|------|--------|
| Grupo | **Criado** |
| Único usuário vinculado | **`fiscal01`** |
| `usuario_pode_emitir_nfe_producao(fiscal01)` | `true` (perfil) |
| Emissão produção efetiva | **Bloqueada** — `NFE_PRODUCAO_HABILITADA=false` |

### 17.4 Status checklist §11 atualizado

| Item | Status |
|------|--------|
| `NFE_PRODUCAO_HABILITADA=false` | **OK** |
| Backup formal | **OK** — responsável Bruno Lira (§11 + §17.1) |
| `DEBUG=false` servidor operacional | **OK** — confirmado pelo operador |
| Grupo `fiscal_nfe_producao` + emissor `fiscal01` | **OK** |
| Certificado A1 / SEFAZ 107 | **OK** (auditorias anteriores) |
| Numeração produção (contador) | **PENDENTE** |
| NF-e candidata T0 pronta | **PENDENTE** |
| Checklist §11 assinado | **PENDENTE** |
| Autorização formal direção | **PENDENTE** |
| Contador/fiscal na janela | **PENDENTE** |

### 17.5 Bloqueio T0 mantido — próximos passos

1. Completar **data/hora exata** do backup na tabela §11 (se ainda em branco).
2. Contador/fiscal validar **série 1 / próximo número 1**.
3. Preparar **NF-e real candidata** → «Pronta para emissão» → `validar-emissao-producao` sem pendências.
4. Assinar checklist §11 + autorização da direção.
5. Janela T0 com contador/fiscal presente → **somente então** `NFE_PRODUCAO_HABILITADA=true`.

### 17.6 Confirmações desta etapa

- [x] Backup formal registrado (responsável Bruno Lira)
- [x] `fiscal_nfe_producao` criado; somente `fiscal01` vinculado
- [x] `admin` não alterado como operador T0
- [x] `NFE_PRODUCAO_HABILITADA=false`
- [x] Nenhuma NF-e produção transmitida
- [x] Nenhum número reservado
- [x] T0 **BLOQUEADO** até NF candidata + checklist + autorização
