# Deploy ERP 4.0.15.2 / 4.0.15.2.1 — Produção fiscal completa

Checklist operacional para subida no **servidor de produção**, com **todos os fluxos fiscais em produção SEFAZ**.

| Campo | Valor |
|-------|-------|
| **Versão** | ERP 4.0.15.2 → 4.0.15.2.1 (correção de premissa operacional) |
| **Branch** | `feat/comercial-status-itens-proposta` |
| **Commit principal** | `ee66354` — feat(fiscal): manifestação do destinatário e melhorias na Central DF-e |
| **Escopo** | NF-e Saída produção · Manifestação do Destinatário · Central DF-e · NF-e Entrada Importada · CT-e Importado |

> **Premissa operacional (4.0.15.2.1):** no servidor, **tudo fiscal opera em produção**. NF-e Saída produção **já está ativa** e deve **continuar funcionando** após o deploy. Este documento **não** orienta desligar `NFE_PRODUCAO_HABILITADA` nem reverter emissão produção.

> **Documento histórico:** `docs/go-live-nfe-saida-producao.md` descreve o planejamento pré-T0 (2026-06). O **estado operacional atual do servidor** é produção fiscal ativa — ver seção «Situação desejada» abaixo.

---

## 1. Situação desejada no servidor

| Fluxo | Ambiente SEFAZ | Comportamento |
|-------|----------------|---------------|
| **NF-e Saída (emissão própria)** | Produção (`tpAmb=1`) | **Ativo** — preservar configuração e operação atuais |
| **Manifestação do Destinatário** | Produção (`homologacao=False` no código) | Manual; só NF-e `tpAmb=1` |
| **Central DF-e / DF-e Recebidos** | Produção | Captura e consulta de documentos reais destinados |
| **XML NF-e fornecedor** | Produção | Armazenamento manual → **Base NF-e Entrada Importada** |
| **XML CT-e transportadora** | Produção | Armazenamento manual → **Base CT-e Importada** |
| **CT-e** | Produção | **Sem** Manifestação do Destinatário |
| **Homologação (`tpAmb=2`)** | Teste/dev | **Excluída** do fechamento mensal, contador e bases fiscais reais |

### O que continua manual (não automatizar)

- Manifestação do Destinatário (evento por NF-e, sem lote).
- Download/armazenamento de XML completo (NF-e e CT-e).
- Confirmação da Operação **não** vem pré-selecionada no modal.

### O que não é gerado automaticamente

- Financeiro (CP/CR).
- Estoque.
- Expedição / rateio.
- Apuração fiscal automática.

---

## 2. Commits a subir

| Commit | Descrição |
|--------|-----------|
| `ee66354` | Manifestação do Destinatário, Central DF-e, armazenamento XML, parser retorno SEFAZ, UF da chave |
| `1fcfb76` | Migration produtos `0024` (se pendente no servidor) |

Se o deploy for merge completo da branch, todos os commits entre a base do servidor e `ee66354` sobem juntos. Para deploy **somente fiscal**, preferir merge seletivo ou cherry-pick de `ee66354`.

---

## 3. Migrations (verificar no servidor — não aplicar daqui)

```bash
docker compose exec -T backend python manage.py showmigrations fiscal produtos cadastros
```

| App | Migration | Obrigatória para |
|-----|-----------|------------------|
| fiscal | `0049_nfe_destinada_manifestacao_4015` | Manifestação / monitor NF-e destinada |
| cadastros | `0013_empresa_nfe_ambiente` | Dependência de `0049` |
| produtos | `0024_alter_familiaproduto_tipo_dimensional_and_more` | Branch atual (se pendente) |

Conferir também `fiscal.0041`–`0048` se o servidor estiver atrás da branch.

---

## 4. Configuração fiscal de produção (servidor)

**Não alterar `.env` neste procedimento.** Confirmar no servidor que a configuração **já existente** suporta produção fiscal completa.

| Item | O que confirmar |
|------|-----------------|
| `NFE_PRODUCAO_HABILITADA` | Se **já está `true` no servidor**, **preservar**. Não desligar. |
| `NFE_AMBIENTE` | Referência documental; emissão produção é controlada pela flag acima + cadastro empresa |
| `NEXUS_APP_AMBIENTE` | Badge visual do app; não substitui `tpAmb` fiscal |
| Certificado A1 | Cadastrado na empresa (`certificado_arquivo` + senha no cadastro, **não** no repositório) |
| CNPJ certificado | Compatível com CNPJ da empresa destinataria/emitente conforme o fluxo |
| `NO_PROXY` (se aplicável) | Domínios SEFAZ sem interceptação de proxy |

### Separação técnica no código (sem misturar fluxos)

| Módulo | Gate de produção |
|--------|------------------|
| NF-e Saída `emitir-producao` | `NFE_PRODUCAO_HABILITADA` + permissão `fiscal_nfe_producao` + confirmação dupla |
| Manifestação / DF-e / baixar XML | `homologacao=False` fixo; documentos `tpAmb=2` rejeitados ou filtrados |
| Fechamento mensal | `ambiente=PRODUCAO` em manifestação; `q_excluir_homologacao_*` em NF-e/CT-e base |

**Certificados e senhas:** nunca versionados (`.gitignore`: `.env`, `*.pfx`). Volume `certificados/` no servidor — fazer backup antes do deploy.

---

## 5. Rotas que exigem restart do backend

Após deploy de código ou alteração em `api_urls.py`:

```
POST /api/central-dfe/{id}/armazenar-xml-nfe/
POST /api/central-dfe/{id}/armazenar-xml-cte/
POST /api/fiscal/manifestacao-destinatario/consultar/
POST /api/fiscal/manifestacao-destinatario/iniciar-por-chave/
POST /api/fiscal/manifestacao-destinatario/{id}/manifestar/
POST /api/fiscal/manifestacao-destinatario/{id}/baixar-xml/
GET  /api/fiscal/manifestacao-destinatario/fechamento-preview/
```

```bash
docker compose restart backend
# frontend, se em container:
docker compose restart frontend
```

---

## 6. Filtro de homologação (fechamento e bases reais)

Documentos com `tpAmb=2` (homologação):

- **Não** entram no preview de fechamento mensal de manifestação (`ambiente=PRODUCAO` apenas).
- **Não** entram nas contagens de NF-e/CT-e armazenados no fechamento (`q_excluir_homologacao_historica_entrada`, `q_excluir_homologacao_cte`).
- **Não** devem ser armazenados como base fiscal oficial (serviços retornam erro para homologação).
- Permanecem visíveis em ambiente de teste/dev quando capturados, com badges de homologação.

---

## 7. Checklist final para o operador (servidor)

### Pré-deploy

1. [ ] **Backup do banco** PostgreSQL.
2. [ ] **Backup do volume de certificados** (`certificados/`).
3. [ ] Confirmar **branch/commits** a subir (`ee66354` mínimo).
4. [ ] Confirmar **migrations pendentes** (`showmigrations`).
5. [ ] Confirmar **configuração fiscal de produção já existente** (`NFE_PRODUCAO_HABILITADA` preservada se `true`; certificado válido; CNPJ compatível).

### Deploy

6. [ ] `git pull` / merge da branch no servidor.
7. [ ] `docker compose exec -T backend python manage.py migrate --noinput` (após revisar pendências).
8. [ ] `docker compose restart backend` (e frontend se aplicável).

### Pós-deploy — regressão NF-e Saída produção

9. [ ] **Validar NF-e Saída produção ainda funcionando** (conferência, validar-emissao-producao, emissão se operação normal do dia exigir).
10. [ ] Confirmar que **não** houve alteração de numeração, DANFE/BFR ou XML de saída por este deploy.

### Pós-deploy — Central DF-e e Manifestação

11. [ ] Abrir **Fiscal > DF-e Recebidos** (`/central-dfe`).
12. [ ] Confirmar **CT-e sem botão Manifestar**; ações: Ver CT-e, Abrir na Base, Armazenar XML, Conferir.
13. [ ] Confirmar **NF-e Fornecedor com Manifestar** (evento não pré-selecionado).
14. [ ] **Primeira Manifestação manual** em NF-e real controlada (`tpAmb=1`); verificar status e histórico após reload.
15. [ ] **Armazenar XML manualmente** (NF-e e/ou CT-e conforme caso).
16. [ ] Confirmar XML na **Base NF-e Entrada Importada** / **Base CT-e Importada**.
17. [ ] Confirmar **ausência** de CP/CR, expedição, movimentação de estoque ou apuração automática novos.
18. [ ] Preview de **fechamento mensal** — contagem só com documentos de produção.

---

## 8. Comandos sugeridos (operador)

```bash
# Backup
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  > backup_pre_40152_$(date +%Y%m%d_%H%M).sql

# Código
git fetch origin
git checkout feat/comercial-status-itens-proposta   # ou branch de produção após merge
git pull

# Migrations (somente após showmigrations)
docker compose exec -T backend python manage.py showmigrations fiscal produtos
docker compose exec -T backend python manage.py migrate --noinput

# Restart
docker compose restart backend
docker compose restart frontend   # se aplicável

# Smoke API (usuário fiscal autenticado)
# GET /api/fiscal/manifestacao-destinatario/?empresa_id=...
# GET /api/central-dfe/?empresa_id=...
```

---

## 9. Riscos antes de usar certificado real

| Risco | Mitigação |
|-------|-----------|
| Quebrar NF-e Saída produção | Validar item 9 do checklist **antes** de manifestar |
| Manifestar NF-e homologação | Backend rejeita; usar só `tpAmb=1` |
| cStat 657 (órgão divergente) | UF do evento = UF da chave (`uf_chave.py` em `ee66354`) |
| CNPJ certificado ≠ empresa | Validar em Cadastros antes do deploy |
| Homologação no fechamento | Verificar que preview não conta `tpAmb=2` |
| Rollback apaga histórico fiscal | Não reverter migration `0049` com dados; ver §10 |

---

## 10. Plano de rollback

1. Reverter **código** para commit estável anterior (`git revert` ou checkout).
2. `docker compose restart backend`.
3. **Não** reverter migration `0049` se já existirem registros em `NFeDestinadaManifestacao` / eventos.
4. **Não** desligar `NFE_PRODUCAO_HABILITADA` como parte do rollback desta feature — NF-e Saída produção deve permanecer operacional.
5. Manifestações e XMLs já transmitidos/armazenados à SEFAZ **não** são desfeitos pelo rollback de software.

---

## 11. Confirmações de entrega (4.0.15.2.1)

- [x] Checklist corrigido para **produção fiscal completa**
- [x] Documento **não** orienta desligar NF-e Saída produção
- [x] Documento orienta **preservar** NF-e Saída produção funcionando
- [x] Manifestação em produção SEFAZ confirmada
- [x] Central DF-e / DF-e Recebidos em produção confirmados
- [x] XML NF-e → Base NF-e Entrada Importada; XML CT-e → Base CT-e Importada
- [x] CT-e sem Manifestação do Destinatário
- [x] Homologação excluída do fechamento mensal
- [x] Manifestação manual; armazenamento XML manual
- [x] Sem financeiro/estoque/expedição/rateio/apuração automática
- [x] Plano de rollback sem apagar histórico fiscal
- [x] **Sem alteração de código, `.env`, SEFAZ, certificado ou XML real nesta entrega documental**

---

*Última atualização: 15/06/2026 — ERP 4.0.15.2.1*
