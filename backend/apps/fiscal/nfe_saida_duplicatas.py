"""Duplicatas comerciais/fiscais da NF-e Saída (XML/DANFE) — sem financeiro automático."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.comercial.payment_terms import compute_due_dates, parse_payment_condition
from apps.core.pdf.formatters import dec, format_currency_br, format_date_br
from apps.fiscal.models import NFeSaida


def _round_money(v: Decimal) -> Decimal:
    return dec(v).quantize(Decimal('0.01'))


def _parse_iso_date(value: str | date | None) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _resolve_dias_parcelas(nf: NFeSaida) -> list[int]:
    days = list(nf.dias_parcelas or [])
    if days:
        return days
    pedido = nf.pedido_venda if nf.pedido_venda_id else None
    if pedido and pedido.dias_parcelas:
        return list(pedido.dias_parcelas)
    texto = (nf.condicao_pagamento_texto or '').strip()
    if not texto and pedido:
        texto = (pedido.condicao_pagamento_texto or '').strip()
    if not texto:
        return []
    try:
        return parse_payment_condition(texto)
    except Exception:
        return []


def _pagamento_a_vista(days: list[int]) -> bool:
    return days == [0] or (len(days) == 1 and days[0] == 0)


def _resolve_vencimentos(nf: NFeSaida, days: list[int]) -> list[date]:
    vencs = [v for v in (nf.vencimentos_finais or []) if v]
    if vencs:
        return vencs

    pedido = nf.pedido_venda if nf.pedido_venda_id else None
    if pedido:
        prev = [v for v in (pedido.vencimentos_previstos or []) if v]
        if prev:
            return prev

    if not days or _pagamento_a_vista(days):
        return []

    base = nf.data or date.today()
    if pedido and pedido.data:
        base = pedido.data
    return compute_due_dates(base, days)


def _titulos_ja_preenchidos(nf: NFeSaida) -> bool:
    titulos = nf.titulos_receber or []
    if not titulos:
        return False
    for t in titulos:
        if not isinstance(t, dict):
            return False
        valor = _round_money(dec(t.get('valor', 0)))
        if valor <= 0:
            return False
        if not _parse_iso_date(t.get('vencimento')):
            return False
    return True


def gerar_duplicatas_nfe_saida(nf: NFeSaida) -> list[dict[str, Any]]:
    """
    Gera duplicatas a partir do pedido/faturamento/NF-e.
    Retorno: [{numero, vencimento (YYYY-MM-DD), valor (Decimal)}]
    """
    if _titulos_ja_preenchidos(nf):
        out: list[dict[str, Any]] = []
        for idx, t in enumerate(nf.titulos_receber or [], start=1):
            if not isinstance(t, dict):
                continue
            valor = _round_money(dec(t.get('valor', 0)))
            if valor <= 0:
                continue
            venc = _parse_iso_date(t.get('vencimento'))
            if not venc:
                continue
            parcela = t.get('parcela') or idx
            try:
                numero = f'{int(parcela):03d}'
            except (TypeError, ValueError):
                numero = str(parcela)
            out.append({'numero': numero, 'vencimento': venc.isoformat(), 'valor': valor})
        return out

    days = _resolve_dias_parcelas(nf)
    if _pagamento_a_vista(days):
        return []

    vencs = _resolve_vencimentos(nf, days)
    if not vencs:
        return []

    total = _round_money(dec(nf.valor_total))
    if total <= 0:
        return []

    count = len(vencs)
    quota = _round_money(total / Decimal(count))
    dups: list[dict[str, Any]] = []
    accumulated = Decimal('0.00')

    for idx, due in enumerate(vencs, start=1):
        if idx < count:
            amount = quota
            accumulated += amount
        else:
            amount = _round_money(total - accumulated)
        if amount <= 0:
            continue
        dups.append({'numero': f'{idx:03d}', 'vencimento': due.isoformat(), 'valor': amount})
    return dups


def aplicar_duplicatas_nfe_saida(nf: NFeSaida, *, save: bool = True) -> list[dict[str, Any]]:
    """Persiste duplicatas em titulos_receber/vencimentos_finais sem gerar financeiro."""
    dups = gerar_duplicatas_nfe_saida(nf)
    titulos: list[dict[str, Any]] = []
    vencs: list[date] = []

    days = _resolve_dias_parcelas(nf)
    for d in dups:
        venc = _parse_iso_date(d['vencimento'])
        if not venc:
            continue
        vencs.append(venc)
        dias = (venc - nf.data).days if nf.data else 0
        if not dias and days and len(days) >= len(titulos):
            dias = int(days[len(titulos)])
        titulos.append(
            {
                'parcela': d['numero'],
                'dias': dias,
                'vencimento': venc.isoformat(),
                'valor': str(d['valor']),
            },
        )

    nf.titulos_receber = titulos
    nf.vencimentos_finais = vencs
    nf.quantidade_parcelas = len(titulos)
    if save and nf.pk:
        nf.save(
            update_fields=['titulos_receber', 'vencimentos_finais', 'quantidade_parcelas'],
        )
    return dups


def assegurar_duplicatas_nfe_saida(nf: NFeSaida, *, save: bool = True) -> list[dict[str, Any]]:
    """Garante duplicatas calculadas e persistidas quando aplicável."""
    if _titulos_ja_preenchidos(nf):
        return gerar_duplicatas_nfe_saida(nf)
    return aplicar_duplicatas_nfe_saida(nf, save=save)


def duplicatas_para_xml(nf: NFeSaida) -> list[dict[str, str]]:
    """Payload simplificado para serialização XML."""
    dups = assegurar_duplicatas_nfe_saida(nf, save=bool(nf.pk))
    return [
        {
            'numero': d['numero'],
            'vencimento': d['vencimento'],
            'valor': str(d['valor']),
        }
        for d in dups
    ]


def numero_fatura_nfe(nf: NFeSaida) -> str:
    if nf.faturamento_pedido_venda_id and nf.faturamento_pedido_venda:
        num = (nf.faturamento_pedido_venda.numero_faturamento or '').strip()
        if num:
            return num[:60]
    num_nf = (nf.numero or '').strip()
    if num_nf and not num_nf.upper().startswith('RASCUNHO'):
        return num_nf[:60]
    return str(nf.pk or '1')[:60]


def duplicatas_nfe_para_api(nf: NFeSaida) -> list[dict[str, str]]:
    """Representação amigável para API/UI — não é título financeiro."""
    rows: list[dict[str, str]] = []
    for d in assegurar_duplicatas_nfe_saida(nf, save=bool(nf.pk)):
        venc = _parse_iso_date(d['vencimento'])
        valor = _round_money(dec(d['valor']))
        rows.append(
            {
                'numero': d['numero'],
                'vencimento': d['vencimento'],
                'vencimento_formatado': format_date_br(venc) if venc else '—',
                'valor': str(valor),
                'valor_formatado': format_currency_br(valor),
            },
        )
    return rows


def formatar_vencimento_duplicata_exibicao(value: str | date | None) -> str:
    venc = _parse_iso_date(value) if not hasattr(value, 'strftime') else value
    if venc:
        return format_date_br(venc)
    return str(value or '—')


def formatar_numero_duplicata_exibicao(value: str | int | None, fallback: int = 1) -> str:
    raw = value if value is not None else fallback
    try:
        return f'{int(raw):03d}'
    except (TypeError, ValueError):
        return str(raw)
