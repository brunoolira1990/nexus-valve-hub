"""DANFE (preview e autorizado) para NF-e entrada própria emitida."""

from __future__ import annotations

import re
from typing import Any

from apps.fiscal.models import NFeEntrada

MSG_DANFE_PREVIEW = 'DANFE de conferência da entrada própria — sem valor fiscal / sem protocolo SEFAZ.'
MSG_DANFE_AUTORIZADO = 'DANFE gerado a partir do XML autorizado na SEFAZ.'


class NFeEntradaDanfeError(ValueError):
    pass


def _autorizada(nf: NFeEntrada) -> bool:
    st = (nf.status_emissao_sefaz or '').strip().upper()
    return st in (
        NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
    )


def _tp_amb(nf: NFeEntrada) -> str:
    if (nf.ambiente_emissao or '').strip().lower() == NFeEntrada.AmbienteEmissao.PRODUCAO:
        return '1'
    return '2'


def gerar_preview_danfe_nfe_entrada(nf: NFeEntrada) -> tuple[bytes, dict[str, Any]]:
    """
    DANFE de conferência a partir do XML oficial preliminar (tpNF=0).
    Exige numeração reservada (mesmo requisito do preview XML).
    """
    from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
        DanfeBfrError,
        DanfeBfrIndisponivelError,
        brazil_fiscal_report_disponivel,
        gerar_danfe_bfr_de_xml_string,
    )
    from apps.fiscal.nfe_entrada_emissao.xml_oficial import gerar_preview_xml_oficial_nfe_entrada

    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        raise NFeEntradaDanfeError('DANFE de entrada própria disponível apenas para ENTRADA_PROPRIA_EMITIDA.')

    if _autorizada(nf) and (nf.xml_autorizado or '').strip():
        return gerar_danfe_autorizado_nfe_entrada(nf)

    if not brazil_fiscal_report_disponivel():
        raise NFeEntradaDanfeError('BrazilFiscalReport indisponível neste ambiente.')

    preview = gerar_preview_xml_oficial_nfe_entrada(nf)
    if preview.get('bloqueado') or not preview.get('ok'):
        msgs = preview.get('pendencias') or []
        detalhe = preview.get('mensagem') or (
            msgs[0].get('mensagem') if msgs and isinstance(msgs[0], dict) else None
        )
        raise NFeEntradaDanfeError(
            detalhe
            or 'Não foi possível gerar o XML preliminar para o DANFE. Reserve a numeração e corrija pendências.',
        )

    xml = (preview.get('xml') or '').strip()
    if not xml:
        raise NFeEntradaDanfeError('XML preliminar vazio — não foi possível gerar o DANFE.')

    tp_amb = str(preview.get('tp_amb') or _tp_amb(nf))
    try:
        pdf = gerar_danfe_bfr_de_xml_string(xml, ambiente=tp_amb, tem_protocolo=False)
    except (DanfeBfrError, DanfeBfrIndisponivelError) as exc:
        raise NFeEntradaDanfeError(str(exc)) from exc

    m_chave = re.search(r'Id="NFe([0-9]{44})"', xml)
    chave = m_chave.group(1) if m_chave else (nf.chave_acesso or '')
    meta: dict[str, Any] = {
        'preview': True,
        'conferencia': True,
        'bloqueado': False,
        'render_engine': 'brazil_fiscal_report',
        'danfe_origem': 'xml_oficial_entrada_preliminar',
        'danfe_renderer_label': 'DANFE Conferência — entrada própria',
        'nf_entrada_id': nf.pk,
        'numero': nf.numero,
        'chave_acesso_preliminar': chave,
        'serie_nfe': nf.serie_nfe,
        'numero_nfe': nf.numero_nfe,
        'tp_amb': tp_amb,
        'content_type': 'application/pdf',
        'filename': f'danfe-conferencia-entrada-{nf.pk}.pdf',
        'mensagens': [MSG_DANFE_PREVIEW],
    }
    return pdf, meta


def gerar_danfe_autorizado_nfe_entrada(nf: NFeEntrada) -> tuple[bytes, dict[str, Any]]:
    """DANFE final a partir do XML autorizado (procNFe)."""
    from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
        DanfeBfrError,
        DanfeBfrIndisponivelError,
        brazil_fiscal_report_disponivel,
        gerar_danfe_bfr_de_xml_string,
    )

    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        raise NFeEntradaDanfeError('DANFE autorizado disponível apenas para ENTRADA_PROPRIA_EMITIDA.')

    if not _autorizada(nf):
        raise NFeEntradaDanfeError('DANFE autorizado disponível apenas após autorização na SEFAZ.')

    xml = (nf.xml_autorizado or '').strip()
    if not xml:
        raise NFeEntradaDanfeError('XML autorizado não encontrado nesta NF-e de entrada.')

    if not brazil_fiscal_report_disponivel():
        raise NFeEntradaDanfeError('BrazilFiscalReport indisponível neste ambiente.')

    tp_amb = _tp_amb(nf)
    try:
        pdf = gerar_danfe_bfr_de_xml_string(xml, ambiente=tp_amb, tem_protocolo=True)
    except (DanfeBfrError, DanfeBfrIndisponivelError) as exc:
        raise NFeEntradaDanfeError(str(exc)) from exc

    chave = (nf.chave_acesso or '').strip() or 'sem-chave'
    meta: dict[str, Any] = {
        'preview': False,
        'autorizado': True,
        'bloqueado': False,
        'render_engine': 'brazil_fiscal_report',
        'danfe_origem': 'xml_autorizado_entrada',
        'danfe_renderer_label': 'DANFE autorizado — entrada própria',
        'nf_entrada_id': nf.pk,
        'numero': nf.numero,
        'chave_acesso': chave,
        'serie_nfe': nf.serie_nfe,
        'numero_nfe': nf.numero_nfe,
        'tp_amb': tp_amb,
        'content_type': 'application/pdf',
        'filename': f'danfe-autorizado-entrada-{chave}.pdf',
        'mensagens': [MSG_DANFE_AUTORIZADO],
    }
    return pdf, meta
