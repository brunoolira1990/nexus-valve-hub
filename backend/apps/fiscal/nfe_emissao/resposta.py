"""Resposta JSON padronizada da emissão NF-e em homologação."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz


def montar_resposta_emissao_homologacao(
    nf: NFeSaida | None,
    *,
    ok: bool,
    autorizado: bool | None = None,
    mensagem: str = '',
    erros: list[str] | None = None,
    cstat: str = '',
    xmotivo: str = '',
    protocolo: str = '',
    etapa: str = '',
    resultado: ResultadoAutorizacaoSefaz | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Formato único para UI e testes — separa lote vs NF-e."""
    if resultado is not None:
        cstat = cstat or (resultado.nfe.c_stat if resultado.nfe else '')
        xmotivo = xmotivo or (resultado.nfe.x_motivo if resultado.nfe else '')
        protocolo = protocolo or resultado.protocolo
        if autorizado is None:
            autorizado = resultado.autorizado
        if not ok and resultado.autorizado:
            ok = True

    if autorizado is None:
        autorizado = ok and bool(
            cstat in ('100', '150')
            or (nf and nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO),
        )

    status = ''
    if nf:
        status = nf.status_emissao_sefaz or nf.status or ''

    cstat_nfe = cstat or (nf.cstat_autorizacao if nf else '') or ''
    xmotivo_nfe = xmotivo or (nf.motivo_autorizacao if nf else '') or ''

    payload: dict[str, Any] = {
        'ok': ok,
        'autorizado': bool(autorizado),
        'ambiente': 'homologacao',
        'status': status,
        'numero_nfe': (nf.numero_nfe if nf else '') or '',
        'serie_nfe': (nf.serie_nfe if nf else '') or '',
        'chave_acesso': (nf.chave_acesso if nf else '') or '',
        'cstat': cstat_nfe,
        'xmotivo': xmotivo_nfe,
        'cStat': cstat_nfe,
        'xMotivo': xmotivo_nfe,
        'protocolo': protocolo or (nf.protocolo_autorizacao if nf else '') or '',
        'protocolo_autorizacao': protocolo or (nf.protocolo_autorizacao if nf else '') or '',
        'mensagem': mensagem,
        'erros': list(erros or []),
        'etapa': etapa,
        'sem_efeitos_erp': True,
        'lote': {
            'cstat': (nf.cstat_lote if nf else '') or (resultado.lote.c_stat if resultado else ''),
            'xmotivo': (nf.xmotivo_lote if nf else '') or (resultado.lote.x_motivo if resultado else ''),
            'recibo': (nf.recibo_lote if nf else '') or (resultado.recibo if resultado else ''),
        },
        'nfe': {
            'cstat': cstat_nfe,
            'xmotivo': xmotivo_nfe,
            'protocolo': protocolo or (nf.protocolo_autorizacao if nf else '') or '',
            'dh_recbto': (
                (resultado.nfe.dh_recbto if resultado and resultado.nfe else '')
                or ''
            ),
        },
    }
    if nf:
        payload['nfe_saida_id'] = nf.pk
        payload['status_emissao_sefaz'] = nf.status_emissao_sefaz
        payload['ambiente_emissao'] = nf.ambiente_emissao or 'homologacao'
    if extras:
        payload.update(extras)
    return payload
