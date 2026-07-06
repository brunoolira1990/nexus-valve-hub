"""Rastreabilidade por item de conferência NF-e entrada (modo legado e split de corridas)."""

from __future__ import annotations

from collections import namedtuple
from decimal import Decimal

from apps.fiscal.models import ItemNFeEntradaConferencia, ItemNFeEntradaConferenciaCorridaSplit

TOLERANCIA_QUANTIDADE_SPLIT = Decimal('0.001')

LinhaRastreabilidade = namedtuple(
    'LinhaRastreabilidade',
    ['corrida', 'lote', 'quantidade', 'split', 'ordem'],
)


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def quantidade_alvo_item(item: ItemNFeEntradaConferencia) -> Decimal:
    """Mesma regra de quantidade_aplicar_item (estoque calculado ou qty NF)."""
    q = _dec(item.quantidade_estoque_calculada)
    if q > 0:
        return q
    return _dec(item.quantidade_nf)


def _splits_ordenados(item: ItemNFeEntradaConferencia) -> list[ItemNFeEntradaConferenciaCorridaSplit]:
    if hasattr(item, '_prefetched_objects_cache') and 'corridas_split' in item._prefetched_objects_cache:
        return sorted(item.corridas_split.all(), key=lambda s: (s.ordem, s.id))
    return list(item.corridas_split.order_by('ordem', 'id'))


def item_usa_split_corrida(item: ItemNFeEntradaConferencia) -> bool:
    return bool(_splits_ordenados(item))


def linhas_aplicacao_estoque(item: ItemNFeEntradaConferencia) -> list[LinhaRastreabilidade]:
    splits = _splits_ordenados(item)
    if splits:
        return [
            LinhaRastreabilidade(
                corrida=(s.corrida or '').strip(),
                lote=(s.lote or '').strip(),
                quantidade=_dec(s.quantidade),
                split=s,
                ordem=s.ordem,
            )
            for s in splits
        ]
    return [
        LinhaRastreabilidade(
            corrida=(item.corrida or '').strip(),
            lote=(item.lote or '').strip(),
            quantidade=quantidade_alvo_item(item),
            split=None,
            ordem=1,
        ),
    ]


def tem_rastreabilidade_item(item: ItemNFeEntradaConferencia) -> bool:
    if (item.corrida or '').strip() or (item.lote or '').strip():
        return True
    for s in _splits_ordenados(item):
        if (s.corrida or '').strip() or (s.lote or '').strip():
            return True
    return False


def validar_splits_quantidade(
    item: ItemNFeEntradaConferencia,
    splits_payload: list[dict] | None = None,
) -> list[str]:
    """Erros se splits existem e soma diverge da quantidade alvo."""
    if splits_payload is not None:
        if not splits_payload:
            return []
        erros: list[str] = []
        alvo = quantidade_alvo_item(item)
        soma = sum(_dec(row.get('quantidade') or 0) for row in splits_payload if isinstance(row, dict))
        if abs(soma - alvo) > TOLERANCIA_QUANTIDADE_SPLIT:
            erros.append(
                f'A soma das quantidades do split ({soma:.3f}) deve ser igual à quantidade do item ({alvo:.3f}).',
            )
        for idx, row in enumerate(splits_payload, start=1):
            if not isinstance(row, dict):
                continue
            ordem = int(row.get('ordem') or idx)
            if _dec(row.get('quantidade') or 0) <= 0:
                erros.append(f'Sub-linha {ordem}: quantidade deve ser maior que zero.')
        return erros

    splits = _splits_ordenados(item)
    if not splits:
        return []
    erros: list[str] = []
    alvo = quantidade_alvo_item(item)
    soma = sum(_dec(s.quantidade) for s in splits)
    if abs(soma - alvo) > TOLERANCIA_QUANTIDADE_SPLIT:
        erros.append(
            f'A soma das quantidades do split ({soma:.3f}) deve ser igual à quantidade do item ({alvo:.3f}).',
        )
    for s in splits:
        if _dec(s.quantidade) <= 0:
            erros.append(f'Sub-linha {s.ordem}: quantidade deve ser maior que zero.')
    return erros


def alertas_splits_parciais(item: ItemNFeEntradaConferencia) -> list[str]:
    """Alertas por sub-linha sem corrida/lote."""
    alertas: list[str] = []
    for s in _splits_ordenados(item):
        if not (s.corrida or '').strip() and not (s.lote or '').strip():
            alertas.append(f'Sub-linha {s.ordem} sem corrida/lote informado.')
    return alertas


def sincronizar_corridas_split_item(
    item: ItemNFeEntradaConferencia,
    splits_data: list[dict] | None,
) -> None:
    """Upsert de sub-linhas por ordem; limpa corrida/lote do pai quando há splits."""
    if item.status == ItemNFeEntradaConferencia.Status.IGNORADO:
        if splits_data is not None:
            item.corridas_split.all().delete()
        return

    if splits_data is None:
        return

    if not splits_data:
        item.corridas_split.all().delete()
        return

    ordens_payload: set[int] = set()
    for idx, row in enumerate(splits_data, start=1):
        if not isinstance(row, dict):
            continue
        ordem = int(row.get('ordem') or idx)
        ordens_payload.add(ordem)
        defaults = {
            'corrida': (row.get('corrida') or '').strip(),
            'lote': (row.get('lote') or '').strip(),
            'quantidade': _dec(row.get('quantidade') or 0),
        }
        ItemNFeEntradaConferenciaCorridaSplit.objects.update_or_create(
            item_conferencia=item,
            ordem=ordem,
            defaults=defaults,
        )

    item.corridas_split.exclude(ordem__in=ordens_payload).delete()
    item.corrida = ''
    item.lote = ''
    item.save(update_fields=['corrida', 'lote', 'atualizado_em'])
