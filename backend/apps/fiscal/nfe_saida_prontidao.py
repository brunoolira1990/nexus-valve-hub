"""NF-e Saída 3.5.3 — prontidão da conferência (separada do status fiscal/SEFAZ)."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.fiscal.models import NFeSaida, NFeSaidaEvento
from apps.fiscal.nfe_saida_bloqueio import STATUS_NFE_RASCUNHO, dados_complementares_editaveis, nf_autorizada_homologacao, nf_ja_finalizada_operacionalmente
from apps.fiscal.nfe_saida_efeitos import _registrar_evento
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao

MSG_MARCAR_PRONTA_PENDENCIAS = 'Não é possível marcar como pronta. Existem pendências bloqueantes.'
MSG_MARCAR_PRONTA_STATUS = 'Somente NF-e em rascunho pode ser marcada como pronta para emissão.'
MSG_MARCAR_PRONTA_FINALIZADA = 'NF-e autorizada ou cancelada não pode ser marcada como pronta.'


STATUS_CONFERENCIA_LABELS = {
    NFeSaida.StatusConferencia.EM_CONFERENCIA: 'Em conferência',
    NFeSaida.StatusConferencia.COM_PENDENCIAS: 'Com pendências',
    NFeSaida.StatusConferencia.CONFERIDA: 'Conferida',
    NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO: 'Pronta para emissão',
}


def status_conferencia_display(status: str | None) -> str:
    st = (status or '').strip().upper()
    if not st:
        return STATUS_CONFERENCIA_LABELS[NFeSaida.StatusConferencia.EM_CONFERENCIA]
    for key, label in STATUS_CONFERENCIA_LABELS.items():
        if key == st:
            return label
    return st


def _norm_status_fiscal(status: str | None) -> str:
    return (status or '').strip().upper()


def tem_pendencias_bloqueantes(validacao: dict[str, Any]) -> bool:
    return int(validacao.get('total_pendencias') or 0) > 0


def pode_validar_conferencia(nf: NFeSaida) -> bool:
    if nf_autorizada_homologacao(nf):
        return False
    if nf_ja_finalizada_operacionalmente(nf):
        return False
    if _norm_status_fiscal(nf.status) != STATUS_NFE_RASCUNHO:
        return False
    return nf.itens.exists()


def pode_marcar_pronta(nf: NFeSaida, validacao: dict[str, Any] | None = None) -> bool:
    if not pode_validar_conferencia(nf):
        return False
    st_conf = (nf.status_conferencia or '').strip().upper()
    if st_conf == NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO:
        return False
    val = validacao if validacao is not None else validar_nfe_saida_para_emissao(nf)
    return not tem_pendencias_bloqueantes(val)


def avaliar_prontidao_nfe(nf: NFeSaida) -> dict[str, Any]:
    validacao = validar_nfe_saida_para_emissao(nf)
    sugerido = (
        NFeSaida.StatusConferencia.COM_PENDENCIAS
        if tem_pendencias_bloqueantes(validacao)
        else NFeSaida.StatusConferencia.CONFERIDA
    )
    return {
        'status_conferencia_sugerido': sugerido,
        'pode_marcar_pronta': pode_marcar_pronta(nf, validacao),
        'total_pendencias': validacao.get('total_pendencias', 0),
        'total_alertas': validacao.get('total_alertas', 0),
        'mensagens': validacao.get('mensagens', []),
        'grupos': validacao.get('grupos', {}),
        'validacao': validacao,
    }


def montar_payload_prontidao(nf: NFeSaida, validacao: dict[str, Any] | None = None) -> dict[str, Any]:
    st = nf.status_conferencia or NFeSaida.StatusConferencia.EM_CONFERENCIA
    if validacao is not None:
        val = validacao
        pode_marcar = pode_marcar_pronta(nf, val)
        total_pendencias = val.get('total_pendencias', 0)
        total_alertas = val.get('total_alertas', 0)
        mensagens = val.get('mensagens', [])
    else:
        val = None
        st_upper = st.strip().upper()
        total_pendencias = 1 if st_upper == NFeSaida.StatusConferencia.COM_PENDENCIAS else 0
        total_alertas = 0
        mensagens = [nf.conferencia_ultima_mensagem] if nf.conferencia_ultima_mensagem else []
        pode_marcar = st_upper == NFeSaida.StatusConferencia.CONFERIDA
    return {
        'nfe_saida_id': nf.pk,
        'status': nf.status,
        'status_conferencia': st,
        'status_conferencia_display': status_conferencia_display(st),
        'pode_validar': pode_validar_conferencia(nf),
        'pode_marcar_pronta': pode_marcar,
        'total_pendencias': total_pendencias,
        'total_alertas': total_alertas,
        'mensagens': mensagens,
        'ultima_validacao_em': (
            nf.conferencia_validada_em.isoformat() if nf.conferencia_validada_em else None
        ),
        'marcada_pronta_em': (
            nf.conferencia_marcada_pronta_em.isoformat() if nf.conferencia_marcada_pronta_em else None
        ),
        'conferencia_ultima_mensagem': nf.conferencia_ultima_mensagem or '',
        'validacao_cacheada': validacao is None,
    }


def _grupos_com_pendencias(validacao: dict[str, Any]) -> list[str]:
    grupos: list[str] = []
    for nome, itens in (validacao.get('grupos') or {}).items():
        if any((it or {}).get('tipo') == 'PENDENCIA' for it in (itens or [])):
            grupos.append(nome)
    return grupos


def invalidar_prontidao_nfe(
    nf: NFeSaida,
    motivo: str = '',
    *,
    usuario=None,
) -> bool:
    """Volta de PRONTA_PARA_EMISSAO para EM_CONFERENCIA quando aplicável."""
    anterior = (nf.status_conferencia or '').strip().upper()
    if anterior != NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO:
        return False
    nf.status_conferencia = NFeSaida.StatusConferencia.EM_CONFERENCIA
    if motivo:
        nf.conferencia_ultima_mensagem = motivo[:2000]
    nf.save(update_fields=['status_conferencia', 'conferencia_ultima_mensagem'])
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.PRONTIDAO_INVALIDADA,
        status_anterior=anterior,
        status_novo=nf.status_conferencia,
        resumo={'motivo': motivo},
        observacao=motivo or 'Prontidão invalidada.',
        usuario=usuario,
    )
    return True


def processar_prontidao_apos_salvar_conferencia(
    nf: NFeSaida,
    *,
    usuario=None,
    alterou_dados: bool = False,
) -> NFeSaida:
    """Após salvar complementos: invalida prontidão se necessário — sem checklist pesado."""
    if not dados_complementares_editaveis(nf):
        return nf
    anterior = nf.status_conferencia
    if alterou_dados:
        invalidar_prontidao_nfe(
            nf,
            'Dados da conferência alterados após marcação de pronta.',
            usuario=usuario,
        )
        nf.refresh_from_db()
    st_atual = (nf.status_conferencia or '').strip().upper()
    if st_atual == NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO:
        return nf
    if alterou_dados and st_atual != NFeSaida.StatusConferencia.EM_CONFERENCIA:
        novo = NFeSaida.StatusConferencia.EM_CONFERENCIA
        nf.status_conferencia = novo
        nf.save(update_fields=['status_conferencia'])
        if anterior != novo:
            _registrar_evento(
                nf,
                tipo=NFeSaidaEvento.TipoEvento.CONFERENCIA_SALVA,
                status_anterior=anterior or '',
                status_novo=novo,
                resumo={'alterou_dados': True},
                observacao='Conferência salva; validação pendente.',
                usuario=usuario,
            )
    return nf


def invalidar_prontidao_apos_atualizar_fiscal(nf: NFeSaida, *, usuario=None) -> None:
    """Reabre fluxo de conferência após atualizar impostos/textos fiscais."""
    anterior = nf.status_conferencia
    invalidar_prontidao_nfe(nf, 'Impostos ou textos fiscais atualizados.', usuario=usuario)
    nf.status_conferencia = NFeSaida.StatusConferencia.EM_CONFERENCIA
    update_fields = ['status_conferencia']
    if anterior != NFeSaida.StatusConferencia.EM_CONFERENCIA:
        nf.save(update_fields=update_fields)


def validar_conferencia_nfe(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    from apps.fiscal.nfe_perf import medir_nfe_perf
    from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida
    from apps.fiscal.validacao_nfe_saida import MODO_VALIDACAO_COMPLETO, validar_nfe_saida_para_emissao

    if not pode_validar_conferencia(nf):
        raise ValueError('NF-e não está em rascunho ou não possui itens para validar conferência.')

    with medir_nfe_perf('validar_conferencia', nfe_id=nf.pk) as perf:
        from apps.fiscal.nfe_saida_duplicatas import recalcular_duplicatas_por_data_emissao

        recalcular_duplicatas_por_data_emissao(nf, save=True)
        perf.marcar('duplicatas_ms')
        validacao = validar_nfe_saida_para_emissao(nf, modo=MODO_VALIDACAO_COMPLETO)
        perf.marcar('checklist_ms')
        anterior = nf.status_conferencia
        pendencias = tem_pendencias_bloqueantes(validacao)
        if pendencias:
            novo = NFeSaida.StatusConferencia.COM_PENDENCIAS
            tipo_evt = NFeSaidaEvento.TipoEvento.CONFERENCIA_COM_PENDENCIAS
            msg = f'Conferência com {validacao.get("total_pendencias", 0)} pendência(s) bloqueante(s).'
        else:
            novo = NFeSaida.StatusConferencia.CONFERIDA
            tipo_evt = NFeSaidaEvento.TipoEvento.CONFERENCIA_VALIDADA
            msg = 'Conferência validada sem pendências bloqueantes.'
        agora = timezone.now()
        nf.status_conferencia = novo
        nf.conferencia_validada_em = agora
        nf.conferencia_validada_por = usuario if usuario and getattr(usuario, 'is_authenticated', False) else None
        nf.conferencia_ultima_mensagem = msg
        nf.save(
            update_fields=[
                'status_conferencia',
                'conferencia_validada_em',
                'conferencia_validada_por',
                'conferencia_ultima_mensagem',
            ],
        )
        _registrar_evento(
            nf,
            tipo=tipo_evt,
            status_anterior=anterior or '',
            status_novo=novo,
            resumo={
                'total_pendencias': validacao.get('total_pendencias', 0),
                'total_alertas': validacao.get('total_alertas', 0),
                'grupos': _grupos_com_pendencias(validacao),
            },
            observacao=msg,
            usuario=usuario,
        )
        perf.marcar('persist_ms')
        conferencia = montar_conferencia_nfe_saida(
            nf,
            modo='completo',
            validacao=validacao,
            incluir_checklist=True,
            usuario=usuario,
        )
        perf.marcar('conferencia_ms')
        return {
            'prontidao': montar_payload_prontidao(nf, validacao=validacao),
            'validacao': validacao,
            'conferencia': conferencia,
            'mensagem': msg,
        }

def marcar_nfe_pronta_para_emissao(nf: NFeSaida, *, usuario=None) -> dict[str, Any]:
    if nf_ja_finalizada_operacionalmente(nf):
        raise ValueError(MSG_MARCAR_PRONTA_FINALIZADA)
    if _norm_status_fiscal(nf.status) != STATUS_NFE_RASCUNHO:
        raise ValueError(MSG_MARCAR_PRONTA_STATUS)
    if not nf.itens.exists():
        raise ValueError('NF-e sem itens não pode ser marcada como pronta.')
    validacao = validar_nfe_saida_para_emissao(nf)
    if tem_pendencias_bloqueantes(validacao):
        raise ValueError(MSG_MARCAR_PRONTA_PENDENCIAS)
    from django.conf import settings

    if getattr(settings, 'DANFE_BLOCK_EMISSION_IF_BFR_FAILS', True):
        from apps.fiscal.danfe_render import DanfeBfrRenderError, validar_danfe_bfr_para_emissao

        try:
            validar_danfe_bfr_para_emissao(nf)
        except DanfeBfrRenderError as exc:
            raise ValueError(str(exc)) from exc
    anterior = nf.status_conferencia
    agora = timezone.now()
    nf.status_conferencia = NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO
    nf.conferencia_marcada_pronta_em = agora
    nf.conferencia_marcada_pronta_por = usuario if usuario and getattr(usuario, 'is_authenticated', False) else None
    nf.conferencia_ultima_mensagem = 'NF-e marcada como pronta para emissão futura (sem SEFAZ).'
    nf.save(
        update_fields=[
            'status_conferencia',
            'conferencia_marcada_pronta_em',
            'conferencia_marcada_pronta_por',
            'conferencia_ultima_mensagem',
        ],
    )
    _registrar_evento(
        nf,
        tipo=NFeSaidaEvento.TipoEvento.PRONTA_PARA_EMISSAO,
        status_anterior=anterior or '',
        status_novo=nf.status_conferencia,
        resumo={
            'status_conferencia_anterior': anterior,
            'status_conferencia_novo': nf.status_conferencia,
            'total_pendencias': validacao.get('total_pendencias', 0),
            'total_alertas': validacao.get('total_alertas', 0),
        },
        observacao=nf.conferencia_ultima_mensagem,
        usuario=usuario,
    )
    from apps.fiscal.nfe_saida_conferencia import montar_conferencia_nfe_saida

    return {
        'prontidao': montar_payload_prontidao(nf, validacao=validacao),
        'validacao': validacao,
        'conferencia': montar_conferencia_nfe_saida(
            nf,
            modo='completo',
            validacao=validacao,
            incluir_checklist=True,
            usuario=usuario,
        ),
        'mensagem': 'NF-e marcada como pronta para emissão futura.',
    }
