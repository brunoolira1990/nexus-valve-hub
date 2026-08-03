"""Respostas JSON padronizadas — emissão NF-e entrada própria."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeEntrada
from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz


def montar_resposta_emissao_entrada(
    nf: NFeEntrada | None,
    *,
    ok: bool,
    ambiente: str,
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
    if resultado is not None:
        cstat = cstat or (resultado.nfe.c_stat if resultado.nfe else '')
        xmotivo = xmotivo or (resultado.nfe.x_motivo if resultado.nfe else '')
        protocolo = protocolo or resultado.protocolo
        if autorizado is None:
            autorizado = resultado.autorizado
        if not ok and resultado.autorizado:
            ok = True

    status_autorizada = (
        NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO
        if ambiente == 'producao'
        else NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
    )
    if autorizado is None:
        autorizado = ok and bool(
            cstat in ('100', '150')
            or (nf and nf.status_emissao_sefaz == status_autorizada),
        )

    cstat_nfe = cstat or (nf.cstat_autorizacao if nf else '') or ''
    xmotivo_nfe = xmotivo or (nf.motivo_autorizacao if nf else '') or ''

    payload: dict[str, Any] = {
        'ok': ok,
        'autorizado': bool(autorizado),
        'ambiente': ambiente,
        'status': (nf.status_emissao_sefaz if nf else '') or '',
        'status_operacional': (nf.status_operacional if nf else '') or '',
        'nf_entrada_id': nf.pk if nf else None,
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
        'tp_nf': '0',
        'lote': {
            'cstat': (nf.cstat_lote if nf else '') or (resultado.lote.c_stat if resultado else ''),
            'xmotivo': (nf.xmotivo_lote if nf else '') or (resultado.lote.x_motivo if resultado else ''),
            'recibo': (nf.recibo_lote if nf else '') or (resultado.recibo if resultado else ''),
        },
        'nfe': {
            'cstat': cstat_nfe,
            'xmotivo': xmotivo_nfe,
            'protocolo': protocolo or (nf.protocolo_autorizacao if nf else '') or '',
            'dh_recbto': (resultado.nfe.dh_recbto if resultado and resultado.nfe else '') or '',
        },
    }
    if extras:
        payload.update(extras)
    return payload
