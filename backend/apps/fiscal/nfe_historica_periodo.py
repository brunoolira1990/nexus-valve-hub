"""Resolução de intervalo de datas a partir de query params (mês, trimestre ou intervalo)."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date

from django.http import QueryDict


class PeriodoInvalido(ValueError):
    pass


def _parse_date(s: str) -> date:
    parts = s.strip().split('-')
    if len(parts) != 3:
        raise PeriodoInvalido(f'Data inválida: {s!r} (use AAAA-MM-DD).')
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    return date(y, m, d)


def resolver_periodo(params: QueryDict) -> tuple[date, date, dict]:
    """
    Retorna (data_inicio, data_fim, metadados).
    Precedência: `mes` > `trimestre` > par `data_inicio`+`data_fim`.
    """
    meta: dict = {'tipo': 'intervalo'}

    mes = (params.get('mes') or '').strip()
    if mes:
        if not re.match(r'^\d{4}-\d{2}$', mes):
            raise PeriodoInvalido('Parâmetro mes deve estar no formato AAAA-MM.')
        y, m = int(mes[:4]), int(mes[5:7])
        if m < 1 or m > 12:
            raise PeriodoInvalido('Mês inválido em mes=AAAA-MM.')
        ult = monthrange(y, m)[1]
        meta['tipo'] = 'mes'
        meta['mes'] = mes
        return date(y, m, 1), date(y, m, ult), meta

    tri = (params.get('trimestre') or '').strip()
    if tri:
        m = re.match(r'^(\d{4})-Q([1-4])$', tri, re.I)
        if not m:
            raise PeriodoInvalido('Parâmetro trimestre deve estar no formato AAAA-Q1 a AAAA-Q4.')
        y = int(m.group(1))
        q = int(m.group(2))
        start_m = {1: 1, 2: 4, 3: 7, 4: 10}[q]
        end_m = {1: 3, 2: 6, 3: 9, 4: 12}[q]
        ult = monthrange(y, end_m)[1]
        meta['tipo'] = 'trimestre'
        meta['trimestre'] = f'{y}-Q{q}'
        return date(y, start_m, 1), date(y, end_m, ult), meta

    di_s = (params.get('data_inicio') or '').strip()
    df_s = (params.get('data_fim') or '').strip()
    if not di_s or not df_s:
        raise PeriodoInvalido(
            'Informe o período: mes=AAAA-MM, trimestre=AAAA-Qn ou data_inicio e data_fim (AAAA-MM-DD).'
        )
    di = _parse_date(di_s)
    df = _parse_date(df_s)
    if df < di:
        raise PeriodoInvalido('data_fim não pode ser anterior a data_inicio.')
    meta['data_inicio'] = di.isoformat()
    meta['data_fim'] = df.isoformat()
    return di, df, meta


def bounds_para_listagem(params: QueryDict) -> tuple[date, date] | None:
    """
    Se houver filtro de período na querystring, retorna (início, fim).
    Se não houver nenhum, retorna None (lista completa).
    """
    if params.get('mes') or params.get('trimestre'):
        di, df, _ = resolver_periodo(params)
        return di, df
    if params.get('data_inicio') or params.get('data_fim'):
        di, df, _ = resolver_periodo(params)
        return di, df
    return None


def aplicar_filtros_vinculo(
    qs, cliente_id: str | None, empresa_emitente_id: str | None
):
    if cliente_id:
        try:
            cid = int(cliente_id)
        except ValueError:
            raise PeriodoInvalido('cliente_id inválido.') from None
        qs = qs.filter(cliente_id=cid)
    if empresa_emitente_id:
        try:
            eid = int(empresa_emitente_id)
        except ValueError:
            raise PeriodoInvalido('empresa_emitente_id inválido.') from None
        qs = qs.filter(empresa_emitente_id=eid)
    return qs
