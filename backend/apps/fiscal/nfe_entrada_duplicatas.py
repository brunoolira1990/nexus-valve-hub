"""Duplicatas/fatura da NF-e Entrada importada (XML) — cópia operacional para financeiro."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from apps.comercial.payment_terms import compute_due_dates
from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada

CENTAVO = Decimal('0.01')


def _round_money(v: Decimal | str | float | int) -> Decimal:
    return Decimal(str(v)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _parse_iso_date(value: str | date | None) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _normalize_dup_list(cobr: dict[str, Any]) -> list[dict[str, Any]]:
    dup_raw = cobr.get('dup')
    if not dup_raw:
        return []
    if isinstance(dup_raw, list):
        return [d for d in dup_raw if isinstance(d, dict)]
    if isinstance(dup_raw, dict):
        return [dup_raw]
    return []


def extrair_duplicatas_xml_nf_entrada(nf: NFeEntradaHistoricaImportada) -> list[dict[str, Any]]:
    """Extrai duplicatas do bloco cobr persistido em reforma_e_outros_json."""
    extra = nf.reforma_e_outros_json or {}
    cobr = extra.get('cobr')
    if not isinstance(cobr, dict):
        return []

    dups: list[dict[str, Any]] = []
    for idx, dup in enumerate(_normalize_dup_list(cobr), start=1):
        valor = _round_money(dup.get('vDup') or dup.get('valor') or 0)
        if valor <= 0:
            continue
        venc = _parse_iso_date(dup.get('dVenc') or dup.get('vencimento'))
        if not venc:
            continue
        num_raw = dup.get('nDup') or dup.get('numero') or idx
        try:
            numero = f'{int(str(num_raw).lstrip("0") or idx):03d}'
        except (TypeError, ValueError):
            numero = str(num_raw)
        dups.append({'numero': numero, 'vencimento': venc.isoformat(), 'valor': valor})
    return dups


def _parcelas_pedido_compra(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None,
) -> list[dict[str, Any]]:
    pedido = conferencia.pedido_compra if conferencia and conferencia.pedido_compra_id else None
    if not pedido:
        return []

    vencs = [v for v in (pedido.vencimentos_previstos or []) if v]
    if not vencs and pedido.dias_parcelas:
        base = nf.dh_emissao.date() if nf.dh_emissao else date.today()
        vencs = compute_due_dates(base, list(pedido.dias_parcelas))
    if not vencs:
        return []

    total = _round_money(nf.valor_total_nf or 0)
    if total <= 0:
        return []

    count = len(vencs)
    quota = _round_money(total / Decimal(count))
    parcelas: list[dict[str, Any]] = []
    accumulated = Decimal('0.00')
    for idx, due in enumerate(vencs, start=1):
        if idx < count:
            amount = quota
            accumulated += amount
        else:
            amount = _round_money(total - accumulated)
        if amount <= 0:
            continue
        parcelas.append({'numero': f'{idx:03d}', 'vencimento': due.isoformat(), 'valor': amount})
    return parcelas


def montar_parcelas_sugeridas_nf_entrada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> list[dict[str, Any]]:
    dups = extrair_duplicatas_xml_nf_entrada(nf)
    if dups:
        return [
            {
                'numero_parcela': int(d['numero']) if str(d['numero']).isdigit() else i,
                'vencimento': d['vencimento'],
                'valor': str(d['valor']),
                'observacoes': '',
            }
            for i, d in enumerate(dups, start=1)
        ]

    pedido_parcelas = _parcelas_pedido_compra(nf, conferencia)
    if pedido_parcelas:
        return [
            {
                'numero_parcela': int(d['numero']) if str(d['numero']).isdigit() else i,
                'vencimento': d['vencimento'],
                'valor': str(d['valor']),
                'observacoes': '',
            }
            for i, d in enumerate(pedido_parcelas, start=1)
        ]

    venc = nf.dh_emissao.date() if nf.dh_emissao else date.today()
    total = _round_money(nf.valor_total_nf or 0)
    if total <= 0:
        return []
    return [
        {
            'numero_parcela': 1,
            'vencimento': venc.isoformat(),
            'valor': str(total),
            'observacoes': '',
        },
    ]
