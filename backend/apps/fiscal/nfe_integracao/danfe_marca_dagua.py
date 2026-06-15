"""Marca d'água do DANFE conforme status fiscal real da NF-e (MOC / Nexus)."""

from __future__ import annotations

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_bloqueio import STATUS_NFE_RASCUNHO

_STATUS_CANCELADA = frozenset({'CANCELADA', 'CANCELADO', 'CANCELADA_INTERNA'})
_STATUS_EMITIDA = frozenset({
    'EMITIDA',
    'EMITIDO',
    'AUTORIZADA_INTERNA',
    'AUTORIZADA',
    'AUTORIZADA_HOMOLOGACAO',
})
_STATUS_DENEGADA = frozenset({'DENEGADA', 'DENEGADO'})


def _norm_status(val: str | None) -> str:
    return (val or '').strip().upper()


def _tp_amb_str(ambiente: str | int | None, *, nfe_saida: NFeSaida | None = None) -> str:
    if ambiente is not None:
        raw = str(ambiente).strip()
        if raw in ('1', '2'):
            return raw
    if nfe_saida is not None:
        amb = (nfe_saida.ambiente_emissao or '').strip()
        if amb == NFeSaida.AmbienteEmissao.PRODUCAO:
            return '1'
        if amb == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
            return '2'
    return '2'


def nfe_em_conferencia_ou_pre_emissao(nfe_saida: NFeSaida, *, tem_protocolo: bool = False) -> bool:
    """Rascunho/conferência/pronta — sem autorização SEFAZ real."""
    if tem_protocolo:
        return False
    st = _norm_status(nfe_saida.status)
    if st in _STATUS_CANCELADA or st in _STATUS_DENEGADA:
        return False
    if st in _STATUS_EMITIDA:
        return False
    if st == STATUS_NFE_RASCUNHO:
        return True
    conf = _norm_status(nfe_saida.status_conferencia)
    return conf in (
        'EM_CONFERENCIA',
        'COM_PENDENCIAS',
        'CONFERIDA',
        'PRONTA_PARA_EMISSAO',
        '',
    )


def nfe_cancelada(nfe_saida: NFeSaida) -> bool:
    return _norm_status(nfe_saida.status) in _STATUS_CANCELADA


def nfe_autorizada(nfe_saida: NFeSaida, *, tem_protocolo: bool = False) -> bool:
    st = _norm_status(nfe_saida.status)
    if st in _STATUS_EMITIDA:
        return True
    if (nfe_saida.status_emissao_sefaz or '') == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        return True
    if (nfe_saida.status_emissao_sefaz or '') == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
        return True
    if st == 'AUTORIZADA_PRODUCAO':
        return True
    return bool(tem_protocolo or nfe_saida.efeitos_autorizacao_aplicados_em)


def resolver_marca_dagua_danfe(
    nfe_saida: NFeSaida,
    ambiente: str | int | None = None,
    *,
    tem_protocolo: bool = False,
) -> str | None:
    """
    Texto da marca d'água para o DANFE (linhas separadas por \\n).

    BrazilFiscalReport 0.7.4 não expõe texto customizado em DanfeConfig; o renderer Nexus
    (DanfeNexus) desenha este texto quando retornado. None = sem marca customizada
    (homologação autorizada usa só «SEM VALOR FISCAL» da biblioteca).
    """
    tp_amb = _tp_amb_str(ambiente, nfe_saida=nfe_saida)
    homolog = tp_amb != '1'

    if _norm_status(nfe_saida.status) in _STATUS_DENEGADA:
        return 'DENEGADA'

    if nfe_cancelada(nfe_saida):
        if homolog:
            return 'CANCELADA\nSEM VALOR FISCAL'
        return 'CANCELADA'

    if nfe_autorizada(nfe_saida, tem_protocolo=tem_protocolo):
        if homolog:
            return 'SEM VALOR FISCAL'
        return None

    if nfe_em_conferencia_ou_pre_emissao(nfe_saida, tem_protocolo=tem_protocolo):
        return 'DANFE DE CONFERÊNCIA\nSEM VALOR FISCAL'

    # XML preliminar / pré-autorização sem protocolo
    if not tem_protocolo:
        return 'DANFE DE CONFERÊNCIA\nSEM VALOR FISCAL'

    return None


def usar_watermark_cancelada_bfr(nfe_saida: NFeSaida) -> bool:
    """Só ativa watermark_cancelled da BFR quando a NF-e está realmente cancelada."""
    return nfe_cancelada(nfe_saida)
