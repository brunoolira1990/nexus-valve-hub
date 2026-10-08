"""Parser de retorno SEFAZ (autorização NF-e) — lote vs protocolo NF-e."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from apps.fiscal.models import NFeSaida

NS_NFE = 'http://www.portalfiscal.inf.br/nfe'

CSTAT_AUTORIZADO = frozenset({'100', '150'})
CSTAT_LOTE_RECEBIDO = '103'
CSTAT_LOTE_PROCESSADO = '104'
CSTAT_LOTE_EM_PROCESSAMENTO = '105'


@dataclass(frozen=True)
class DadosLoteSefaz:
    c_stat: str = ''
    x_motivo: str = ''
    recibo: str = ''
    tp_amb: str = ''
    versao: str = ''
    dh_recbto: str = ''


@dataclass(frozen=True)
class DadosProtocoloNFe:
    c_stat: str = ''
    x_motivo: str = ''
    protocolo: str = ''
    ch_nfe: str = ''
    dh_recbto: str = ''
    dig_val: str = ''


@dataclass(frozen=True)
class ResultadoAutorizacaoSefaz:
    """Resultado interpretado — status final baseado em infProt, não no cStat do lote."""

    status_final: str
    autorizado: bool
    rejeitado: bool
    lote: DadosLoteSefaz
    nfe: DadosProtocoloNFe | None
    xml_retorno_lote: str
    xml_protocolo: str
    xml_autorizado: str
    recibo: str = ''

    # Campos legados (NF-e / compatibilidade)
    @property
    def c_stat(self) -> str:
        if self.nfe and self.nfe.c_stat:
            return self.nfe.c_stat
        return self.lote.c_stat

    @property
    def x_motivo(self) -> str:
        if self.nfe and self.nfe.x_motivo:
            return self.nfe.x_motivo
        return self.lote.x_motivo

    @property
    def protocolo(self) -> str:
        return (self.nfe.protocolo if self.nfe else '') or ''

    @property
    def xml_retorno(self) -> str:
        return self.xml_retorno_lote


def _texto_xml(val: Any) -> str:
    if val is None:
        return ''
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='replace')
    if hasattr(val, 'text'):
        return _texto_xml(getattr(val, 'text', None))
    return str(val)


def _local(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _find_element(root: Any, local_name: str) -> Any | None:
    if root is None:
        return None
    for el in root.iter():
        if _local(el.tag) == local_name:
            return el
    return None


def _direct_child_text(parent: Any, local_name: str) -> str:
    if parent is None:
        return ''
    for el in parent:
        if _local(el.tag) == local_name and el.text is not None:
            return (el.text or '').strip()
    return ''


def _find_first_text_in(parent: Any, local_name: str) -> str:
    if parent is None:
        return ''
    for el in parent.iter():
        if _local(el.tag) == local_name and el.text is not None:
            return (el.text or '').strip()
    return ''


def _parse_xml_root(payload: Any) -> Any | None:
    from lxml import etree

    if payload is None:
        return None
    if hasattr(payload, 'tag'):
        return payload
    xml_str = _texto_xml(payload).strip()
    if not xml_str:
        return None
    try:
        return etree.fromstring(xml_str.encode('utf-8'))
    except Exception:
        return None


def _extrair_recibo_lote(ret_root: Any) -> str:
    nrec = _direct_child_text(ret_root, 'nRec')
    if nrec:
        return nrec
    inf_rec = _find_element(ret_root, 'infRec')
    if inf_rec is not None:
        return _direct_child_text(inf_rec, 'nRec')
    return ''


def _extrair_lote(ret_root: Any) -> DadosLoteSefaz:
    return DadosLoteSefaz(
        c_stat=_direct_child_text(ret_root, 'cStat'),
        x_motivo=_direct_child_text(ret_root, 'xMotivo'),
        recibo=_extrair_recibo_lote(ret_root),
        tp_amb=_direct_child_text(ret_root, 'tpAmb'),
        versao=ret_root.get('versao', '') if ret_root is not None and hasattr(ret_root, 'get') else '',
        dh_recbto=_direct_child_text(ret_root, 'dhRecbto'),
    )


def _extrair_protocolo_nfe(ret_root: Any) -> DadosProtocoloNFe | None:
    prot_nfe = _find_element(ret_root, 'protNFe')
    if prot_nfe is None:
        return None
    inf_prot = _find_element(prot_nfe, 'infProt')
    if inf_prot is None:
        return None
    c_stat = _direct_child_text(inf_prot, 'cStat') or _find_first_text_in(inf_prot, 'cStat')
    if not c_stat:
        return None
    return DadosProtocoloNFe(
        c_stat=c_stat,
        x_motivo=_direct_child_text(inf_prot, 'xMotivo') or _find_first_text_in(inf_prot, 'xMotivo'),
        protocolo=_direct_child_text(inf_prot, 'nProt') or _find_first_text_in(inf_prot, 'nProt'),
        ch_nfe=_direct_child_text(inf_prot, 'chNFe') or _find_first_text_in(inf_prot, 'chNFe'),
        dh_recbto=_direct_child_text(inf_prot, 'dhRecbto') or _find_first_text_in(inf_prot, 'dhRecbto'),
        dig_val=_direct_child_text(inf_prot, 'digVal') or _find_first_text_in(inf_prot, 'digVal'),
    )


def _localizar_retorno_envio(root: Any) -> Any | None:
    for tag in ('retEnviNFe', 'retConsReciNFe', 'nfeProc'):
        el = _find_element(root, tag)
        if el is not None:
            return el
    return root


def _serializar_elemento(el: Any) -> str:
    from lxml import etree

    if el is None:
        return ''
    body = etree.tostring(el, encoding='unicode', xml_declaration=False)
    if not body.strip().startswith('<?xml'):
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + body
    return body


def _classificar_status(lote: DadosLoteSefaz, nfe: DadosProtocoloNFe | None) -> tuple[str, bool, bool]:
    c_lote = (lote.c_stat or '').strip()

    if nfe and nfe.c_stat:
        if nfe.c_stat in CSTAT_AUTORIZADO:
            return NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO, True, False
        return NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO, False, True

    if c_lote == CSTAT_LOTE_RECEBIDO:
        return 'AGUARDANDO_PROCESSAMENTO', False, False
    if c_lote == CSTAT_LOTE_EM_PROCESSAMENTO:
        return 'AGUARDANDO_PROCESSAMENTO', False, False
    if c_lote == CSTAT_LOTE_PROCESSADO:
        return 'LOTE_PROCESSADO_SEM_PROTOCOLO', False, False
    if c_lote:
        return NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO, False, True

    return 'ERRO_RETORNO_SEFAZ', False, False


def _montar_proc_nfe_de_assinado(xml_assinado: str, prot_nfe_el: Any) -> str:
    from lxml import etree

    root = etree.fromstring(xml_assinado.encode('utf-8'))
    nfe_el = root
    if _local(root.tag) != 'NFe':
        for child in root:
            if _local(child.tag) == 'NFe':
                nfe_el = child
                break
    return montar_proc_nfe_xml(nfe_el, prot_nfe_el)


def processar_retorno_autorizacao_nfe(
    xml_retorno: str,
    nfe_saida: NFeSaida | None = None,
    *,
    xml_assinado: str = '',
    codigo_pynfe: int | None = None,
) -> ResultadoAutorizacaoSefaz:
    """
    Interpreta XML de retorno SEFAZ (SOAP, retEnviNFe, nfeProc).

    Regra central: cStat do lote (ex.: 104) ≠ status final da NF-e.
    Status final vem de infProt.cStat quando protNFe estiver presente.
    """
    root = _parse_xml_root(xml_retorno)
    xml_bruto = _texto_xml(xml_retorno)

    if root is None:
        return ResultadoAutorizacaoSefaz(
            status_final='ERRO_RETORNO_SEFAZ',
            autorizado=False,
            rejeitado=False,
            lote=DadosLoteSefaz(),
            nfe=None,
            xml_retorno_lote=xml_bruto,
            xml_protocolo='',
            xml_autorizado='',
        )

    # nfeProc direto (PyNFe sucesso síncrono)
    if _local(root.tag) == 'nfeProc' or _find_element(root, 'nfeProc') is not None:
        nfe_proc = root if _local(root.tag) == 'nfeProc' else _find_element(root, 'nfeProc')
        nfe = _extrair_protocolo_nfe(nfe_proc)
        lote = DadosLoteSefaz(c_stat=nfe.c_stat if nfe else '', x_motivo=nfe.x_motivo if nfe else '')
        status, autorizado, rejeitado = _classificar_status(lote, nfe)
        xml_aut = _serializar_elemento(nfe_proc) if autorizado else ''
        prot_el = _find_element(nfe_proc, 'protNFe')
        return ResultadoAutorizacaoSefaz(
            status_final=status,
            autorizado=autorizado,
            rejeitado=rejeitado,
            lote=lote,
            nfe=nfe,
            xml_retorno_lote=xml_bruto,
            xml_protocolo=_serializar_elemento(prot_el) if prot_el is not None else '',
            xml_autorizado=xml_aut,
        )

    ret_root = _localizar_retorno_envio(root)
    lote = _extrair_lote(ret_root)
    nfe = _extrair_protocolo_nfe(ret_root)
    status, autorizado, rejeitado = _classificar_status(lote, nfe)

    prot_el = _find_element(ret_root, 'protNFe')
    xml_protocolo = _serializar_elemento(prot_el) if prot_el is not None else ''
    xml_autorizado = ''

    if autorizado and prot_el is not None and xml_assinado:
        try:
            xml_autorizado = _montar_proc_nfe_de_assinado(xml_assinado, prot_el)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                'Falha ao montar procNFe na autorização — será remontado no DANFE: %s',
                exc,
            )
            xml_autorizado = ''
    elif autorizado and _local(root.tag) == 'nfeProc':
        xml_autorizado = _serializar_elemento(root)

    recibo = lote.recibo
    if codigo_pynfe == 0 and not recibo and nfe and nfe.protocolo:
        recibo = nfe.protocolo

    return ResultadoAutorizacaoSefaz(
        status_final=status,
        autorizado=autorizado,
        rejeitado=rejeitado,
        lote=lote,
        nfe=nfe,
        xml_retorno_lote=xml_bruto,
        xml_protocolo=xml_protocolo,
        xml_autorizado=xml_autorizado,
        recibo=recibo,
    )


def parse_resposta_autorizacao_pynfe(
    codigo_retorno: int,
    payload: Any,
    *,
    xml_enviado: str = '',
) -> ResultadoAutorizacaoSefaz:
    """Adaptador PyNFe → processar_retorno_autorizacao_nfe."""
    if codigo_retorno == 0 and payload is not None:
        if hasattr(payload, 'tag'):
            xml_ret = _serializar_elemento(payload)
        else:
            xml_ret = _texto_xml(payload)
        return processar_retorno_autorizacao_nfe(
            xml_ret,
            xml_assinado=xml_enviado,
            codigo_pynfe=codigo_retorno,
        )

    xml_ret = ''
    if isinstance(payload, tuple):
        parts = list(payload)
        xml_ret = _texto_xml(parts[0] if parts else '')
    else:
        xml_ret = _texto_xml(getattr(payload, 'text', None) or payload)

    if not xml_ret.strip() and xml_enviado:
        xml_ret = xml_enviado

    return processar_retorno_autorizacao_nfe(
        xml_ret,
        xml_assinado=xml_enviado,
        codigo_pynfe=codigo_retorno,
    )


def montar_proc_nfe_xml(nfe_element: Any, prot_element: Any) -> str:
    from lxml import etree

    root = etree.Element('{http://www.portalfiscal.inf.br/nfe}nfeProc', nsmap={None: NS_NFE})
    root.set('versao', '4.00')
    root.append(nfe_element)
    root.append(prot_element)
    body = etree.tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def resultado_autorizacao_mock(
    *,
    autorizado: bool = False,
    c_stat: str = '',
    x_motivo: str = '',
    protocolo: str = '',
    xml_retorno: str = '',
    xml_autorizado: str = '',
    recibo: str = '',
    cstat_lote: str = '104',
    xmotivo_lote: str = 'Lote processado',
) -> ResultadoAutorizacaoSefaz:
    """Factory para testes — mantém compatibilidade com mocks antigos."""
    nfe = None
    if c_stat:
        nfe = DadosProtocoloNFe(c_stat=c_stat, x_motivo=x_motivo, protocolo=protocolo)
    lote = DadosLoteSefaz(c_stat=cstat_lote, x_motivo=xmotivo_lote, recibo=recibo)
    status, auth, rej = _classificar_status(lote, nfe)
    if autorizado:
        status = NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
        auth, rej = True, False
    return ResultadoAutorizacaoSefaz(
        status_final=status,
        autorizado=auth,
        rejeitado=rej,
        lote=lote,
        nfe=nfe,
        xml_retorno_lote=xml_retorno,
        xml_protocolo='',
        xml_autorizado=xml_autorizado if autorizado else '',
        recibo=recibo,
    )
