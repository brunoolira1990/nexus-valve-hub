"""Resposta API — Inutilização SEFAZ NF-e."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.fiscal.nfe_integracao.adapters.inutilizacao_parser import ResultadoInutilizacaoSefaz


def montar_resposta_inutilizacao(
    *,
    configuracao_id: int,
    serie: str,
    ambiente: str,
    numero_inicial: int,
    numero_final: int,
    resultado: ResultadoInutilizacaoSefaz,
    ok: bool | None = None,
    mensagem: str = '',
    justificativa: str = '',
    inutilizacao_id: int | None = None,
    nfs_afetadas: list[int] | None = None,
) -> dict[str, Any]:
    sucesso = ok if ok is not None else resultado.ok
    msg = mensagem or (
        f'Inutilização homologada — cStat {resultado.c_stat}: {resultado.x_motivo}'.strip()
        if sucesso
        else resultado.x_motivo or 'Inutilização não homologada pela SEFAZ.'
    )
    return {
        'ok': sucesso,
        'mensagem': msg,
        'configuracao_id': configuracao_id,
        'serie': serie,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if ambiente == 'homologacao' else 'Produção',
        'numero_inicial': numero_inicial,
        'numero_final': numero_final,
        'justificativa': justificativa,
        'inutilizacao_id': inutilizacao_id,
        'nfs_afetadas': nfs_afetadas or [],
        'cstat': resultado.c_stat,
        'cStat': resultado.c_stat,
        'xmotivo': resultado.x_motivo,
        'xMotivo': resultado.x_motivo,
        'protocolo': resultado.protocolo,
        'protocolo_inutilizacao': resultado.protocolo,
        'emitido_em': timezone.now().isoformat(),
        'etapa': 'INUTILIZACAO',
        'sefaz': {
            'cstat': resultado.c_stat,
            'xmotivo': resultado.x_motivo,
            'protocolo': resultado.protocolo,
            'serie': resultado.serie or serie,
            'numero_inicial': resultado.numero_inicial or str(numero_inicial),
            'numero_final': resultado.numero_final or str(numero_final),
            'ano': resultado.ano,
            'dh_recbto': resultado.dh_recbto,
        },
    }
