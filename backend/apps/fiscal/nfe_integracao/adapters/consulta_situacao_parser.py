"""Parser retConsSitNFe — consulta situação NF-e na SEFAZ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.fiscal.nfe_emissao.retorno_sefaz import _direct_child_text, _find_element, _local, _parse_xml_root, _texto_xml

CSTAT_AUTORIZADO = frozenset({'100', '150'})
CSTAT_CANCELADO = frozenset({'101', '151', '135'})
CSTAT_DENEGADO = frozenset({'110', '301', '302', '303'})


@dataclass(frozen=True)
class ResultadoConsultaSituacaoSefaz:
    ok: bool
    c_stat_consulta: str
    x_motivo_consulta: str
    c_stat_nfe: str
    x_motivo_nfe: str
    protocolo: str
    chave_acesso: str
    dh_recbto: str
    tp_amb: str
    xml_retorno: str
    autorizada: bool
    cancelada: bool
    denegada: bool

    @property
    def c_stat(self) -> str:
        return self.c_stat_nfe or self.c_stat_consulta

    @property
    def x_motivo(self) -> str:
        return self.x_motivo_nfe or self.x_motivo_consulta


def _extrair_prot_nfe(ret_root: Any) -> Any | None:
    prot = _find_element(ret_root, 'protNFe')
    if prot is not None:
        return _find_element(prot, 'infProt') or prot
    return _find_element(ret_root, 'infProt')


def parse_consulta_situacao_resposta(payload: Any) -> ResultadoConsultaSituacaoSefaz:
    xml_str = _texto_xml(payload).strip()
    root = _parse_xml_root(payload)
    if root is None:
        return ResultadoConsultaSituacaoSefaz(
            ok=False,
            c_stat_consulta='',
            x_motivo_consulta='Resposta SEFAZ vazia ou inválida.',
            c_stat_nfe='',
            x_motivo_nfe='',
            protocolo='',
            chave_acesso='',
            dh_recbto='',
            tp_amb='',
            xml_retorno=xml_str,
            autorizada=False,
            cancelada=False,
            denegada=False,
        )

    ret = root
    if _local(root.tag) != 'retConsSitNFe':
        ret = _find_element(root, 'retConsSitNFe') or root

    c_stat_consulta = _direct_child_text(ret, 'cStat')
    x_motivo_consulta = _direct_child_text(ret, 'xMotivo')
    tp_amb = _direct_child_text(ret, 'tpAmb')

    inf_prot = _extrair_prot_nfe(ret)
    c_stat_nfe = _direct_child_text(inf_prot, 'cStat') if inf_prot is not None else ''
    x_motivo_nfe = _direct_child_text(inf_prot, 'xMotivo') if inf_prot is not None else ''
    protocolo = _direct_child_text(inf_prot, 'nProt') if inf_prot is not None else ''
    chave = _direct_child_text(inf_prot, 'chNFe') if inf_prot is not None else ''
    dh_recbto = _direct_child_text(inf_prot, 'dhRecbto') if inf_prot is not None else ''

    cstat_efetivo = c_stat_nfe or c_stat_consulta
    autorizada = cstat_efetivo in CSTAT_AUTORIZADO
    cancelada = cstat_efetivo in CSTAT_CANCELADO
    denegada = cstat_efetivo in CSTAT_DENEGADO
    ok = bool(cstat_efetivo) and cstat_efetivo not in ('', 'ERRO')

    return ResultadoConsultaSituacaoSefaz(
        ok=ok,
        c_stat_consulta=c_stat_consulta,
        x_motivo_consulta=x_motivo_consulta,
        c_stat_nfe=c_stat_nfe,
        x_motivo_nfe=x_motivo_nfe,
        protocolo=protocolo,
        chave_acesso=chave,
        dh_recbto=dh_recbto,
        tp_amb=tp_amb,
        xml_retorno=xml_str,
        autorizada=autorizada,
        cancelada=cancelada,
        denegada=denegada,
    )
