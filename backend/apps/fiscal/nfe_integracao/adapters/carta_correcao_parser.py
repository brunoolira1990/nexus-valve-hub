"""Parser retEnvEvento — Carta de Correção (CC-e) NF-e."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.fiscal.nfe_emissao.retorno_sefaz import _direct_child_text, _find_element, _local, _parse_xml_root, _texto_xml

CSTAT_EVENTO_REGISTRADO = frozenset({'135', '136'})
CSTAT_LOTE_EVENTO_PROCESSADO = frozenset({'128'})


@dataclass(frozen=True)
class ResultadoCartaCorrecaoSefaz:
    ok: bool
    c_stat_lote: str
    x_motivo_lote: str
    c_stat_evento: str
    x_motivo_evento: str
    protocolo: str
    chave_acesso: str
    n_seq_evento: str
    tp_evento: str
    dh_reg_evento: str
    tp_amb: str
    id_evento: str
    xml_retorno: str

    @property
    def c_stat(self) -> str:
        return self.c_stat_evento or self.c_stat_lote

    @property
    def x_motivo(self) -> str:
        return self.x_motivo_evento or self.x_motivo_lote


def _extrair_inf_evento(ret_root: Any) -> Any | None:
    ret_evento = _find_element(ret_root, 'retEvento')
    if ret_evento is not None:
        inf = _find_element(ret_evento, 'infEvento')
        if inf is not None:
            return inf
    return _find_element(ret_root, 'infEvento')


def parse_carta_correcao_resposta(payload: Any) -> ResultadoCartaCorrecaoSefaz:
    xml_str = _texto_xml(payload).strip()
    root = _parse_xml_root(payload)
    if root is None:
        return ResultadoCartaCorrecaoSefaz(
            ok=False,
            c_stat_lote='',
            x_motivo_lote='Resposta SEFAZ vazia ou inválida.',
            c_stat_evento='',
            x_motivo_evento='',
            protocolo='',
            chave_acesso='',
            n_seq_evento='',
            tp_evento='110110',
            dh_reg_evento='',
            tp_amb='',
            id_evento='',
            xml_retorno=xml_str,
        )

    ret = root
    if _local(root.tag) != 'retEnvEvento':
        ret = _find_element(root, 'retEnvEvento') or root

    c_stat_lote = _direct_child_text(ret, 'cStat')
    x_motivo_lote = _direct_child_text(ret, 'xMotivo')
    tp_amb = _direct_child_text(ret, 'tpAmb')

    inf = _extrair_inf_evento(ret)
    c_stat_evento = _direct_child_text(inf, 'cStat') if inf is not None else ''
    x_motivo_evento = _direct_child_text(inf, 'xMotivo') if inf is not None else ''
    protocolo = _direct_child_text(inf, 'nProt') if inf is not None else ''
    chave = _direct_child_text(inf, 'chNFe') if inf is not None else ''
    n_seq = _direct_child_text(inf, 'nSeqEvento') if inf is not None else ''
    tp_evento = _direct_child_text(inf, 'tpEvento') if inf is not None else '110110'
    dh_reg = _direct_child_text(inf, 'dhRegEvento') if inf is not None else ''
    id_evento = ''
    if inf is not None and inf.get('Id'):
        id_evento = str(inf.get('Id') or '')

    cstat_efetivo = c_stat_evento or c_stat_lote
    ok = cstat_efetivo in CSTAT_EVENTO_REGISTRADO or (
        cstat_efetivo in CSTAT_LOTE_EVENTO_PROCESSADO and bool(protocolo)
    )

    return ResultadoCartaCorrecaoSefaz(
        ok=ok,
        c_stat_lote=c_stat_lote,
        x_motivo_lote=x_motivo_lote,
        c_stat_evento=c_stat_evento,
        x_motivo_evento=x_motivo_evento,
        protocolo=protocolo,
        chave_acesso=chave,
        n_seq_evento=n_seq,
        tp_evento=tp_evento or '110110',
        dh_reg_evento=dh_reg,
        tp_amb=tp_amb,
        id_evento=id_evento,
        xml_retorno=xml_str,
    )
