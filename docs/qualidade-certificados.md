# Qualidade — tipos de certificado no ERP

Documentação **Fase D (tipos de certificado)** e **Fases E.2–E.4 (matriz de permissões, RBAC mínimo no backend e UX de 403 no frontend)**. Objetivo: alinhar desenvolvimento e operação sobre conceitos, riscos e **política de acesso** — a matriz (E.2) continua **recomendação**; a implementação incremental está descrita na secção 8.

---

## 1. Visão geral

No módulo de Qualidade (e pontos adjacentes em Fiscal) coexistem **três** entidades com o termo “certificado”:

| Conceito | Modelo principal | Papel resumido |
|----------|------------------|----------------|
| Legado automático | `Certificado` | PDF simples gerado ao persistir **NF-e de saída**; compatibilidade histórica. |
| Oficial de qualidade | `CertificadoQualidade` | Documento **emitido pela Nexus** com ciclo de vida, PDF oficial e rastreabilidade rica. |
| Entrada / fornecedor | `CertificadoFornecedorEntrada` | **Documento recebido** do fornecedor na entrada; base de **dados técnicos** para o CQ. |

São fluxos **paralelos por desenho**: o legado não foi substituído automaticamente pelo CQ. Por isso a política de uso e os riscos abaixo são relevantes para evolução futura do produto.

---

## 2. Certificado legado (`Certificado`)

### Modelo e vínculo

- **Modelo:** `apps.qualidade.models.Certificado`
- **Vínculo:** `OneToOneField` com `fiscal.NFeSaida` (`related_name='certificado'`)
- **Armazenamento:** `FileField` `arquivo` + `gerado_em`

### Geração e PDF

- **Gatilho:** criação e atualização de `NFeSaida` via `NFeSaidaSerializer` em `apps.fiscal.serializers` — função `_gerar_ou_atualizar_certificado`: remove certificado anterior da NF, chama `gerar_certificado_pdf(nf)` em `apps.qualidade.certificado_pdf`, grava novo `Certificado`.
- **PDF:** `gerar_certificado_pdf` — layout **canvas**, **A4 retrato**, conteúdo mínimo (ex.: “Certificado de conformidade”, itens/corridas). **Não** é o PDF oficial do `CertificadoQualidade` (A4 paisagem, template v3, marcas d’água de prévia/cancelado, etc.).

### API

- **ViewSet:** `CertificadoViewSet` — **somente leitura** (`ReadOnlyModelViewSet`)
- **Serializer:** `CertificadoSerializer` — campos típicos: `id`, `nf_saida`, `arquivo`, `gerado_em`
- **Rota registrada:** `GET /api/certificados/` e `GET /api/certificados/{id}/` (basename `certificado`)

### Papel recomendado

- **Compatibilidade / legado:** manter enquanto existirem integrações ou processos que esperem um arquivo por NF de saída.
- **Não** tratar como **certificado oficial de qualidade Nexus** para cliente, auditoria comercial ou substituição do `CertificadoQualidade`.

---

## 3. Certificado de qualidade (`CertificadoQualidade`)

### Papel

- **Documento oficial de qualidade** emitido pela empresa (Nexus), com regras de rascunho, emissão e cancelamento.

### Ciclo de vida e PDF

- **Status:** `rascunho` | `emitido` | `cancelado`
- **PDF:** `gerar_certificado_qualidade_pdf` — documento operacional validado (Fases A/C): prévia/rascunho, cancelado com marcação explícita, layout A4 paisagem.

### Vínculos

- Cliente (FK + snapshots)
- **NF saída:** `nota_fiscal` (operacional) e/ou `nota_fiscal_historica` (histórica importada), conforme cadastro
- Itens (`ItemCertificadoQualidade`), opcionalmente componentes para válvula

### API e UI

- **Rota API:** `/api/certificados-qualidade/` (CRUD + ações, ex.: `preencher-por-nfe`, `pdf`)
- **Tela SPA:** rota **`/certificados`** — “Certificados de Qualidade” (lista + modal de edição/emissão/PDF)

### Papel recomendado

- **Fonte oficial** para processos comerciais, envio ao cliente e **auditoria** quando o assunto for “certificado de qualidade emitido pela Nexus”.

---

## 4. Certificado de fornecedor (`CertificadoFornecedorEntrada`)

### Papel

- **Documento técnico recebido do fornecedor** na cadeia de **entrada** (NF-e de entrada operacional ou histórica).

### Conteúdo e uso

- Cabeçalho (fornecedor, NF, número do certificado do fornecedor, etc.) + **itens** e, quando aplicável, **componentes** (válvula).
- **Uso pelo CQ:** busca de dados técnicos (corrida, lote, composição, ensaios, etc.) para preencher ou validar itens do `CertificadoQualidade`; snapshots e IDs de origem nos itens do CQ.

### API e UI

- **Rota API:** `/api/certificados-fornecedor/` (+ endpoints de busca de dados técnicos conforme implementação)
- **Tela SPA:** **`/certificados-fornecedor`**

### Papel recomendado

- **Evidência de entrada** e **insumo técnico**; **não** é certificado **emitido** pela Nexus na saída.

---

## 5. Endpoints e telas (resumo)

### Endpoints principais

| Uso | Método / caminho (prefixo típico `/api/`) |
|-----|-------------------------------------------|
| Legado por NF saída | `GET certificados/`, `GET certificados/{id}/` |
| CQ (oficial) | `certificados-qualidade/` (CRUD + `pdf`, `preencher-por-nfe`, …) |
| Fornecedor (entrada) | `certificados-fornecedor/` (CRUD + buscas de dados técnicos) |

*(Detalhes de query params e actions: código em `apps/qualidade/views.py` e `apps/api_urls.py`.)*

### Telas SPA

| Rota SPA | Conteúdo |
|----------|-----------|
| `/certificados` | **CertificadoQualidade** (não consome o endpoint legado `certificados`) |
| `/certificados-fornecedor` | **CertificadoFornecedorEntrada** |

### Atenção: nomes parecidos

- **`/certificados`** (frontend) ≠ **`/api/certificados/`** (API legada).  
  - O primeiro é a **tela do certificado de qualidade**.  
  - O segundo é a **API somente leitura** do PDF automático ligado à `NFeSaida`.  
  Evitar assumir que “certificados” no URL da SPA se refere ao modelo `Certificado` legado.

---

## 6. Riscos conhecidos

1. **Duplicidade conceitual na mesma NF de saída**  
   Pode existir o registro **legado** (`Certificado` + PDF simples) **e** um ou mais **`CertificadoQualidade`** referenciando a mesma NF (operacional ou histórica). Não há, por si só, um único “donos” do conceito na UI unificada.

2. **PDF legado confundido com o oficial**  
   Ambos são PDFs “de certificado”, com layouts e semânticas diferentes. Quem só abre o anexo da NF pode interpretar o legado como documento final de qualidade.

3. **Integrações antigas**  
   Consumidores de `GET /api/certificados/` podem continuar existindo; alterações futuras exigem **inventário** antes de depreciar.

4. **Erro operacional**  
   Operador pode emitir/consultar o documento que **não** corresponde ao processo desejado (legado vs CQ), se o processo interno não estiver documentado.

---

## 7. Política recomendada de uso

| Tipo | Política |
|------|----------|
| **`CertificadoQualidade`** | **Oficial** para qualidade Nexus na saída (comercial, cliente, auditoria). |
| **`Certificado` (legado)** | **Compatibilidade**; não posicionar como substituto do CQ. |
| **`CertificadoFornecedorEntrada`** | **Insumo técnico de entrada** e evidência do fornecedor; suporte ao CQ, não “o” certificado de qualidade emitido pela Nexus. |

---

## 8. Permissões e ações críticas (Fase E.2 + implementação E.3/E.4)

Esta secção documenta em primeiro lugar a **política recomendada** (matriz E.2). **Implementação actual (Fase E.3):** os viewsets `CertificadoViewSet`, `CertificadoQualidadeViewSet` e `CertificadoFornecedorEntradaViewSet` em `apps/qualidade/views.py` definem `permission_classes` com **`IsAuthenticated`** mais classes que verificam **permissões de modelo Django** por acção (ver comentário “Fase E.3” no ficheiro). Utilizadores sem o codename adequado recebem **HTTP 403**. **Fase E.4:** o frontend (`Certificados.tsx`, `CertificadosFornecedor.tsx`, `apiErrorMessage` / `formatApiErrors`) trata 403 com mensagem explícita; o JWT **não** transporta codenames — capacidades finas na UI dependem de evolução futura (ex. endpoint de permissões). O frontend **não** substitui o controlo do servidor.

### 8.1 Perfis conceituais (política alvo)

| Perfil | Descrição |
|--------|-----------|
| **1. Consulta Qualidade** | Leitura de listas e detalhes; PDF conforme regra da empresa (ex.: só documentos **emitidos** / **registrados**, não expor rascunho a todos). |
| **2. Operador Qualidade** | Cria e edita **rascunhos**; prepara certificado; usa **preencher por NF**, **corridas disponíveis** e **buscar dados técnicos**; **não** cancela, **não** apaga e **não** deve emitir/registrar sozinho se a empresa exigir dupla validação. |
| **3. Responsável Qualidade** | Pode **emitir** CQ, **registrar** certificado de fornecedor, **cancelar**; pode **alterar emitido/registrado** apenas quando necessário e auditável. |
| **4. Administrador** | Ações excepcionais; **apagar** (`DELETE`) apenas se a empresa aceitar o risco para auditoria; útil para correcção de dados ou ambiente controlado. |

*Os nomes são conceituais: podem mapear para grupos Django, cargos RH ou integrações com nomes próprios.*

### 8.2 Ações a controlar (inventário)

**Certificado de qualidade (`CertificadoQualidade` — `/api/certificados-qualidade/`)**

| Ação | Mapeamento API típico |
|------|------------------------|
| Listar | `GET` coleção |
| Visualizar detalhe | `GET` detalhe |
| Gerar PDF | `GET …/{id}/pdf/` (query `preview` conforme regra) |
| Criar rascunho | `POST` criação (status rascunho) |
| Editar rascunho | `PATCH`/`PUT` com certificado em rascunho |
| Editar emitido | `PATCH`/`PUT` com certificado já emitido |
| Emitir certificado | `PATCH`/`PUT` (fluxo que grava como emitido) ou equivalente no serializer |
| Cancelar certificado | `PATCH`/`PUT` alterando status para cancelado |
| Apagar certificado | `DELETE` detalhe |
| Preencher por NF saída | `POST …/preencher-por-nfe/` |
| Corridas disponíveis | `GET …/corridas-disponiveis/?produto_id=` |

**Certificado de fornecedor (`CertificadoFornecedorEntrada` — `/api/certificados-fornecedor/`)**

| Ação | Mapeamento API típico |
|------|------------------------|
| Listar / detalhe | `GET` coleção / detalhe |
| Criar / editar rascunho | `POST` / `PATCH` em rascunho |
| Editar registrado | `PATCH`/`PUT` com status registrado (correções controladas) |
| Registrar | `PATCH`/`PUT` passando a registrado (conforme serializer) |
| Cancelar | `PATCH`/`PUT` para cancelado |
| Apagar | `DELETE` |
| Preencher por NF entrada | `POST …/preencher-por-nfe-entrada/` |
| Buscar dados técnicos | `GET …/buscar-dados-tecnicos/` |

**Certificado legado (`Certificado` — `/api/certificados/`)**

| Ação | Mapeamento API típico |
|------|------------------------|
| Acessar / listar | `GET` (viewset só leitura) |

### 8.3 Matriz ação × perfil (recomendada)

Legenda: **Sim** = permitido · **Não** = negado · **Cond.** = permitido com processo excecional / auditoria / política escrita da empresa

#### Certificado de qualidade (CQ)

| Ação | Consulta | Operador | Responsável | Admin |
|------|:--------:|:--------:|:-----------:|:-----:|
| Listar | Sim | Sim | Sim | Sim |
| Visualizar detalhe | Sim | Sim | Sim | Sim |
| Gerar PDF | Cond.¹ | Sim | Sim | Sim |
| Criar rascunho | Não | Sim | Sim | Sim |
| Editar rascunho | Não | Sim | Sim | Sim |
| Editar emitido | Não | Não | Cond.² | Cond.² |
| Emitir | Não | Cond.³ | Sim | Sim |
| Cancelar | Não | Não | Sim | Sim |
| Apagar | Não | Não | Não | Cond.⁴ |
| Preencher por NF | Não | Sim | Sim | Sim |
| Corridas disponíveis | Cond.⁵ | Sim | Sim | Sim |

¹ *Consulta:* PDF só de certificados **emitidos** (e opcionalmente cancelados para auditoria), **sem** prévia de rascunho de terceiros, se assim definir a empresa.  
² *Responsável/Admin:* alteração pós-emissão só quando necessário e rastreável.  
³ *Operador:* emitir apenas se a empresa permitir sem segundo olhar; caso contrário **Não** e só Responsável **Sim**.  
⁴ *Admin:* `DELETE` só se a política corporativa aceitar perda de registro.  
⁵ *Consulta:* endpoint cruza estoque/conferência/fornecedor — restringir se dados forem sensíveis.

#### Certificado de fornecedor (CF)

| Ação | Consulta | Operador | Responsável | Admin |
|------|:--------:|:--------:|:-----------:|:-----:|
| Listar / detalhe | Sim | Sim | Sim | Sim |
| Criar / editar rascunho | Não | Sim | Sim | Sim |
| Editar registrado | Não | Não | Cond.² | Cond.² |
| Registrar | Não | Cond.³ | Sim | Sim |
| Cancelar | Não | Não | Sim | Sim |
| Apagar | Não | Não | Não | Cond.⁴ |
| Preencher por NF entrada | Não | Sim | Sim | Sim |
| Buscar dados técnicos | Cond.⁵ | Sim | Sim | Sim |

#### Certificado legado

| Ação | Consulta | Operador | Responsável | Admin |
|------|:--------:|:--------:|:-----------:|:-----:|
| Listar / visualizar | Cond.⁶ | Cond.⁶ | Cond.⁶ | Sim |

⁶ *Acesso ao legado* pode ser limitado a quem precisa de integração ou suporte; evitar exposição amplo a todos os autenticados.

### 8.4 Riscos residual (após E.3/E.4)

- Com **E.3**, deixou de ser verdade que *qualquer* autenticado pode todas as acções nas APIs de **Qualidade** listadas acima; ainda assim, **outros módulos** da API podem manter política mais permissiva — não generalizar.
- O **frontend não é barreira de segurança**; chamadas directas (Postman, scripts) contornam botões; **E.4** melhora UX de 403, não a segurança por si.
- **`DELETE`** continua sensível para **auditoria**; política corporativa deve limitar quem recebe `delete_*`.
- **PDF** e **buscas** continuam a expor dados comerciais/técnicos; a matriz (condicionantes de negócio) pode ser reforçada em fases futuras (object-level, regras por status).
- **Integrações antigas** sem permissões Django correctas passam a ver **403** — comunicação e atribuição de grupos/permissões continuam necessárias.

### 8.5 Plano incremental (RBAC) — estado

1. **Validar** esta matriz com produto / compliance / operação — *em curso / iterativo*.  
2. **`permission_classes` por viewset** (Qualidade) — **feito (E.3)**; refinamentos futuros (object permissions, regras por status no PDF, etc.).  
3. **Testes 403/200** — **feito** para os viewsets de Qualidade (`apps/qualidade/tests/`).  
4. **Frontend** — **feito (E.4)** mensagem de 403; ocultar «Novo» só quando o GET da lista devolve 403; evolução: claims ou `/me/permissions`.  
5. **Comunicar** a integrações e utilizadores sobre **403** e atribuir permissões em Django — *operacional*.

---

## 9. Plano futuro — consolidação de modelos e legado (não executar só com este documento)

Ordem sugerida para evolução **segura**, quando o produto autorizar:

1. **Inventariar consumidores** do endpoint `GET /api/certificados/` (logs, integrações, scripts).
2. **Decidir política de negócio:** ex. se haverá **no máximo um CQ canônico** por NF de saída (ou exceções documentadas).
3. **Avaliar depreciação** do legado: comunicação, período de transição, alternativa (ex.: link ou metadado para CQ).
4. **Só então** planejar mudanças estruturais: migrations, FK explícita, backfill, desligamento da geração automática ou do endpoint — **fora do escopo deste arquivo**.

---

## Referências rápidas no código

- Modelos: `backend/apps/qualidade/models.py`
- PDF CQ e função legada: `backend/apps/qualidade/certificado_pdf.py`
- Views CQ / fornecedor / legado: `backend/apps/qualidade/views.py`
- Geração legada na NF saída: `backend/apps/fiscal/serializers.py` (`_gerar_ou_atualizar_certificado`)
- Remoção na exclusão da NF: `backend/apps/fiscal/views.py` (`NFeSaidaViewSet.perform_destroy`)
- Rotas: `backend/apps/api_urls.py`
- Testes de qualidade: `backend/apps/qualidade/tests/` (inclui permissões E.3)

---

*Última atualização: Fases D–E.4 + F (revisão documental; RBAC mínimo em `views.py` + UX 403 no frontend).*
