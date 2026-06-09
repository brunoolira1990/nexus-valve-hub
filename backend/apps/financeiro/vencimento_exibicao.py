"""Exibição de vencimento em relatórios financeiros — ERP 4.0.14.8."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.utils import timezone

from apps.financeiro.models import ParcelaFinanceira, TituloFinanceiro
from apps.financeiro.status import CENTAVO


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def vencimento_operacional_titulo(
    titulo: TituloFinanceiro,
    *,
    hoje: date | None = None,
    incluir_historico: bool = False,
) -> tuple[date | None, str | None]:
    """
    Retorna (data_vencimento, aviso_inconsistencia).
    Prioriza próximo vencimento em aberto nas parcelas; senão data_vencimento do título.
    """
    hoje = hoje or timezone.localdate()
    parcelas = list(
        titulo.parcelas.all().order_by('numero_parcela').values(
            'data_vencimento',
            'valor_aberto',
            'status',
        ),
    )
    aberto_st = {
        TituloFinanceiro.Status.EM_ABERTO,
        TituloFinanceiro.Status.VENCIDO,
        TituloFinanceiro.Status.PARCIALMENTE_RECEBIDO,
        TituloFinanceiro.Status.PARCIALMENTE_PAGO,
    }

    if parcelas:
        candidatas: list[date] = []
        for p in parcelas:
            dv = _parse_date(p['data_vencimento'])
            if not dv:
                continue
            saldo = p.get('valor_aberto') or Decimal('0')
            st = p.get('status') or ''
            if saldo > CENTAVO or st in aberto_st:
                candidatas.append(dv)
            elif incluir_historico:
                candidatas.append(dv)
        if candidatas:
            return min(candidatas), None
        if incluir_historico:
            datas = [_parse_date(p['data_vencimento']) for p in parcelas]
            datas_ok = [d for d in datas if d]
            if datas_ok:
                return min(datas_ok), None

    dv_titulo = titulo.data_vencimento
    if dv_titulo:
        return dv_titulo, None
    return None, 'Vencimento não informado.'


def vencimento_exibicao_titulo(
    titulo: TituloFinanceiro,
    *,
    hoje: date | None = None,
    incluir_historico: bool = False,
) -> dict:
    dv, aviso = vencimento_operacional_titulo(
        titulo,
        hoje=hoje,
        incluir_historico=incluir_historico,
    )
    label = None
    if dv and titulo.parcelas.count() > 1:
        hoje = hoje or timezone.localdate()
        if (titulo.valor_aberto or Decimal('0')) > CENTAVO and dv >= hoje:
            label = f'Próx.: {dv.isoformat()}'
    return {
        'vencimento': dv.isoformat() if dv else None,
        'vencimento_label': label,
        'vencimento_ausente': aviso,
    }
