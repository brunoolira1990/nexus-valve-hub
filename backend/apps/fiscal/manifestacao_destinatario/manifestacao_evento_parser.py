"""Parser retEnvEvento — Manifestação do Destinatário (evento individual da NF-e)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.fiscal.nfe_emissao.retorno_sefaz import _direct_child_text, _find_element, _local, _parse_xml_root, _texto_xml

# cStat do evento individual aceito / idempotente (não usar cStat 128 do lote sozinho).
CSTAT_EVENTO_ACEITO = frozenset({'135', '136', '155', '573'})
CSTAT_DUPLICIDADE_EVENTO = frozenset({'573'})


@dataclass(frozen=True)
class ResultadoManifestacaoEventoSefaz:
    c_stat_lote: str
    x_motivo_lote: str
    c_stat_evento: str
    x_motivo_evento: str
    protocolo: str
    tp_evento: str
    chave_acesso: str
    xml_retorno: str

    @property
    def cstat_efetivo(self) -> str:
        return self.c_stat_evento or self.c_stat_lote

    @property
    def xmotivo_efetivo(self) -> str:
        if self.c_stat_evento:
            return self.x_motivo_evento or self.x_motivo_lote
        return self.x_motivo_lote or self.x_motivo_evento

    @property
    def duplicidade(self) -> bool:
        return self.c_stat_evento in CSTAT_DUPLICIDADE_EVENTO

    @property
    def aceito(self) -> bool:
        """Somente o retorno individual do evento define sucesso."""
        if not self.c_stat_evento:
            return False
        return self.c_stat_evento in CSTAT_EVENTO_ACEITO


def _extrair_inf_evento(ret_root: Any) -> Any | None:
    ret_evento = _find_element(ret_root, 'retEvento')
    if ret_evento is not None:
        inf = _find_element(ret_evento, 'infEvento')
        if inf is not None:
            return inf
    return _find_element(ret_root, 'infEvento')


def parse_manifestacao_evento_resposta(payload: Any) -> ResultadoManifestacaoEventoSefaz:
    xml_str = _texto_xml(payload).strip()
    root = _parse_xml_root(payload)
    if root is None:
        return ResultadoManifestacaoEventoSefaz(
            c_stat_lote='',
            x_motivo_lote='Resposta SEFAZ vazia ou inválida.',
            c_stat_evento='',
            x_motivo_evento='',
            protocolo='',
            tp_evento='',
            chave_acesso='',
            xml_retorno=xml_str,
        )

    ret = root
    if _local(root.tag) != 'retEnvEvento':
        ret = _find_element(root, 'retEnvEvento') or root

    c_stat_lote = _direct_child_text(ret, 'cStat')
    x_motivo_lote = _direct_child_text(ret, 'xMotivo')

    inf = _extrair_inf_evento(ret)
    c_stat_evento = _direct_child_text(inf, 'cStat') if inf is not None else ''
    x_motivo_evento = _direct_child_text(inf, 'xMotivo') if inf is not None else ''
    protocolo = _direct_child_text(inf, 'nProt') if inf is not None else ''
    chave = _direct_child_text(inf, 'chNFe') if inf is not None else ''
    tp_evento = _direct_child_text(inf, 'tpEvento') if inf is not None else ''

    return ResultadoManifestacaoEventoSefaz(
        c_stat_lote=c_stat_lote,
        x_motivo_lote=x_motivo_lote,
        c_stat_evento=c_stat_evento,
        x_motivo_evento=x_motivo_evento,
        protocolo=protocolo,
        tp_evento=tp_evento,
        chave_acesso=chave,
        xml_retorno=xml_str,
    )
