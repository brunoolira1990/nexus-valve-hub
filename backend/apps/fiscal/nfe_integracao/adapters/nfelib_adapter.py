"""Adaptador nfelib — leitura/validação XML NF-e 4.00."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lxml import etree

from apps.fiscal.nfe_integracao.adapters.exceptions import NFeIntegracaoError


@dataclass
class RetornoStatusServicoParsed:
    tp_amb: str | None = None
    ver_aplic: str | None = None
    c_stat: str | None = None
    x_motivo: str | None = None
    c_uf: str | None = None
    dh_recbto: str | None = None
    t_med: str | None = None
    versao: str | None = None
    servico_operacional: bool = False


def _parse_via_lxml(xml_text: str) -> RetornoStatusServicoParsed:
    """Fallback: extrai campos do retConsStatServ via lxml."""
    try:
        root = etree.fromstring(xml_text.encode('utf-8'))
    except Exception as exc:
        raise NFeIntegracaoError(f'XML de retorno inválido: {exc}') from exc

    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    def _txt(tag: str) -> str | None:
        el = root.find(f'nfe:{tag}', ns) or root.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return None

    c_stat = _txt('cStat')
    return RetornoStatusServicoParsed(
        tp_amb=_txt('tpAmb'),
        ver_aplic=_txt('verAplic'),
        c_stat=c_stat,
        x_motivo=_txt('xMotivo'),
        c_uf=_txt('cUF'),
        dh_recbto=_txt('dhRecbto'),
        t_med=_txt('tMed'),
        versao=root.get('versao'),
        servico_operacional=c_stat in ('107', '108'),
    )


def parse_ret_cons_stat_serv(xml_text: str) -> RetornoStatusServicoParsed:
    """Interpreta XML retConsStatServ (NF-e 4.00) com nfelib + fallback lxml."""
    if not (xml_text or '').strip():
        raise NFeIntegracaoError('Resposta XML vazia da SEFAZ.')

    try:
        from xsdata.formats.dataclass.parsers import XmlParser
        from nfelib.nfe.bindings.v4_0.ret_cons_stat_serv_v4_00 import RetConsStatServ

        obj: RetConsStatServ = XmlParser().from_string(xml_text, RetConsStatServ)
        c_stat = str(getattr(obj, 'c_stat', None) or getattr(obj, 'cStat', '') or '')
        return RetornoStatusServicoParsed(
            tp_amb=_attr(obj, 'tp_amb', 'tpAmb'),
            ver_aplic=_attr(obj, 'ver_aplic', 'verAplic'),
            c_stat=c_stat or None,
            x_motivo=_attr(obj, 'x_motivo', 'xMotivo'),
            c_uf=_attr(obj, 'c_uf', 'cUF'),
            dh_recbto=_attr(obj, 'dh_recbto', 'dhRecbto'),
            t_med=_attr(obj, 't_med', 'tMed'),
            versao=_attr(obj, 'versao'),
            servico_operacional=c_stat in ('107', '108'),
        )
    except ImportError:
        return _parse_via_lxml(xml_text)
    except Exception:
        return _parse_via_lxml(xml_text)


def _attr(obj: Any, *names: str) -> str | None:
    for name in names:
        val = getattr(obj, name, None)
        if val is None:
            continue
        if hasattr(val, 'value'):
            val = val.value
        return str(val).strip() or None
    return None


def nfelib_disponivel() -> bool:
    try:
        import nfelib  # noqa: F401

        return True
    except ImportError:
        return False
