"""POC NF-e 3.5.4.6 — DANFE via BrazilFiscalReport (isolado, sem SEFAZ/status/estoque).

Uso esperado da biblioteca::

    from brazilfiscalreport.danfe import Danfe
    danfe = Danfe(xml=xml_content)
    danfe.output(path)

Licença do pacote: LGPL-3.0 (ver docs/fiscal/brazil-fiscal-report-poc.md).
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# XML NF-e 4.00 mínimo para testes/POC (homologação, 1 item, chave fictícia só debug).
XML_NFE_EXEMPLO_POC = """<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
<infNFe Id="NFe35240512345678000190550010000000011000000010" versao="4.00">
<ide>
<cUF>35</cUF><cNF>00000001</cNF><natOp>Venda</natOp><mod>55</mod><serie>1</serie><nNF>1</nNF>
<dhEmi>2024-05-21T10:00:00-03:00</dhEmi><tpNF>1</tpNF><idDest>1</idDest><cMunFG>3550308</cMunFG>
<tpImp>1</tpImp><tpEmis>1</tpEmis><cDV>0</cDV><tpAmb>2</tpAmb><finNFe>1</finNFe><indFinal>1</indFinal><indPres>1</indPres><procEmi>0</procEmi><verProc>NexusPOC</verProc>
</ide>
<emit><CNPJ>12345678000190</CNPJ><xNome>EMITENTE TESTE LTDA</xNome><xFant>EMITENTE</xFant><IE>123456789012</IE><CRT>3</CRT>
<enderEmit><xLgr>Rua Teste</xLgr><nro>100</nro><xBairro>Centro</xBairro><cMun>3550308</cMun><xMun>Sao Paulo</xMun><UF>SP</UF><CEP>01001000</CEP><cPais>1058</cPais><xPais>Brasil</xPais></enderEmit>
</emit>
<dest><CNPJ>98765432000110</CNPJ><xNome>DESTINATARIO TESTE</xNome><indIEDest>9</indIEDest>
<enderDest><xLgr>Av Cliente</xLgr><nro>200</nro><xBairro>Jardim</xBairro><cMun>3550308</cMun><xMun>Sao Paulo</xMun><UF>SP</UF><CEP>02002000</CEP><cPais>1058</cPais><xPais>Brasil</xPais></enderDest>
</dest>
<det nItem="1"><prod><cProd>001</cProd><cEAN>SEM GTIN</cEAN><xProd>Produto POC BrazilFiscalReport</xProd><NCM>84818099</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>100.00</vUnCom><vProd>100.00</vProd><cEANTrib>SEM GTIN</cEANTrib><uTrib>UN</uTrib><qTrib>1.0000</qTrib><vUnTrib>100.00</vUnTrib><indTot>1</indTot></prod>
<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC><vBC>100.00</vBC><pICMS>18.00</pICMS><vICMS>18.00</vICMS></ICMS00></ICMS></imposto></det>
<total><ICMSTot><vBC>100.00</vBC><vICMS>18.00</vICMS><vProd>100.00</vProd><vNF>100.00</vNF></ICMSTot></total>
<transp><modFrete>9</modFrete></transp>
<infAdic><infCpl>POC BrazilFiscalReport - XML de teste Nexus (nao transmitir)</infCpl></infAdic>
</infNFe>
</NFe>
"""


class DanfeBfrError(Exception):
    """Erro amigável na geração DANFE via BrazilFiscalReport."""


class DanfeBfrIndisponivelError(DanfeBfrError):
    """Biblioteca não instalada ou dependência ausente."""


def _importar_danfe():
    try:
        from brazilfiscalreport.danfe import Danfe
        from brazilfiscalreport.danfe.config import DanfeConfig
    except ImportError as exc:
        raise DanfeBfrIndisponivelError(
            'BrazilFiscalReport não está instalado. Adicione BrazilFiscalReport==0.7.4 ao ambiente.'
        ) from exc
    return Danfe, DanfeConfig


def sanitizar_xml_para_bfr(xml: str, *, ajustes_poc: bool = False, nfe_saida_id: int | None = None) -> str:
    """Remove comentários/declarações duplicadas e normaliza texto para fontes Times da BFR."""
    if not (xml or '').strip():
        raise DanfeBfrError('XML vazio.')

    texto = str(xml)
    texto = re.sub(r'<!--.*?-->', '', texto, flags=re.DOTALL)
    texto = re.sub(r'<\?xml[^?]*\?>\s*', '', texto, flags=re.IGNORECASE)
    texto = texto.replace('\u2014', '-').replace('\u2013', '-')
    texto = texto.strip()
    if not texto.startswith('<'):
        raise DanfeBfrError('XML inválido: conteúdo não parece um documento NF-e.')

    if ajustes_poc:
        # Apenas renderização POC: nNF numérico (BFR exige int) e tpAmb homologação (marca SEM VALOR FISCAL).
        if nfe_saida_id is not None:
            texto = re.sub(r'<nNF>[^<]+</nNF>', f'<nNF>{int(nfe_saida_id)}</nNF>', texto, count=1)
        elif re.search(r'<nNF>[^0-9<]+</nNF>', texto):
            texto = re.sub(r'<nNF>[^<]+</nNF>', '<nNF>1</nNF>', texto, count=1)
        if '<tpAmb>' not in texto and '</ide>' in texto:
            texto = texto.replace('</ide>', '<tpAmb>2</tpAmb></ide>', 1)

    return texto


def _config_conferencia_poc(DanfeConfig):
    """Config BFR para rascunho/conferência: marca d'água cancelada/homolog + PIS/COFINS."""
    return DanfeConfig(
        watermark_cancelled=True,
        display_pis_cofins=True,
    )


def gerar_danfe_bfr_de_xml_string(
    xml_string: str,
    *,
    ajustes_poc: bool = False,
    nfe_saida_id: int | None = None,
) -> bytes:
    """Gera PDF DANFE a partir de XML NF-e (string). Não altera NF-e nem transmite SEFAZ."""
    Danfe, DanfeConfig = _importar_danfe()
    xml_limpo = sanitizar_xml_para_bfr(xml_string, ajustes_poc=ajustes_poc, nfe_saida_id=nfe_saida_id)
    try:
        danfe = Danfe(xml=xml_limpo, config=_config_conferencia_poc(DanfeConfig))
        buffer = BytesIO()
        danfe.output(buffer)
        pdf = buffer.getvalue()
    except DanfeBfrError:
        raise
    except Exception as exc:
        logger.warning('Falha BrazilFiscalReport ao gerar DANFE: %s', type(exc).__name__)
        raise DanfeBfrError(f'Não foi possível gerar o DANFE: {exc}') from exc

    if not pdf.startswith(b'%PDF'):
        raise DanfeBfrError('Saída não é um PDF válido.')
    return pdf


def gerar_danfe_bfr_de_xml_bytes(
    xml_bytes: bytes,
    *,
    ajustes_poc: bool = False,
    nfe_saida_id: int | None = None,
) -> bytes:
    """Gera PDF DANFE a partir de XML NF-e (bytes UTF-8)."""
    try:
        xml_string = xml_bytes.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise DanfeBfrError('XML deve estar em UTF-8.') from exc
    return gerar_danfe_bfr_de_xml_string(
        xml_string,
        ajustes_poc=ajustes_poc,
        nfe_saida_id=nfe_saida_id,
    )


def gerar_danfe_bfr_debug_file(
    xml: str | bytes,
    output_path: str | Path,
    *,
    ajustes_poc: bool = False,
    nfe_saida_id: int | None = None,
) -> str:
    """Salva PDF em disco (debug/POC). Retorna caminho absoluto."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(xml, bytes):
        pdf = gerar_danfe_bfr_de_xml_bytes(xml, ajustes_poc=ajustes_poc, nfe_saida_id=nfe_saida_id)
    else:
        pdf = gerar_danfe_bfr_de_xml_string(xml, ajustes_poc=ajustes_poc, nfe_saida_id=nfe_saida_id)
    path.write_bytes(pdf)
    return str(path.resolve())


def brazil_fiscal_report_disponivel() -> bool:
    try:
        _importar_danfe()
        return True
    except DanfeBfrIndisponivelError:
        return False


def gerar_danfe_bfr_de_nfe_saida_preview(nfe_saida) -> tuple[bytes, dict[str, Any]]:
    """POC: DANFE a partir do XML de prévia do Nexus (não persistido como autorizado)."""
    from apps.fiscal.nfe_saida_preview import gerar_preview_xml_nfe_saida

    preview = gerar_preview_xml_nfe_saida(nfe_saida)
    if preview.get('bloqueado'):
        return b'', {
            'bloqueado': True,
            'mensagens': preview.get('mensagens') or [],
            'render_engine': 'brazil_fiscal_report_poc',
        }

    xml = preview.get('xml') or ''
    pdf = gerar_danfe_bfr_de_xml_string(
        xml,
        ajustes_poc=True,
        nfe_saida_id=nfe_saida.pk,
    )
    meta = {
        'preview': True,
        'conferencia': True,
        'bloqueado': False,
        'render_engine': 'brazil_fiscal_report',
        'mensagens': [
            'DANFE POC via BrazilFiscalReport — XML de prévia, sem valor fiscal.',
            'Não transmitir. Sem protocolo SEFAZ.',
        ],
        'nfe_saida_id': nfe_saida.pk,
        'numero': nfe_saida.numero,
        'status': nfe_saida.status,
        'content_type': 'application/pdf',
        'filename': f'danfe-bfr-poc-nfe-{nfe_saida.pk}.pdf',
    }
    return pdf, meta
