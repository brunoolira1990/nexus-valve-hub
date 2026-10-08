"""Resposta API — consulta situação NF-e na SEFAZ."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_integracao.adapters.consulta_situacao_parser import ResultadoConsultaSituacaoSefaz


def montar_resposta_consulta_situacao(
    nf: NFeSaida,
    resultado: ResultadoConsultaSituacaoSefaz,
    *,
    ok: bool | None = None,
    mensagem: str = '',
    status_local_atualizado: bool = False,
) -> dict[str, Any]:
    ambiente = (nf.ambiente_emissao or '').strip() or 'homologacao'
    consultado_em = timezone.now().isoformat()
    sucesso = ok if ok is not None else resultado.ok
    msg = mensagem or (
        f'Consulta SEFAZ concluída — cStat {resultado.c_stat}: {resultado.x_motivo}'.strip()
        if sucesso
        else resultado.x_motivo or 'Consulta SEFAZ não concluída.'
    )
    return {
        'ok': sucesso,
        'mensagem': msg,
        'nfe_saida_id': nf.pk,
        'ambiente': ambiente,
        'ambiente_label': 'Homologação' if ambiente == 'homologacao' else 'Produção',
        'chave_acesso': nf.chave_acesso or resultado.chave_acesso,
        'cstat': resultado.c_stat,
        'cStat': resultado.c_stat,
        'xmotivo': resultado.x_motivo,
        'xMotivo': resultado.x_motivo,
        'protocolo': resultado.protocolo or nf.protocolo_autorizacao or '',
        'protocolo_autorizacao': resultado.protocolo or nf.protocolo_autorizacao or '',
        'consultado_em': consultado_em,
        'status_emissao_sefaz': nf.status_emissao_sefaz or '',
        'status_local_atualizado': status_local_atualizado,
        'sem_efeitos_fiscais': True,
        'etapa': 'CONSULTA_SITUACAO',
        'situacao_sefaz': {
            'cstat': resultado.c_stat,
            'xmotivo': resultado.x_motivo,
            'protocolo': resultado.protocolo,
            'dh_recbto': resultado.dh_recbto,
            'autorizada': resultado.autorizada,
            'cancelada': resultado.cancelada,
            'denegada': resultado.denegada,
        },
    }
