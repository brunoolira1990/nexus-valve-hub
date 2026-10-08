"""Numeração diária PREFIXO-AAAAMMDD-NNNN (padrão Pedido de Compra)."""

from __future__ import annotations

from datetime import date, datetime

from django.db import IntegrityError, transaction


def coerce_data_referencia(data) -> date:
    if isinstance(data, date) and not isinstance(data, datetime):
        return data
    if isinstance(data, datetime):
        return data.date()
    if isinstance(data, str):
        return datetime.strptime(data[:10], '%Y-%m-%d').date()
    raise TypeError(f'data inválida para numeração: {type(data)!r}')


def formatar_numero_diario(prefix: str, data: date, sequencial: int) -> str:
    p = (prefix or '').strip().upper()
    return f'{p}-{data.strftime("%Y%m%d")}-{sequencial:04d}'


@transaction.atomic
def alocar_numero_diario(*, modelo_sequencia, filtros: dict, prefix: str, data) -> str:
    """
    Reserva o próximo número do dia com lock pessimista.
    `filtros` identifica a linha de sequência (ex.: tipo + data_referencia).
    """
    date_key = coerce_data_referencia(data)
    qs = modelo_sequencia.objects.select_for_update().filter(**filtros)
    seq = qs.first()
    if seq is None:
        try:
            modelo_sequencia.objects.create(**filtros, proximo_numero=1)
        except IntegrityError:
            pass
        seq = modelo_sequencia.objects.select_for_update().get(**filtros)
    n = seq.proximo_numero
    seq.proximo_numero = n + 1
    seq.save(update_fields=['proximo_numero'])
    return formatar_numero_diario(prefix, date_key, n)
