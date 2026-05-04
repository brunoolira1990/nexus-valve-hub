from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from .models import CTeHistoricoImportado


def _money_float(d: Decimal) -> float:
    return float(d.quantize(Decimal('0.01')))


def _pct(numer: Decimal, denom: Decimal) -> float | None:
    if denom <= 0:
        return None
    return float((numer / denom * Decimal('100')).quantize(Decimal('0.0001')))


@dataclass
class LinhaConsolidadaCTe:
    valor_total_fretes: Decimal = Decimal('0')
    valor_total_receber: Decimal = Decimal('0')
    icms_total: Decimal = Decimal('0')
    quantidade_ctes: int = 0
    transportadoras_distintas: set[int] = field(default_factory=set)
    total_por_transportadora: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))

    def add_cte(self, cte: CTeHistoricoImportado) -> None:
        self.quantidade_ctes += 1
        self.valor_total_fretes += cte.valor_total_servico or Decimal('0')
        self.valor_total_receber += cte.valor_receber or Decimal('0')
        self.icms_total += cte.icms_valor or Decimal('0')

        if cte.transportadora_id:
            self.transportadoras_distintas.add(cte.transportadora_id)

        nome_transportadora = ''
        if cte.transportadora_id and cte.transportadora:
            nome_transportadora = cte.transportadora.razao_social
        if not nome_transportadora:
            nome_transportadora = (cte.emit_json or {}).get('xNome', '') or 'Sem transportadora identificada'
        self.total_por_transportadora[nome_transportadora] += cte.valor_total_servico or Decimal('0')


def queryset_cte_historico_logistico(qs: QuerySet[CTeHistoricoImportado]) -> QuerySet[CTeHistoricoImportado]:
    # Fluxo normal de frete/custo considera somente CT-e em que a Empresa ERP é tomadora.
    return qs.filter(empresa_tomadora__isnull=False)


def consolidar_queryset_cte(qs: QuerySet[CTeHistoricoImportado]) -> LinhaConsolidadaCTe:
    linha = LinhaConsolidadaCTe()
    for cte in qs.iterator(chunk_size=500):
        linha.add_cte(cte)
    return linha


def serializar_linha_cte(linha: LinhaConsolidadaCTe) -> dict[str, Any]:
    frete_medio = Decimal('0')
    if linha.quantidade_ctes > 0:
        frete_medio = linha.valor_total_fretes / Decimal(linha.quantidade_ctes)

    total_por_transportadora = [
        {'transportadora_nome': nome, 'valor_total_frete': _money_float(valor)}
        for nome, valor in sorted(linha.total_por_transportadora.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        'valor_total_fretes': _money_float(linha.valor_total_fretes),
        'valor_total_receber': _money_float(linha.valor_total_receber),
        'icms_total': _money_float(linha.icms_total),
        'quantidade_ctes': linha.quantidade_ctes,
        'frete_medio': _money_float(frete_medio),
        'quantidade_transportadoras_vinculadas': len(linha.transportadoras_distintas),
        'total_por_transportadora': total_por_transportadora,
        'indicadores_gerenciais': {
            'aliquota_efetiva_media_icms_sobre_frete_pct': _pct(linha.icms_total, linha.valor_total_fretes),
        },
    }


def separar_totais_e_indicadores_cte(linha: LinhaConsolidadaCTe) -> tuple[dict[str, Any], dict[str, Any]]:
    full = serializar_linha_cte(linha)
    ind = full.pop('indicadores_gerenciais', {})
    return full, ind


def agrupar_cte_por_mes(qs: QuerySet[CTeHistoricoImportado]) -> list[dict[str, Any]]:
    buckets: dict[str, LinhaConsolidadaCTe] = defaultdict(LinhaConsolidadaCTe)
    for cte in qs.iterator(chunk_size=500):
        d = cte.dh_emissao.date()
        key = f'{d.year:04d}-{d.month:02d}'
        buckets[key].add_cte(cte)
    out = []
    for ano_mes in sorted(buckets.keys()):
        tot, ind = separar_totais_e_indicadores_cte(buckets[ano_mes])
        out.append({'ano_mes': ano_mes, 'totais': tot, 'indicadores_gerenciais': ind})
    return out


def agrupar_cte_por_trimestre(qs: QuerySet[CTeHistoricoImportado]) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int], LinhaConsolidadaCTe] = defaultdict(LinhaConsolidadaCTe)
    for cte in qs.iterator(chunk_size=500):
        d = cte.dh_emissao.date()
        tri = (d.month - 1) // 3 + 1
        buckets[(d.year, tri)].add_cte(cte)
    out = []
    for (year, tri) in sorted(buckets.keys()):
        tot, ind = separar_totais_e_indicadores_cte(buckets[(year, tri)])
        out.append(
            {
                'ano': year,
                'trimestre': tri,
                'rotulo': f'{year}-Q{tri}',
                'totais': tot,
                'indicadores_gerenciais': ind,
            }
        )
    return out


def agrupar_cte_por_transportadora(qs: QuerySet[CTeHistoricoImportado]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    total_geral = Decimal('0')

    for cte in qs.iterator(chunk_size=500):
        nome = ''
        if cte.transportadora_id and cte.transportadora:
            nome = cte.transportadora.razao_social
        if not nome:
            nome = (cte.emit_json or {}).get('xNome', '') or 'Sem transportadora identificada'

        valor = cte.valor_total_servico or Decimal('0')
        total_geral += valor
        if nome not in rows:
            rows[nome] = {
                'transportadora_nome': nome,
                'quantidade_ctes': 0,
                'valor_total_fretes': Decimal('0'),
            }
        rows[nome]['quantidade_ctes'] += 1
        rows[nome]['valor_total_fretes'] += valor

    out: list[dict[str, Any]] = []
    for nome, row in rows.items():
        qtd = int(row['quantidade_ctes'])
        total = row['valor_total_fretes']
        frete_medio = (total / Decimal(qtd)) if qtd > 0 else Decimal('0')
        participacao = _pct(total, total_geral)
        out.append(
            {
                'transportadora_nome': nome,
                'quantidade_ctes': qtd,
                'valor_total_fretes': _money_float(total),
                'frete_medio': _money_float(frete_medio),
                'participacao_pct': participacao,
            }
        )
    out.sort(key=lambda r: r['valor_total_fretes'], reverse=True)
    return out
