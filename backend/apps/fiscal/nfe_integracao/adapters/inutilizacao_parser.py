"""Parser retInutNFe — Inutilização de numeração NF-e."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.fiscal.nfe_emissao.retorno_sefaz import _direct_child_text, _find_element, _local, _parse_xml_root, _texto_xml

CSTAT_INUTILIZACAO_HOMOLOGADA = frozenset({'102', '563'})


@dataclass(frozen=True)
class ResultadoInutilizacaoSefaz:
    ok: bool
    c_stat: str
    x_motivo: str
    protocolo: str
    serie: str
    numero_inicial: str
    numero_final: str
    ano: str
    tp_amb: str
    dh_recbto: str
    xml_retorno: str

    @property
    def cStat(self) -> str:
        return self.c_stat

    @property
    def xMotivo(self) -> str:
        return self.x_motivo


def parse_inutilizacao_resposta(payload: Any) -> ResultadoInutilizacaoSefaz:
    xml_str = _texto_xml(payload).strip()
    root = _parse_xml_root(payload)
    if root is None:
        return ResultadoInutilizacaoSefaz(
            ok=False,
            c_stat='',
            x_motivo='Resposta SEFAZ vazia ou inválida.',
            protocolo='',
            serie='',
            numero_inicial='',
            numero_final='',
            ano='',
            tp_amb='',
            dh_recbto='',
            xml_retorno=xml_str,
        )

    ret = root
    if _local(root.tag) != 'retInutNFe':
        ret = _find_element(root, 'retInutNFe') or root

    inf = _find_element(ret, 'infInut')
    if inf is None:
        c_stat = _direct_child_text(ret, 'cStat')
        x_motivo = _direct_child_text(ret, 'xMotivo')
        return ResultadoInutilizacaoSefaz(
            ok=c_stat in CSTAT_INUTILIZACAO_HOMOLOGADA,
            c_stat=c_stat,
            x_motivo=x_motivo,
            protocolo='',
            serie='',
            numero_inicial='',
            numero_final='',
            ano='',
            tp_amb='',
            dh_recbto='',
            xml_retorno=xml_str,
        )

    c_stat = _direct_child_text(inf, 'cStat')
    x_motivo = _direct_child_text(inf, 'xMotivo')
    protocolo = _direct_child_text(inf, 'nProt')
    serie = _direct_child_text(inf, 'serie')
    numero_inicial = _direct_child_text(inf, 'nNFIni')
    numero_final = _direct_child_text(inf, 'nNFFin')
    ano = _direct_child_text(inf, 'ano')
    tp_amb = _direct_child_text(inf, 'tpAmb')
    dh_recbto = _direct_child_text(inf, 'dhRecbto')

    ok = c_stat in CSTAT_INUTILIZACAO_HOMOLOGADA

    return ResultadoInutilizacaoSefaz(
        ok=ok,
        c_stat=c_stat,
        x_motivo=x_motivo,
        protocolo=protocolo,
        serie=serie,
        numero_inicial=numero_inicial,
        numero_final=numero_final,
        ano=ano,
        tp_amb=tp_amb,
        dh_recbto=dh_recbto,
        xml_retorno=xml_str,
    )
