"""Fase 2A — estoque físico por peça a partir da composição validada na conferência.

Suporta dois tipos de composição:
- BARRA_M: cada barra física vira um EstoqueBarra com saldo em metros.
- PECA_KG: cada peça/chapa física vira um EstoqueBarra com saldo em kg.

A unidade base fica em EstoqueBarra.unidade_base ('M' ou 'KG') e o saldo na
unidade base fica em EstoqueBarra.saldo (com quantidade_original correspondente).
Os campos *_m são espelhados apenas quando a unidade base é M, por compatibilidade.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.db.models import Sum

from apps.fiscal.composicao_fisica_conferencia import (
    expandir_barras_fisicas_composicao,
    expandir_pecas_fisicas_composicao,
    item_controla_composicao_fisica,
    item_e_peca_kg,
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
    tipo_composicao: str
    unidade_base: str
    quantidade_original: str
    saldo: str
    comprimento_original_m: str | None
    saldo_m: str | None
    status: str


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))


def _fmt_qty(v) -> str:
    return f'{_dec(v):.3f}'


def _fmt_qty_opt(v) -> str | None:
    return None if v is None else _fmt_qty(v)


def gerar_codigo_interno_barra(
    item_conferencia_id: int,
    equivalencia_id: int,
    ordem_equiv: int,
    sequencia_grupo: int,
) -> str:
    return f'EB-{item_conferencia_id}-{ordem_equiv:03d}-{sequencia_grupo:03d}-{equivalencia_id}'


def _status_inicial_barra(quantidade: Decimal) -> str:
    if quantidade <= 0:
        return EstoqueBarra.Status.CANCELADA
    return EstoqueBarra.Status.DISPONIVEL


def _barra_tem_consumo(barra: EstoqueBarra) -> bool:
    if barra.status in (EstoqueBarra.Status.PARCIAL, EstoqueBarra.Status.CONSUMIDA):
        return True
    return _dec(barra.saldo) < _dec(barra.quantidade_original)


def _tipo_e_unidade(item: ItemNFeEntradaConferencia) -> tuple[str, str]:
    if item_e_peca_kg(item):
        return EstoqueBarra.TipoComposicao.PECA_KG, 'KG'
    return EstoqueBarra.TipoComposicao.BARRA_M, 'M'


def _expandir_unidades_fisicas(
    item: ItemNFeEntradaConferencia,
    equiv: ItemNFeEntradaConferenciaEquivalencia,
) -> list[Decimal]:
    if item_e_peca_kg(item):
        return expandir_pecas_fisicas_composicao(equiv)
    return expandir_barras_fisicas_composicao(equiv)


def _montar_metadata_barra(
    item: ItemNFeEntradaConferencia,
    equiv: ItemNFeEntradaConferenciaEquivalencia,
    *,
    sequencia_grupo: int,
    tipo_composicao: str,
    unidade_base: str,
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
        'tipo_composicao': tipo_composicao,
        'unidade_base': unidade_base,
        'qtd_barras_grupo': equiv.qtd_barras,
        'comprimento_unitario_m': (
            str(equiv.comprimento_unitario_m) if equiv.comprimento_unitario_m is not None else None
        ),
        'peso_real_kg': str(equiv.peso_kg) if equiv.peso_kg is not None else None,
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
    """Soma saldo em M das barras disponíveis (BARRA_M)."""
    return _saldo_produto_por_tipo(
        produto_id,
        tipo=EstoqueBarra.TipoComposicao.BARRA_M,
        incluir_parcial=incluir_parcial,
    )


def saldo_pecas_produto_kg(
    produto_id: int,
    *,
    incluir_parcial: bool = True,
) -> Decimal:
    """Soma saldo em KG das peças/chapas disponíveis (PECA_KG)."""
    return _saldo_produto_por_tipo(
        produto_id,
        tipo=EstoqueBarra.TipoComposicao.PECA_KG,
        incluir_parcial=incluir_parcial,
    )


def _saldo_produto_por_tipo(
    produto_id: int,
    *,
    tipo: str,
    incluir_parcial: bool = True,
) -> Decimal:
    statuses = [EstoqueBarra.Status.DISPONIVEL]
    if incluir_parcial:
        statuses.append(EstoqueBarra.Status.PARCIAL)
    total = (
        EstoqueBarra.objects.filter(
            produto_id=produto_id,
            tipo_composicao=tipo,
            status__in=statuses,
        ).aggregate(total=Sum('saldo'))['total']
    )
    return _dec(total)


def _cancelar_barra(barra: EstoqueBarra) -> None:
    if _barra_tem_consumo(barra):
        raise ValueError(
            f'Peça {barra.codigo_interno_barra} já possui consumo; não é possível cancelar.',
        )
    barra.saldo = Decimal('0')
    if barra.unidade_base == 'M':
        barra.saldo_m = Decimal('0')
    barra.status = EstoqueBarra.Status.CANCELADA
    barra.save(update_fields=['saldo', 'saldo_m', 'status', 'atualizado_em'])


@transaction.atomic
def estornar_barras_composicao_item(item: ItemNFeEntradaConferencia) -> int:
    """Cancela peças do item quando a conferência é revertida (sem consumo prévio)."""
    canceladas = 0
    for barra in item.estoque_barras.select_for_update().exclude(
        status=EstoqueBarra.Status.CANCELADA,
    ):
        _cancelar_barra(barra)
        canceladas += 1
    return canceladas


def _aplicar_valores_barra(
    barra: EstoqueBarra,
    *,
    quantidade: Decimal,
    unidade_base: str,
) -> None:
    barra.quantidade_original = quantidade
    barra.saldo = quantidade
    if unidade_base == 'M':
        barra.comprimento_original_m = quantidade
        barra.saldo_m = quantidade
    else:
        barra.comprimento_original_m = None
        barra.saldo_m = None


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
    Cria EstoqueBarra individual para cada unidade física (barra em M ou peça em KG).
    Idempotente por (equivalencia_entrada, sequencia_grupo).
    """
    if not item_controla_composicao_fisica(item):
        return []

    equivs = list(item.equivalencias.order_by('ordem', 'id'))
    if not equivs:
        return []

    tipo_composicao, unidade_base = _tipo_e_unidade(item)
    resultado: list[BarraAplicadaDict] = []
    chaves_ativas: set[tuple[int, int]] = set()

    for equiv in equivs:
        quantidades = _expandir_unidades_fisicas(item, equiv)
        if not quantidades:
            continue
        for seq, quantidade in enumerate(quantidades, start=1):
            chaves_ativas.add((equiv.id, seq))
            metadata = _montar_metadata_barra(
                item,
                equiv,
                sequencia_grupo=seq,
                tipo_composicao=tipo_composicao,
                unidade_base=unidade_base,
                nf_numero=nf_numero,
                conferencia_id=conferencia_id,
            )
            codigo = gerar_codigo_interno_barra(item.id, equiv.id, equiv.ordem, seq)

            defaults = {
                'produto_id': item.produto_id,
                'item_conferencia_id': item.id,
                'nfe_entrada_historica_id': nfe_entrada_historica_id,
                'fornecedor_id': fornecedor_id,
                'codigo_interno_barra': codigo,
                'tipo_composicao': tipo_composicao,
                'unidade_base': unidade_base,
                'quantidade_original': quantidade,
                'saldo': quantidade,
                'comprimento_original_m': quantidade if unidade_base == 'M' else None,
                'saldo_m': quantidade if unidade_base == 'M' else None,
                'status': _status_inicial_barra(quantidade),
                'origem': EstoqueBarra.Origem.CONFERENCIA_NFE_ENTRADA,
                'metadata': metadata,
            }

            barra, created = EstoqueBarra.objects.select_for_update().get_or_create(
                equivalencia_entrada_id=equiv.id,
                sequencia_grupo=seq,
                defaults=defaults,
            )

            if not created:
                if _barra_tem_consumo(barra):
                    if _dec(barra.quantidade_original) != quantidade or _dec(barra.saldo) != quantidade:
                        raise ValueError(
                            f'Peça {barra.codigo_interno_barra} já utilizada; '
                            'não é possível alterar a composição.',
                        )
                elif barra.status == EstoqueBarra.Status.CANCELADA:
                    barra.tipo_composicao = tipo_composicao
                    barra.unidade_base = unidade_base
                    _aplicar_valores_barra(barra, quantidade=quantidade, unidade_base=unidade_base)
                    barra.status = _status_inicial_barra(quantidade)
                    barra.metadata = metadata
                    barra.save(
                        update_fields=[
                            'tipo_composicao',
                            'unidade_base',
                            'quantidade_original',
                            'saldo',
                            'comprimento_original_m',
                            'saldo_m',
                            'status',
                            'metadata',
                            'atualizado_em',
                        ],
                    )
                elif _dec(barra.quantidade_original) != quantidade or barra.tipo_composicao != tipo_composicao:
                    barra.tipo_composicao = tipo_composicao
                    barra.unidade_base = unidade_base
                    _aplicar_valores_barra(barra, quantidade=quantidade, unidade_base=unidade_base)
                    barra.metadata = metadata
                    barra.save(
                        update_fields=[
                            'tipo_composicao',
                            'unidade_base',
                            'quantidade_original',
                            'saldo',
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
                    'tipo_composicao': barra.tipo_composicao,
                    'unidade_base': barra.unidade_base,
                    'quantidade_original': _fmt_qty(barra.quantidade_original),
                    'saldo': _fmt_qty(barra.saldo),
                    'comprimento_original_m': _fmt_qty_opt(barra.comprimento_original_m),
                    'saldo_m': _fmt_qty_opt(barra.saldo_m),
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
