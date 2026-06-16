"""Resposta API — Cancelamento SEFAZ NF-e Saída."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.adapters.cancelamento_parser import ResultadoCancelamentoSefaz


def montar_resposta_cancelamento(
    nf: NFeSaida,
    resultado: ResultadoCancelamentoSefaz,
    *,
    ok: bool | None = None,
    mensagem: str = '',
    justificativa: str = '',
    evento_id: int | None = None,
) -> dict[str, Any]:
    ambiente = (nf.ambiente_emissao or '').strip() or 'homologacao'
    emitido_em = timezone.now().isoformat()
    sucesso = ok if ok is not None else resultado.ok
    msg = mensagem or (
        f'Cancelamento registrado — cStat {resultado.c_stat}: {resultado.x_motivo}'.strip()
        if sucesso
        else resultado.x_motivo or 'Cancelamento não registrado na SEFAZ.'
    )
    return {
        'ok': sucesso,
        'mensagem': msg,
        'nfe_saida_id': nf.pk,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if ambiente == 'homologacao' else 'Produção',
        'chave_acesso': nf.chave_acesso or resultado.chave_acesso,
        'justificativa': justificativa,
        'evento_id': evento_id,
        'cstat': resultado.c_stat,
        'cStat': resultado.c_stat,
        'xmotivo': resultado.x_motivo,
        'xMotivo': resultado.x_motivo,
        'protocolo': resultado.protocolo,
        'protocolo_cancelamento': resultado.protocolo,
        'emitido_em': emitido_em,
        'status': nf.status or '',
        'status_emissao_sefaz': nf.status_emissao_sefaz or '',
        'etapa': 'CANCELAMENTO',
        'evento_sefaz': {
            'cstat': resultado.c_stat,
            'xmotivo': resultado.x_motivo,
            'protocolo': resultado.protocolo,
            'n_seq_evento': resultado.n_seq_evento,
            'tp_evento': resultado.tp_evento,
            'dh_reg_evento': resultado.dh_reg_evento,
            'id_evento': resultado.id_evento,
        },
    }
