"""Fase 2A — estoque físico por barra a partir da composição validada na conferência."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.db.models import Sum

from apps.fiscal.composicao_fisica_conferencia import (
    expandir_barras_fisicas_composicao,
    item_controla_composicao_fisica,
    montar_auditoria_composicao_fisica,
)
from apps.fiscal.models import (
    EstoqueBarra,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaConferenciaEquivalencia,
)


class BarraAplicadaDict(TypedDict):
    estoque_barra_id: int
    codigo_interno_barra: str
    ordem: int
    sequencia_grupo: int
    comprimento_original_m: str
    saldo_m: str
    status: str


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))


def _fmt_qty(v: Decimal) -> str:
    return f'{v:.3f}'


def gerar_codigo_interno_barra(
    item_conferencia_id: int,
    equivalencia_id: int,
    ordem_equiv: int,
    sequencia_grupo: int,
) -> str:
    return f'EB-{item_conferencia_id}-{ordem_equiv:03d}-{sequencia_grupo:03d}-{equivalencia_id}'


def _status_inicial_barra(metros: Decimal) -> str:
    if metros <= 0:
        return EstoqueBarra.Status.CANCELADA
    return EstoqueBarra.Status.DISPONIVEL


def _barra_tem_consumo(barra: EstoqueBarra) -> bool:
    if barra.status in (EstoqueBarra.Status.PARCIAL, EstoqueBarra.Status.CONSUMIDA):
        return True
    return _dec(barra.saldo_m) < _dec(barra.comprimento_original_m)


def _montar_metadata_barra(
    item: ItemNFeEntradaConferencia,
    equiv: ItemNFeEntradaConferenciaEquivalencia,
    *,
    sequencia_grupo: int,
    nf_numero: str = '',
    conferencia_id: int | None = None,
) -> dict[str, Any]:
    equivs = list(item.equivalencias.order_by('ordem', 'id'))
    auditoria = item.conversao_estoque_auditoria
    if not auditoria and equivs:
        auditoria = montar_auditoria_composicao_fisica(item, equivs)
    return {
        'conferencia_id': conferencia_id,
        'item_conferencia_id': item.id,
        'equivalencia_ordem': equiv.ordem,
        'equivalencia_id': equiv.id,
        'sequencia_grupo': sequencia_grupo,
        'qtd_barras_grupo': equiv.qtd_barras,
        'comprimento_unitario_m': (
            str(equiv.comprimento_unitario_m) if equiv.comprimento_unitario_m is not None else None
        ),
        'nf_numero': nf_numero,
        'conversao_estoque_auditoria': auditoria,
        'unidade_nf': item.unidade_nf,
        'quantidade_nf': str(item.quantidade_nf) if item.quantidade_nf is not None else None,
    }


def saldo_barras_produto_metros(
    produto_id: int,
    *,
    incluir_parcial: bool = True,
) -> Decimal:
    """Soma saldo em M das barras disponíveis (e parciais, se solicitado)."""
    statuses = [EstoqueBarra.Status.DISPONIVEL]
    if incluir_parcial:
        statuses.append(EstoqueBarra.Status.PARCIAL)
    total = (
        EstoqueBarra.objects.filter(produto_id=produto_id, status__in=statuses).aggregate(
            total=Sum('saldo_m'),
        )['total']
    )
    return _dec(total)


def _cancelar_barra(barra: EstoqueBarra) -> None:
    if _barra_tem_consumo(barra):
        raise ValueError(
            f'Barra {barra.codigo_interno_barra} já possui consumo; não é possível cancelar.',
        )
    barra.saldo_m = Decimal('0')
    barra.status = EstoqueBarra.Status.CANCELADA
    barra.save(update_fields=['saldo_m', 'status', 'atualizado_em'])


@transaction.atomic
def estornar_barras_composicao_item(item: ItemNFeEntradaConferencia) -> int:
    """Cancela barras do item quando a conferência é revertida (sem consumo prévio)."""
    canceladas = 0
    for barra in item.estoque_barras.select_for_update().exclude(
        status=EstoqueBarra.Status.CANCELADA,
    ):
        _cancelar_barra(barra)
        canceladas += 1
    return canceladas


@transaction.atomic
def aplicar_estoque_barras_composicao_conferencia(
    item: ItemNFeEntradaConferencia,
    *,
    fornecedor_id: int | None,
    nfe_entrada_historica_id: int | None,
    nf_numero: str = '',
    conferencia_id: int | None = None,
) -> list[BarraAplicadaDict]:
    """
    Cria EstoqueBarra individual para cada barra física (expansão de qtd_barras × comprimento).
    Idempotente por (equivalencia_entrada, sequencia_grupo).
    """
    if not item_controla_composicao_fisica(item):
        return []

    equivs = list(item.equivalencias.order_by('ordem', 'id'))
    if not equivs:
        return []

    resultado: list[BarraAplicadaDict] = []
    chaves_ativas: set[tuple[int, int]] = set()

    for equiv in equivs:
        comprimentos = expandir_barras_fisicas_composicao(equiv)
        if not comprimentos:
            continue
        for seq, metros in enumerate(comprimentos, start=1):
            chaves_ativas.add((equiv.id, seq))
            metadata = _montar_metadata_barra(
                item,
                equiv,
                sequencia_grupo=seq,
                nf_numero=nf_numero,
                conferencia_id=conferencia_id,
            )
            codigo = gerar_codigo_interno_barra(item.id, equiv.id, equiv.ordem, seq)

            barra, created = EstoqueBarra.objects.select_for_update().get_or_create(
                equivalencia_entrada_id=equiv.id,
                sequencia_grupo=seq,
                defaults={
                    'produto_id': item.produto_id,
                    'item_conferencia_id': item.id,
                    'nfe_entrada_historica_id': nfe_entrada_historica_id,
                    'fornecedor_id': fornecedor_id,
                    'codigo_interno_barra': codigo,
                    'comprimento_original_m': metros,
                    'saldo_m': metros,
                    'unidade_base': 'M',
                    'status': _status_inicial_barra(metros),
                    'origem': EstoqueBarra.Origem.CONFERENCIA_NFE_ENTRADA,
                    'metadata': metadata,
                },
            )

            if not created:
                if _barra_tem_consumo(barra):
                    if barra.comprimento_original_m != metros or barra.saldo_m != metros:
                        raise ValueError(
                            f'Barra {barra.codigo_interno_barra} já utilizada; '
                            'não é possível alterar a composição.',
                        )
                elif barra.status == EstoqueBarra.Status.CANCELADA:
                    barra.comprimento_original_m = metros
                    barra.saldo_m = metros
                    barra.status = _status_inicial_barra(metros)
                    barra.metadata = metadata
                    barra.save(
                        update_fields=[
                            'comprimento_original_m',
                            'saldo_m',
                            'status',
                            'metadata',
                            'atualizado_em',
                        ],
                    )
                elif barra.comprimento_original_m != metros:
                    barra.comprimento_original_m = metros
                    barra.saldo_m = metros
                    barra.metadata = metadata
                    barra.save(
                        update_fields=[
                            'comprimento_original_m',
                            'saldo_m',
                            'metadata',
                            'atualizado_em',
                        ],
                    )

            resultado.append(
                {
                    'estoque_barra_id': barra.id,
                    'codigo_interno_barra': barra.codigo_interno_barra,
                    'ordem': equiv.ordem,
                    'sequencia_grupo': seq,
                    'comprimento_original_m': _fmt_qty(barra.comprimento_original_m),
                    'saldo_m': _fmt_qty(barra.saldo_m),
                    'status': barra.status,
                },
            )

    for barra in item.estoque_barras.select_for_update().exclude(
        status=EstoqueBarra.Status.CANCELADA,
    ):
        chave = (barra.equivalencia_entrada_id, barra.sequencia_grupo)
        if chave not in chaves_ativas:
            _cancelar_barra(barra)

    return resultado
