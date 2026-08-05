"""ERP 4.0.10.2.2 — conferência segura de CT-e importado (sem financeiro/expedição/rateio)."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.fiscal.dfe_classificacao import (
    eh_documento_autorizado,
    eh_documento_homologacao,
    eh_documento_producao,
    metadados_classificacao_dfe,
    pode_entrar_apuracao,
)
from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeEntradaHistoricaImportada,
    NFeSaidaHistoricaImportada,
)


class ConferenciaCteErro(ValueError):
    pass


def _status_inicial_importacao(*, cancelado: bool, cstat: str) -> str:
    if cancelado:
        return CTeHistoricoImportado.StatusConferencia.CANCELADO
    if (cstat or '').strip() in ('100', '100.0'):
        return CTeHistoricoImportado.StatusConferencia.PROCESSADO
    return CTeHistoricoImportado.StatusConferencia.IMPORTADO


def status_conferencia_apos_importacao(cte: CTeHistoricoImportado) -> str:
    return _status_inicial_importacao(cancelado=bool(cte.cancelado), cstat=cte.cstat or '')


def pode_marcar_conferido_operacional(cte: CTeHistoricoImportado) -> tuple[bool, str]:
    if eh_documento_homologacao(cte):
        return False, 'CT-e de homologação não pode ser conferido para uso operacional.'
    if cte.cancelado or cte.status_conferencia == CTeHistoricoImportado.StatusConferencia.CANCELADO:
        return False, 'CT-e cancelado não pode ser conferido operacionalmente.'
    if cte.status_conferencia == CTeHistoricoImportado.StatusConferencia.IGNORADO:
        return False, 'CT-e ignorado operacionalmente. Reabra na base antes de conferir.'
    if not eh_documento_producao(cte):
        return False, 'Apenas CT-e de produção pode ser conferido operacionalmente.'
    if not eh_documento_autorizado(cte):
        return False, 'CT-e deve estar autorizado (cStat 100) para conferência operacional.'
    return True, ''


def queryset_cte_entrada_operacional() -> QuerySet[CTeHistoricoImportado]:
    """CT-es aptos à tela CT-e Entrada (conferidos, produção, sem efeito automático)."""
    return (
        CTeHistoricoImportado.objects.filter(
            apto_operacional=True,
            cancelado=False,
            ignorado_operacionalmente=False,
            status_conferencia__in=[
                CTeHistoricoImportado.StatusConferencia.CONFERIDO,
                CTeHistoricoImportado.StatusConferencia.PREPARADO,
            ],
        )
        .filter(Q(tp_amb='1') | Q(tp_amb='') | Q(tp_amb__isnull=True))
        .filter(Q(cstat='100') | Q(cstat__iexact='100'))
        .select_related('transportadora', 'empresa_tomadora', 'conferido_por')
    )


def resolver_documentos_vinculados(cte: CTeHistoricoImportado) -> list[dict[str, Any]]:
    from apps.fiscal.models import NFeEntrada

    linhas: list[dict[str, Any]] = []
    for chave in cte.chaves_nfe_vinculadas or []:
        ch = str(chave).strip()
        if not ch:
            continue
        entrada = NFeEntradaHistoricaImportada.objects.filter(chave_acesso=ch).first()
        if entrada:
            op = NFeEntrada.objects.filter(chave_acesso=ch).only('id', 'numero', 'status_operacional').first()
            linhas.append(
                {
                    'chave_acesso': ch,
                    'localizada': True,
                    'origem': 'BASE_NFE_ENTRADA_IMPORTADA',
                    'origem_label': 'Base NF-e Entrada Importada',
                    'documento_id': entrada.id,
                    'numero': entrada.numero,
                    'serie': entrada.serie,
                    'rota_detalhe': f'/nfe-entrada-historica-importada?id={entrada.id}',
                    'nfe_entrada_operacional_id': op.id if op else None,
                    'nfe_entrada_status': op.status_operacional if op else None,
                    'rota_operacional': f'/nfe-entrada?detalhe={op.id}' if op else None,
                },
            )
            continue
        saida = NFeSaidaHistoricaImportada.objects.filter(chave_acesso=ch).first()
        if saida:
            linhas.append(
                {
                    'chave_acesso': ch,
                    'localizada': True,
                    'origem': 'BASE_NFE_SAIDA_IMPORTADA',
                    'origem_label': 'Base NF-e Saída Importada',
                    'documento_id': saida.id,
                    'numero': saida.numero,
                    'serie': saida.serie,
                    'rota_detalhe': f'/nfe-historica-importada?id={saida.id}',
                    'nfe_entrada_operacional_id': None,
                    'nfe_entrada_status': None,
                    'rota_operacional': None,
                },
            )
            continue
        op = NFeEntrada.objects.filter(chave_acesso=ch).only('id', 'numero', 'status_operacional').first()
        if op:
            linhas.append(
                {
                    'chave_acesso': ch,
                    'localizada': True,
                    'origem': 'NFE_ENTRADA_OPERACIONAL',
                    'origem_label': 'NF-e Entrada operacional',
                    'documento_id': op.id,
                    'numero': op.numero,
                    'serie': getattr(op, 'serie', '') or '',
                    'rota_detalhe': f'/nfe-entrada?detalhe={op.id}',
                    'nfe_entrada_operacional_id': op.id,
                    'nfe_entrada_status': op.status_operacional,
                    'rota_operacional': f'/nfe-entrada?detalhe={op.id}',
                },
            )
            continue
        linhas.append(
            {
                'chave_acesso': ch,
                'localizada': False,
                'origem': None,
                'origem_label': 'NF-e referenciada não localizada na base',
                'documento_id': None,
                'numero': None,
                'serie': None,
                'rota_detalhe': None,
                'nfe_entrada_operacional_id': None,
                'nfe_entrada_status': None,
                'rota_operacional': None,
            },
        )
    return linhas


def serializar_resposta_conferencia(cte: CTeHistoricoImportado) -> dict[str, Any]:
    conf_st = cte.status_conferencia
    return {
        'id': cte.id,
        'status_conferencia': conf_st,
        'apto_operacional': cte.apto_operacional,
        'conferido_em': cte.conferido_em.isoformat() if cte.conferido_em else None,
        'conferido_por_id': cte.conferido_por_id,
        'conferido_por_nome': (
            cte.conferido_por.get_full_name() or cte.conferido_por.username
            if cte.conferido_por_id
            else ''
        ),
        'observacao_conferencia': cte.observacao_conferencia,
        'divergencia_motivo': cte.divergencia_motivo,
        'ignorado_operacionalmente': cte.ignorado_operacionalmente,
        'checklist_conferencia_json': cte.checklist_conferencia_json or {},
        'classificacao_dfe': metadados_classificacao_dfe(
            cte,
            conferencia_status=conf_st,
            incluir_canceladas=bool(cte.cancelado),
        ),
        'pode_entrar_apuracao': pode_entrar_apuracao(cte),
        'documentos_vinculados_resumo': resolver_documentos_vinculados(cte),
        'regra_fiscal': _regra_fiscal_cte_safe(cte),
    }


def _regra_fiscal_cte_safe(cte: CTeHistoricoImportado) -> dict[str, Any]:
    from apps.fiscal.cte_regra_fiscal import avaliar_regra_fiscal_cte

    try:
        return avaliar_regra_fiscal_cte(cte)
    except Exception:
        return {'status': 'SEM_REGRA', 'mensagem': 'Falha ao avaliar regra fiscal do CT-e.', 'pode_conferir': False}


def conferir_cte_importado(
    cte: CTeHistoricoImportado,
    usuario,
    dados: dict[str, Any] | None = None,
) -> CTeHistoricoImportado:
    ok, msg = pode_marcar_conferido_operacional(cte)
    if not ok:
        raise ConferenciaCteErro(msg)

    from apps.fiscal.cte_regra_fiscal import exigir_regra_fiscal_cte_ok

    try:
        exigir_regra_fiscal_cte_ok(cte)
    except ValueError as exc:
        raise ConferenciaCteErro(str(exc)) from exc

    payload = dados or {}
    checklist = {
        'confirmar_tomador': bool(payload.get('confirmar_tomador')),
        'confirmar_transportadora': bool(payload.get('confirmar_transportadora')),
        'confirmar_valores': bool(payload.get('confirmar_valores')),
        'confirmar_documentos_referenciados': bool(payload.get('confirmar_documentos_referenciados')),
    }
    if not all(checklist.values()):
        raise ConferenciaCteErro('Confirme todos os itens do checklist antes de marcar como conferido.')

    agora = timezone.now()
    cte.status_conferencia = CTeHistoricoImportado.StatusConferencia.CONFERIDO
    cte.apto_operacional = True
    cte.ignorado_operacionalmente = False
    cte.divergencia_motivo = ''
    cte.conferido_em = agora
    cte.conferido_por = usuario
    cte.observacao_conferencia = str(payload.get('observacao') or '').strip()
    cte.checklist_conferencia_json = checklist
    cte.save(
        update_fields=[
            'status_conferencia',
            'apto_operacional',
            'ignorado_operacionalmente',
            'divergencia_motivo',
            'conferido_em',
            'conferido_por',
            'observacao_conferencia',
            'checklist_conferencia_json',
        ],
    )
    return cte


def marcar_cte_importado_divergente(
    cte: CTeHistoricoImportado,
    usuario,
    *,
    motivo: str,
    observacao: str = '',
) -> CTeHistoricoImportado:
    motivo = (motivo or '').strip()
    if not motivo:
        raise ConferenciaCteErro('Informe o motivo da divergência.')

    cte.status_conferencia = CTeHistoricoImportado.StatusConferencia.DIVERGENTE
    cte.apto_operacional = False
    cte.ignorado_operacionalmente = False
    cte.divergencia_motivo = motivo[:500]
    cte.observacao_conferencia = (observacao or '').strip()
    cte.conferido_em = timezone.now()
    cte.conferido_por = usuario
    cte.save(
        update_fields=[
            'status_conferencia',
            'apto_operacional',
            'ignorado_operacionalmente',
            'divergencia_motivo',
            'observacao_conferencia',
            'conferido_em',
            'conferido_por',
        ],
    )
    return cte


def ignorar_cte_importado_operacionalmente(
    cte: CTeHistoricoImportado,
    usuario,
    *,
    motivo: str,
    observacao: str = '',
) -> CTeHistoricoImportado:
    motivo = (motivo or '').strip()
    if not motivo:
        raise ConferenciaCteErro('Informe o motivo para ignorar operacionalmente.')

    cte.status_conferencia = CTeHistoricoImportado.StatusConferencia.IGNORADO
    cte.apto_operacional = False
    cte.ignorado_operacionalmente = True
    cte.divergencia_motivo = ''
    cte.observacao_conferencia = f'{motivo}\n{(observacao or "").strip()}'.strip()[:2000]
    cte.conferido_em = timezone.now()
    cte.conferido_por = usuario
    cte.save(
        update_fields=[
            'status_conferencia',
            'apto_operacional',
            'ignorado_operacionalmente',
            'divergencia_motivo',
            'observacao_conferencia',
            'conferido_em',
            'conferido_por',
        ],
    )
    return cte
