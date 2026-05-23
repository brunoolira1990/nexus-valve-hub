# POC BrazilFiscalReport 0.7.4 — DANFE modelo 55

## Motivo

A DANFE Conferência atual (HTML/CSS + WeasyPrint) ainda apresenta instabilidade visual; após ajustes de densidade (3.5.4.7), NF-e com um item pode quebrar em duas páginas. Esta POC avalia se **BrazilFiscalReport** pode substituir ou complementar o renderizador.

## Instalação (backend Docker)

- Pacote: `BrazilFiscalReport==0.7.4`
- Dependências pip transitivas: `fpdf2`, `python-barcode`, `phonenumbers`, `defusedxml`
- **Sem** dependências de sistema extras além do que o `python:3.12-slim` já possui (diferente do WeasyPrint)
- Compatível com Python 3.12 do projeto
- Não remove `weasyprint`, `reportlab`, `lxml`, `signxml`, `nfelib`, `PyNFe`

## Licença (LGPL-3.0)

| Item | Conclusão |
|------|-----------|
| Licença do pacote | **GNU LGPL v3** (metadado PyPI / arquivo LICENSE no wheel) |
| Uso em ERP/SaaS fechado | Permitido como **biblioteca vinculada** (import Python), desde que cumpridos requisitos LGPL |
| Obrigações principais | Permitir substituição da biblioteca pelo usuário; fornecer meios de relink; aviso de uso da LGPL; licença da lib acessível ao usuário final |
| Impacto Nexus (código fechado) | **Uso em produção é possível**, mas exige processo jurídico/compliance (documentação de dependência, oferta de código-fonte/correspondente da LGPL conforme política do produto) |
| Alternativa conservadora | Manter só como **referência/POC** até parecer jurídico aprovar LGPL em produção |

**Recomendação jurídica:** validar com assessoria antes de tornar renderizador padrão em SaaS multi-tenant.

## API Nexus (isolada)

Módulo: `apps/fiscal/nfe_integracao/danfe_brazil_fiscal_report.py`

- `gerar_danfe_bfr_de_xml_bytes`
- `gerar_danfe_bfr_de_xml_string`
- `gerar_danfe_bfr_debug_file`
- `gerar_danfe_bfr_de_nfe_saida_preview` (XML de prévia + `ajustes_poc`)

Feature flag: `FISCAL_DANFE_RENDERER` = `html` | `brazil_fiscal_report` | `reportlab_fallback` (default: `html`).

## Limitações encontradas na POC

1. **XML de prévia Nexus:** comentário + segunda declaração `<?xml` (minidom) — exige sanitização.
2. **Caracteres Unicode:** em-dash em `infCpl` quebra fonte Times — normalizar para ASCII `-`.
3. **`nNF` não numérico** (ex.: `RASCUNHO-FAT-2`): BFR falha — em POC usa-se `ajustes_poc` com número interno (`pk`), **não** exibir como chave oficial na UI.
4. **Marca d’água conferência:** não há texto customizado “NF-e CONFERÊNCIA”; com `tpAmb=2` e sem `protNFe` aparece **SEM VALOR FISCAL**; `watermark_cancelled=True` → **CANCELADA - SEM VALOR FISCAL** em homologação (não é o mesmo texto do Nexus).
5. **Chave / barcode:** derivados de `infNFe@Id`; XML prévia usa `NFePREVIEW{id}` — PDF POC gera barcode da chave derivada (não usar como chave oficial; não escaneável como documento válido).
6. **Customização:** `DanfeConfig` oferece logo, margens, fontes, `watermark_cancelled`, `footer_stamp` — **não** há hook para “FALTA PROTOCOLO” ou ocultar barcode em conferência.

## Decisão técnica (POC)

**Opção B (recomendada):** usar BrazilFiscalReport **somente para DANFE autorizada futura**, com XML oficial assinado/autorizado (chave 44 dígitos, `protNFe`). Manter **HTML/CSS + WeasyPrint** para conferência pré-emissão (textos e layout sob controle do Nexus).

Motivos: conferência exige mensagens e ausência de barcode escaneável fake; BFR não customiza marca/textos de conferência; LGPL exige due diligence; preview XML do Nexus não é drop-in.

**Opção C** permanece válida se a equipe preferir um único motor visual e continuar refinando WeasyPrint (corrigir paginação 1 item → 2 páginas).

## Comparação visual

Gerar localmente (Docker):

```bash
docker compose exec backend python manage.py shell -c "
from pathlib import Path
from django.conf import settings
from apps.fiscal.models import NFeSaida
from apps.fiscal.danfe_render import render_danfe_conferencia_pdf
from apps.fiscal.danfe_conferencia import montar_dados_danfe_conferencia
from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
    XML_NFE_EXEMPLO_POC, gerar_danfe_bfr_debug_file, gerar_danfe_bfr_de_nfe_saida_preview,
)
out = Path(settings.MEDIA_ROOT) / 'debug'
out.mkdir(parents=True, exist_ok=True)
gerar_danfe_bfr_debug_file(XML_NFE_EXEMPLO_POC, out / 'danfe_bfr_exemplo.pdf')
nf = NFeSaida.objects.filter(numero__icontains='RASCUNHO-FAT-2').first()
if nf:
    pdf, _ = gerar_danfe_bfr_de_nfe_saida_preview(nf)
    (out / 'danfe_bfr_rascunho.pdf').write_bytes(pdf)
    dados = montar_dados_danfe_conferencia(nf)
    html_pdf, _ = render_danfe_conferencia_pdf(dados)
    (out / 'danfe_html_rascunho.pdf').write_bytes(html_pdf)
print('PDFs em', out)
"
```

Comparar `media/debug/danfe_bfr_*.pdf` com `danfe_html_rascunho.pdf` e o PDF de referência de mercado (anexo externo).

## Próximos passos

1. Corrigir paginação WeasyPrint (1 item / 1 página).
2. Parecer jurídico LGPL antes de `FISCAL_DANFE_RENDERER=brazil_fiscal_report` em produção.
3. Se aprovado para emitida: integrar após autorização SEFAZ com XML + `protNFe` reais, sem `ajustes_poc`.
