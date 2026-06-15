"""Resposta API — Carta de Correção (CC-e) NF-e Saída."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.adapters.carta_correcao_parser import ResultadoCartaCorrecaoSefaz


def montar_resposta_carta_correcao(
    nf: NFeSaida,
    resultado: ResultadoCartaCorrecaoSefaz,
    *,
    ok: bool | None = None,
    mensagem: str = '',
    texto_correcao: str = '',
    sequencia_evento: int | None = None,
) -> dict[str, Any]:
    ambiente = (nf.ambiente_emissao or '').strip() or 'homologacao'
    emitido_em = timezone.now().isoformat()
    sucesso = ok if ok is not None else resultado.ok
    msg = mensagem or (
        f'Carta de Correção registrada — cStat {resultado.c_stat}: {resultado.x_motivo}'.strip()
        if sucesso
        else resultado.x_motivo or 'Carta de Correção não registrada na SEFAZ.'
    )
    return {
        'ok': sucesso,
        'mensagem': msg,
        'nfe_saida_id': nf.pk,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if ambiente == 'homologacao' else 'Produção',
        'chave_acesso': nf.chave_acesso or resultado.chave_acesso,
        'texto_correcao': texto_correcao,
        'sequencia_evento': sequencia_evento or (int(resultado.n_seq_evento) if resultado.n_seq_evento.isdigit() else None),
        'cstat': resultado.c_stat,
        'cStat': resultado.c_stat,
        'xmotivo': resultado.x_motivo,
        'xMotivo': resultado.x_motivo,
        'protocolo': resultado.protocolo,
        'protocolo_evento': resultado.protocolo,
        'emitido_em': emitido_em,
        'status_emissao_sefaz': nf.status_emissao_sefaz or '',
        'etapa': 'CARTA_CORRECAO',
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
