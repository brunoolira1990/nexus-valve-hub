"""DANFE via BrazilFiscalReport — XML NF-e 4.00 preliminar ou autorizado (sem SEFAZ)."""

from __future__ import annotations

import logging
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from apps.fiscal.nfe_integracao.danfe_empresa_logo import get_emitente_logo_nfe_saida
from apps.fiscal.nfe_integracao.danfe_marca_dagua import (
    resolver_marca_dagua_danfe,
    usar_watermark_cancelada_bfr,
)

logger = logging.getLogger(__name__)

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
<infAdic><infCpl>POC BrazilFiscalReport - conferencia</infCpl></infAdic>
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


def _tp_amb_do_xml(xml: str) -> str:
    m = re.search(r'<[\w:]*tpAmb>([12])</[\w:]*tpAmb>', xml)
    return m.group(1) if m else '2'


def _xml_tem_protocolo(xml: str) -> bool:
    return bool(re.search(r'<[\w:]*protNFe\b', xml, flags=re.IGNORECASE))


class DanfeNexus:
    """
    Subclasse da BFR com marca d'água customizada por status fiscal Nexus.

    A biblioteca 0.7.4 só oferece watermark_cancelled (texto fixo «CANCELADA…») ou
    «SEM VALOR FISCAL» automático — insuficiente para conferência.
    """

    @staticmethod
    def _criar_classe():
        from brazilfiscalreport.danfe.danfe import Danfe

        from apps.fiscal.nfe_integracao.danfe_bfr_billing import draw_billing_nexus
        from apps.fiscal.nfe_integracao.danfe_bfr_emit import draw_header_emit_nexus
        from apps.fiscal.nfe_integracao.danfe_bfr_taxes import draw_taxes_nexus

        class _DanfeNexus(Danfe):
            def __init__(
                self,
                xml,
                config=None,
                *,
                marca_dagua_custom: str | None = None,
                marca_dagua_cancelada_bfr: bool = False,
                emit_extras: dict | None = None,
            ):
                self._marca_dagua_custom = (marca_dagua_custom or '').strip() or None
                self._marca_dagua_cancelada_bfr = marca_dagua_cancelada_bfr
                self._nexus_emit_extras = emit_extras or {}
                super().__init__(xml, config)
                if marca_dagua_cancelada_bfr:
                    self.watermark_cancelled = True

            def _split_additional_data_in_products(
                self,
                available_height_product_table,
                products_for_current_page,
                addit_data_next_pages,
            ):
                """
                BFR reparte infCpl longo na tabela de produtos quando não cabe no rodapé.
                Nexus: não usar área de produtos; preservar overflow para páginas de
                continuação do bloco Dados Adicionais.
                """
                return None, addit_data_next_pages

            def _get_additional_data_content(self):
                from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
                    inf_cpl_prioriza_pedido_para_danfe,
                )

                texto = super()._get_additional_data_content()
                return inf_cpl_prioriza_pedido_para_danfe(texto)

            def _draw_watermark_multiline(self, texto: str, *, font_size: int = 22) -> None:
                linhas = [ln.strip() for ln in texto.split('\n') if ln.strip()]
                if not linhas:
                    return
                self.set_font(self.default_font, 'B', font_size)
                self.set_text_color(r=200, g=170, b=170)
                line_h = font_size * 0.42
                page_width = self.w
                page_height = self.h
                block_h = line_h * len(linhas)
                # Centralizar na área de produtos (~MOC y=17–24 cm), não na página inteira
                pivot_x = page_width / 2
                pivot_y = page_height * 0.68
                y_center = pivot_y
                with self.rotation(55, pivot_x, pivot_y):
                    y0 = y_center - block_h / 2
                    for i, ln in enumerate(linhas):
                        w = self.get_string_width(ln)
                        x = (page_width - w) / 2
                        self.text(x, y0 + i * line_h, ln)
                self.set_text_color(r=0, g=0, b=0)

            def _draw_void_watermark(self):
                if self._marca_dagua_custom:
                    fs = 20 if self._marca_dagua_custom.count('\n') >= 2 else 24
                    self._draw_watermark_multiline(self._marca_dagua_custom, font_size=fs)
                    return
                if self._marca_dagua_cancelada_bfr:
                    super()._draw_void_watermark()
                    return
                super()._draw_void_watermark()

            _draw_header = draw_header_emit_nexus
            _draw_billing = draw_billing_nexus
            _draw_taxes = draw_taxes_nexus

        return _DanfeNexus

    @classmethod
    def render(
        cls,
        xml: str,
        config,
        *,
        marca_dagua: str | None,
        cancelada_bfr: bool,
        emit_extras: dict | None = None,
    ) -> bytes:
        DanfeCls = cls._criar_classe()
        danfe = DanfeCls(
            xml=xml,
            config=config,
            marca_dagua_custom=marca_dagua,
            marca_dagua_cancelada_bfr=cancelada_bfr,
            emit_extras=emit_extras,
        )
        buffer = BytesIO()
        danfe.output(buffer)
        return buffer.getvalue()


def sanitizar_xml_para_bfr(xml: str) -> str:
    """Remove comentários/declarações duplicadas e normaliza texto para fontes Times da BFR."""
    from apps.fiscal.nfe_cbenef_sp import ocultar_sem_cbenef_para_danfe

    if not (xml or '').strip():
        raise DanfeBfrError('XML vazio.')

    texto = str(xml)
    texto = re.sub(r'<!--.*?-->', '', texto, flags=re.DOTALL)
    texto = re.sub(r'<\?xml[^?]*\?>\s*', '', texto, flags=re.IGNORECASE)
    texto = texto.replace('\u2014', '-').replace('\u2013', '-')
    texto = ocultar_sem_cbenef_para_danfe(texto)
    texto = texto.strip()
    if not texto.startswith('<'):
        raise DanfeBfrError('XML inválido: conteúdo não parece um documento NF-e.')
    return texto


def _montar_config_danfe(
    DanfeConfig,
    *,
    nfe_saida=None,
    xml: str | None = None,
    logo_path: str | None = None,
):
    """
    Configura BFR: logo emitente, PIS/COFINS e infCpl com paginação no bloco Dados Adicionais.

    Overflow de Informações Complementares segue para páginas de continuação (não para produtos).
    """
    from brazilfiscalreport.danfe.config import FontSize

    if logo_path is None and nfe_saida is not None:
        logo_path = get_emitente_logo_nfe_saida(nfe_saida)
    if logo_path and not os.path.isfile(logo_path):
        logger.warning('Logo emitente inexistente ou inacessível: ignorando.')
        logo_path = None

    cancelada = False
    if nfe_saida is not None:
        cancelada = usar_watermark_cancelada_bfr(nfe_saida)

    return DanfeConfig(
        logo=logo_path,
        display_pis_cofins=True,
        watermark_cancelled=cancelada,
        infcpl_semicolon_newline=False,
        font_size=FontSize.SMALL,
    )


def gerar_danfe_bfr_de_xml_string(
    xml_string: str,
    *,
    nfe_saida=None,
    ambiente: str | None = None,
    tem_protocolo: bool | None = None,
) -> bytes:
    """Gera PDF DANFE a partir de XML NF-e (string). Não altera NF-e nem transmite SEFAZ."""
    _, DanfeConfig = _importar_danfe()
    xml_limpo = sanitizar_xml_para_bfr(xml_string)

    if tem_protocolo is None:
        tem_protocolo = _xml_tem_protocolo(xml_limpo)
    if ambiente is None:
        ambiente = _tp_amb_do_xml(xml_limpo)

    marca: str | None = None
    cancelada_bfr = False
    if nfe_saida is not None:
        marca = resolver_marca_dagua_danfe(
            nfe_saida,
            ambiente,
            tem_protocolo=bool(tem_protocolo),
        )
        cancelada_bfr = usar_watermark_cancelada_bfr(nfe_saida)
    elif not tem_protocolo and ambiente != '1':
        marca = 'DANFE DE CONFERÊNCIA\nSEM VALOR FISCAL'

    config = _montar_config_danfe(DanfeConfig, nfe_saida=nfe_saida, xml=xml_limpo)

    emit_extras = None
    if nfe_saida is not None:
        from apps.fiscal.nfe_integracao.danfe_bfr_emit import montar_emit_extras_nfe_saida

        emit_extras = montar_emit_extras_nfe_saida(nfe_saida)

    try:
        pdf = DanfeNexus.render(
            xml_limpo,
            config,
            marca_dagua=marca,
            cancelada_bfr=cancelada_bfr,
            emit_extras=emit_extras,
        )
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
    nfe_saida=None,
    ambiente: str | None = None,
    tem_protocolo: bool | None = None,
) -> bytes:
    try:
        xml_string = xml_bytes.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise DanfeBfrError('XML deve estar em UTF-8.') from exc
    return gerar_danfe_bfr_de_xml_string(
        xml_string,
        nfe_saida=nfe_saida,
        ambiente=ambiente,
        tem_protocolo=tem_protocolo,
    )


def gerar_danfe_bfr_de_xml_string_legacy(
    xml_string: str,
    *,
    ajustes_poc: bool = False,
    nfe_saida_id: int | None = None,
) -> bytes:
    """Compat POC antiga — preferir XML preliminar nfelib."""
    xml = xml_string
    if ajustes_poc:
        if nfe_saida_id is not None:
            xml = re.sub(r'<nNF>[^<]+</nNF>', f'<nNF>{int(nfe_saida_id)}</nNF>', xml, count=1)
        if '<tpAmb>' not in xml and '</ide>' in xml:
            xml = xml.replace('</ide>', '<tpAmb>2</tpAmb></ide>', 1)
    return gerar_danfe_bfr_de_xml_string(xml)


def gerar_danfe_bfr_debug_file(
    xml: str | bytes,
    output_path: str | Path,
    *,
    nfe_saida=None,
) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(xml, bytes):
        pdf = gerar_danfe_bfr_de_xml_bytes(xml, nfe_saida=nfe_saida)
    else:
        pdf = gerar_danfe_bfr_de_xml_string(xml, nfe_saida=nfe_saida)
    path.write_bytes(pdf)
    return str(path.resolve())


def brazil_fiscal_report_disponivel() -> bool:
    try:
        _importar_danfe()
        return True
    except DanfeBfrIndisponivelError:
        return False


def gerar_danfe_bfr_nfe_preliminar(nfe_saida) -> tuple[bytes, dict[str, Any]]:
    """
    Gera DANFE Conferência via BrazilFiscalReport a partir do XML preliminar nfelib.

    Não transmite SEFAZ, não altera status fiscal, não movimenta estoque/financeiro.
    """
    from apps.fiscal.nfe_integracao.nfe_xml_preliminar import (
        AVISO_DANFE_PRELIMINAR,
        NFeXmlPreliminarError,
        gerar_xml_nfe_preliminar,
    )

    if not brazil_fiscal_report_disponivel():
        raise DanfeBfrIndisponivelError('BrazilFiscalReport indisponível neste ambiente.')

    try:
        xml_bytes = gerar_xml_nfe_preliminar(nfe_saida)
    except NFeXmlPreliminarError as exc:
        raise DanfeBfrError(str(exc)) from exc

    xml = xml_bytes.decode('utf-8')
    if _xml_tem_protocolo(xml):
        raise DanfeBfrError('XML preliminar não deve conter protocolo SEFAZ.')

    tp_amb = _tp_amb_do_xml(xml)
    pdf = gerar_danfe_bfr_de_xml_string(
        xml,
        nfe_saida=nfe_saida,
        ambiente=tp_amb,
        tem_protocolo=False,
    )

    m_chave = re.search(r'Id="NFe([0-9]{44})"', xml)
    m_nnf = re.search(r'<[\w:]*nNF>([0-9]+)</[\w:]*nNF>', xml)
    chave = m_chave.group(1) if m_chave else ''
    nnf = m_nnf.group(1) if m_nnf else ''
    marca = resolver_marca_dagua_danfe(nfe_saida, tp_amb, tem_protocolo=False)
    ambiente_label = 'producao' if tp_amb == '1' else 'homologacao'

    meta = {
        'preview': True,
        'conferencia': True,
        'preliminar': True,
        'bloqueado': False,
        'render_engine': 'brazil_fiscal_report',
        'danfe_origem': 'xml_preliminar_nfelib',
        'danfe_renderer_label': 'DANFE Conferência via XML preliminar',
        'xml_format': 'nfelib_4.00_preliminar',
        'chave_acesso_preliminar': chave,
        'numero_fiscal_preliminar': nnf,
        'numero_interno_ref': nfe_saida.numero,
        'nfe_saida_id': nfe_saida.pk,
        'numero': nfe_saida.numero,
        'status': nfe_saida.status,
        'ambiente_emissao': ambiente_label,
        'tp_amb': tp_amb,
        'content_type': 'application/pdf',
        'filename': f'danfe-conferencia-bfr-nfe-{nfe_saida.pk}.pdf',
        'marca_dagua': marca,
        'mensagens': [
            AVISO_DANFE_PRELIMINAR,
            'DANFE gerado por BrazilFiscalReport (XML preliminar).',
            'Não transmitir. Sem protocolo SEFAZ.',
        ],
    }
    return pdf, meta


def gerar_danfe_bfr_producao_autorizada(nfe_saida) -> tuple[bytes, dict[str, Any]]:
    """DANFE via XML autorizado (procNFe) — produção com protocolo SEFAZ."""
    if not brazil_fiscal_report_disponivel():
        raise DanfeBfrIndisponivelError('BrazilFiscalReport indisponível neste ambiente.')

    from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe

    xml = resolver_xml_autorizado_danfe(nfe_saida)

    if not _xml_tem_protocolo(xml):
        raise DanfeBfrError('XML autorizado sem protocolo SEFAZ — DANFE indisponível.')

    tp_amb = _tp_amb_do_xml(xml)
    if tp_amb != '1':
        raise DanfeBfrError('XML autorizado de produção deve conter tpAmb=1.')

    pdf = gerar_danfe_bfr_de_xml_string(
        xml,
        nfe_saida=nfe_saida,
        ambiente='1',
        tem_protocolo=True,
    )
    marca = resolver_marca_dagua_danfe(nfe_saida, '1', tem_protocolo=True)
    meta = {
        'preview': False,
        'conferencia': False,
        'producao_autorizada': True,
        'bloqueado': False,
        'render_engine': 'brazil_fiscal_report',
        'danfe_origem': 'xml_autorizado_procNFe',
        'danfe_renderer_label': 'DANFE Produção (autorizada SEFAZ)',
        'protocolo_autorizacao': nfe_saida.protocolo_autorizacao,
        'chave_acesso': nfe_saida.chave_acesso,
        'nfe_saida_id': nfe_saida.pk,
        'numero': nfe_saida.numero_nfe or nfe_saida.numero,
        'serie': nfe_saida.serie_nfe,
        'ambiente_emissao': 'producao',
        'tp_amb': '1',
        'content_type': 'application/pdf',
        'filename': f'danfe-producao-{nfe_saida.pk}.pdf',
        'marca_dagua': marca,
        'mensagens': ['DANFE produção — documento com validade fiscal.', 'Protocolo SEFAZ real.'],
    }
    return pdf, meta


def gerar_danfe_bfr_homologacao_autorizada(nfe_saida) -> tuple[bytes, dict[str, Any]]:
    """DANFE via XML autorizado (procNFe) — homologação com protocolo real SEFAZ."""
    if not brazil_fiscal_report_disponivel():
        raise DanfeBfrIndisponivelError('BrazilFiscalReport indisponível neste ambiente.')

    from apps.fiscal.nfe_integracao.danfe_xml_autorizado import resolver_xml_autorizado_danfe

    xml = resolver_xml_autorizado_danfe(nfe_saida)

    if not _xml_tem_protocolo(xml):
        raise DanfeBfrError('XML autorizado sem protocolo SEFAZ — DANFE indisponível.')

    pdf = gerar_danfe_bfr_de_xml_string(
        xml,
        nfe_saida=nfe_saida,
        ambiente='2',
        tem_protocolo=True,
    )
    marca = resolver_marca_dagua_danfe(nfe_saida, '2', tem_protocolo=True)
    meta = {
        'preview': False,
        'conferencia': False,
        'homologacao_autorizada': True,
        'bloqueado': False,
        'render_engine': 'brazil_fiscal_report',
        'danfe_origem': 'xml_autorizado_procNFe',
        'danfe_renderer_label': 'DANFE Homologação (autorizada SEFAZ)',
        'protocolo_autorizacao': nfe_saida.protocolo_autorizacao,
        'chave_acesso': nfe_saida.chave_acesso,
        'nfe_saida_id': nfe_saida.pk,
        'content_type': 'application/pdf',
        'filename': f'danfe-homologacao-{nfe_saida.pk}.pdf',
        'marca_dagua': marca,
        'mensagens': ['DANFE homologação — SEM VALOR FISCAL.', 'Protocolo SEFAZ real.'],
    }
    return pdf, meta


def gerar_danfe_bfr_autorizada(nfe_saida) -> tuple[bytes, dict[str, Any]]:
    """DANFE final via XML autorizado — produção ou homologação conforme status da NF-e."""
    from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao, nf_autorizada_producao

    if nf_autorizada_producao(nfe_saida):
        return gerar_danfe_bfr_producao_autorizada(nfe_saida)
    if nf_autorizada_homologacao(nfe_saida):
        return gerar_danfe_bfr_homologacao_autorizada(nfe_saida)
    raise DanfeBfrError('DANFE autorizado disponível apenas após autorização SEFAZ.')


def gerar_danfe_bfr_de_nfe_saida_preview(nfe_saida) -> tuple[bytes, dict[str, Any]]:
    """Fluxo legado POC — delega para XML preliminar quando possível."""
    try:
        return gerar_danfe_bfr_nfe_preliminar(nfe_saida)
    except (DanfeBfrError, DanfeBfrIndisponivelError):
        from apps.fiscal.nfe_saida_preview import gerar_preview_xml_nfe_saida

        preview = gerar_preview_xml_nfe_saida(nfe_saida)
        if preview.get('bloqueado'):
            return b'', {
                'bloqueado': True,
                'mensagens': preview.get('mensagens') or [],
                'render_engine': 'brazil_fiscal_report_legacy',
            }
        pdf = gerar_danfe_bfr_de_xml_string_legacy(
            preview.get('xml') or '',
            ajustes_poc=True,
            nfe_saida_id=nfe_saida.pk,
        )
        return pdf, {
            'preview': True,
            'conferencia': True,
            'bloqueado': False,
            'render_engine': 'brazil_fiscal_report_legacy',
            'danfe_origem': 'xml_previa_simplificada',
            'danfe_renderer_label': 'DANFE Conferência (XML prévia legado)',
            'nfe_saida_id': nfe_saida.pk,
            'content_type': 'application/pdf',
            'filename': f'danfe-bfr-legacy-nfe-{nfe_saida.pk}.pdf',
        }
