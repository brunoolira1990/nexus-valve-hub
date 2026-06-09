# BrazilFiscalReport — DANFE modelo 55 (renderizador oficial)

## Status (ERP 4.0.13.6.13A)

**BrazilFiscalReport (BFR) é o único renderizador oficial do DANFE** no Nexus ERP:

- Conferência, rascunho, preview, homologação autorizada e reimpressão usam o mesmo layout BFR.
- Fallback HTML/WeasyPrint foi **removido** do fluxo oficial (`DANFE_ALLOW_HTML_FALLBACK=false`).
- Se BFR falhar: erro 503, log `[DANFE_BFR_ERROR]`, emissão bloqueada — **sem** PDF alternativo.

Settings:

| Setting | Default | Descrição |
|---------|---------|-----------|
| `DANFE_RENDERER_OFICIAL` | `BFR` | Renderizador único |
| `DANFE_ALLOW_HTML_FALLBACK` | `false` | Fallback HTML proibido |
| `DANFE_ALLOW_HTML_DIAGNOSTIC` | `false` | Modo diagnóstico HTML (só DEBUG) |
| `DANFE_BLOCK_EMISSION_IF_BFR_FAILS` | `true` | Bloqueia «Marcar pronta» se BFR falhar |
| `DANFE_LOG_RENDERER` | `true` | Logs técnicos de renderização |

## Instalação (backend Docker)

- Pacote: `BrazilFiscalReport==0.7.4`
- Dependências pip transitivas: `fpdf2`, `python-barcode`, `phonenumbers`, `defusedxml`
- **Sem** dependências de sistema extras além do `python:3.12-slim`
- Compatível com Python 3.12 do projeto
- `reportlab` permanece no projeto para PDFs comerciais (Pedido de Venda, Proposta, Pedido de Compra, certificados) — **não** usado para DANFE oficial
- `weasyprint` foi removido de `requirements.txt` (era usado apenas para DANFE HTML legado)

## Licença (LGPL-3.0)

| Item | Conclusão |
|------|-----------|
| Licença do pacote | **GNU LGPL v3** |
| Uso em ERP/SaaS fechado | Permitido como biblioteca vinculada, com due diligence jurídica |
| Recomendação | Validar com assessoria antes de produção multi-tenant |

## API Nexus

Módulo: `apps/fiscal/nfe_integracao/danfe_brazil_fiscal_report.py`

- `gerar_danfe_bfr_de_xml_bytes` / `gerar_danfe_bfr_de_xml_string`
- `gerar_danfe_bfr_de_nfe_saida_preview` (XML preliminar nfelib)
- `gerar_danfe_bfr_homologacao_autorizada` (XML autorizado + protocolo)

Orquestração: `apps/fiscal/danfe_render.py` → `gerar_danfe_bfr_oficial`

Logs: `apps/fiscal/danfe_bfr_log.py` — `[DANFE_BFR_ERROR]`, `[DANFE_FALLBACK_BLOQUEADO]`

## Customização Nexus

- `DanfeNexus` + `resolver_marca_dagua_danfe()` — marca d'água por status (conferência vs autorizado)
- Logo emitente via `DanfeConfig.logo` + `get_empresa_logo_path_or_none`
- `montar_informacoes_complementares_danfe()` — infCpl enxuto; observações internas nunca no PDF

## Limitações conhecidas

1. XML de prévia exige sanitização (comentários, declaração XML duplicada).
2. Caracteres Unicode em `infCpl` podem quebrar fonte — normalizar para ASCII.
3. `nNF` deve ser numérico — prévia usa pk via `nfe_numero_fiscal_preliminar`.
4. Chave/barcode em prévia derivam de `infNFe@Id` — não são documento fiscal válido até autorização SEFAZ.

## Renderizadores removidos (4.0.13.6.13A)

- `danfe_modelo55_html.py` (WeasyPrint)
- `danfe_modelo55_conferencia.py` (ReportLab canvas)
- `danfe_moc_matriz_a4_retrato.py`
- `templates/danfe/modelo55_conferencia.html` / `.css`
- Flag `FISCAL_DANFE_RENDERER` e `FISCAL_DANFE_BFR_FALLBACK_HTML`

## Próximos passos

1. Parecer jurídico LGPL para produção SEFAZ.
2. Modo diagnóstico HTML opcional (endpoint separado, só DEBUG/homologação) se necessário para suporte.
3. DANFE produção com XML + `protNFe` reais após emissão produção.
