"""
Consolidação fiscal/gerencial de **compras / entradas** a partir de NFeEntradaHistoricaImportada.

Considera apenas notas em que o **destinatário** foi reconhecido como Empresa do ERP
(`empresa_destinataria` preenchido). Tributos documentais via ICMSTot quando existir.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from .models import NFeEntradaHistoricaImportada
from .nfe_entrada_data_entrada import data_competencia_entrada_nf
from .nfe_historica_fiscal import (
    _money_float,
    _pct,
    documento_tem_icmstot,
    extrair_totais_fiscais_documento,
)


@dataclass
class LinhaConsolidadaEntrada:
    """Totais de compra/custo (não é faturamento)."""

    valor_total_compras: Decimal = Decimal('0')
    valor_produtos: Decimal = Decimal('0')
    frete: Decimal = Decimal('0')
    desconto: Decimal = Decimal('0')
    icms_base: Decimal = Decimal('0')
    icms_valor: Decimal = Decimal('0')
    ipi_valor: Decimal = Decimal('0')
    pis_valor: Decimal = Decimal('0')
    cofins_valor: Decimal = Decimal('0')
    quantidade_notas: int = 0
    notas_sem_icmstot: int = 0
    fornecedores_vinculados_distintos: set[int] = field(default_factory=set)
    notas_com_reforma_json: int = 0

    def add_nota(self, nf: NFeEntradaHistoricaImportada) -> None:
        self.quantidade_notas += 1
        self.valor_total_compras += nf.valor_total_nf or Decimal('0')
        self.valor_produtos += nf.valor_produtos or Decimal('0')
        self.frete += nf.v_frete or Decimal('0')
        self.desconto += nf.v_desc or Decimal('0')

        tot = nf.totais_json or {}
        if not documento_tem_icmstot(tot):
            self.notas_sem_icmstot += 1
        ext = extrair_totais_fiscais_documento(tot)
        self.icms_base += ext['icms_base']
        self.icms_valor += ext['icms_valor']
        self.ipi_valor += ext['ipi_valor']
        self.pis_valor += ext['pis_valor']
        self.cofins_valor += ext['cofins_valor']

        if nf.fornecedor_emitente_id:
            self.fornecedores_vinculados_distintos.add(nf.fornecedor_emitente_id)

        rj = nf.reforma_e_outros_json
        if isinstance(rj, dict) and len(rj) > 0:
            self.notas_com_reforma_json += 1


def queryset_compras_nf_entrada_historica(qs: QuerySet[NFeEntradaHistoricaImportada]) -> QuerySet[NFeEntradaHistoricaImportada]:
    from apps.fiscal.dfe_classificacao import filtrar_queryset_precificacao_historica_entrada

    return filtrar_queryset_precificacao_historica_entrada(qs.filter(empresa_destinataria__isnull=False))


def consolidar_queryset_entrada(qs: QuerySet[NFeEntradaHistoricaImportada]) -> LinhaConsolidadaEntrada:
    linha = LinhaConsolidadaEntrada()
    for nf in qs.iterator(chunk_size=500):
        linha.add_nota(nf)
    return linha


def serializar_linha_entrada(linha: LinhaConsolidadaEntrada) -> dict[str, Any]:
    comp = linha.valor_total_compras
    trib_total = linha.icms_valor + linha.ipi_valor + linha.pis_valor + linha.cofins_valor
    return {
        'valor_total_compras': _money_float(linha.valor_total_compras),
        'valor_produtos': _money_float(linha.valor_produtos),
        'frete': _money_float(linha.frete),
        'desconto': _money_float(linha.desconto),
        'icms_base': _money_float(linha.icms_base),
        'icms_valor': _money_float(linha.icms_valor),
        'ipi_valor': _money_float(linha.ipi_valor),
        'pis_valor': _money_float(linha.pis_valor),
        'cofins_valor': _money_float(linha.cofins_valor),
        'quantidade_notas': linha.quantidade_notas,
        'quantidade_fornecedores_vinculados': len(linha.fornecedores_vinculados_distintos),
        'notas_sem_bloco_icmstot': linha.notas_sem_icmstot,
        'notas_com_reforma_e_outros_json': linha.notas_com_reforma_json,
        'indicadores_gerenciais': {
            'aliquota_efetiva_media_icms_sobre_compras_pct': _pct(linha.icms_valor, comp),
            'aliquota_efetiva_media_pis_sobre_compras_pct': _pct(linha.pis_valor, comp),
            'aliquota_efetiva_media_cofins_sobre_compras_pct': _pct(linha.cofins_valor, comp),
            'carga_tributaria_media_total_observada_pct': _pct(trib_total, comp),
        },
    }


def separar_totais_e_indicadores_entrada(
    linha: LinhaConsolidadaEntrada,
) -> tuple[dict[str, Any], dict[str, Any]]:
    full = serializar_linha_entrada(linha)
    ind = full.pop('indicadores_gerenciais', {})
    return full, ind


def agrupar_por_mes_entrada(qs: QuerySet[NFeEntradaHistoricaImportada]) -> list[dict[str, Any]]:
    buckets: dict[str, LinhaConsolidadaEntrada] = defaultdict(LinhaConsolidadaEntrada)
    for nf in qs.select_related('conferencia').iterator(chunk_size=500):
        d: date = data_competencia_entrada_nf(nf)
        key = f'{d.year:04d}-{d.month:02d}'
        buckets[key].add_nota(nf)
    out = []
    for ano_mes in sorted(buckets.keys()):
        linha = buckets[ano_mes]
        tot, ind = separar_totais_e_indicadores_entrada(linha)
        out.append({'ano_mes': ano_mes, 'totais': tot, 'indicadores_gerenciais': ind})
    return out


def agrupar_por_trimestre_entrada(qs: QuerySet[NFeEntradaHistoricaImportada]) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int], LinhaConsolidadaEntrada] = defaultdict(LinhaConsolidadaEntrada)
    for nf in qs.select_related('conferencia').iterator(chunk_size=500):
        d = data_competencia_entrada_nf(nf)
        tri = (d.month - 1) // 3 + 1
        buckets[(d.year, tri)].add_nota(nf)
    out = []
    for (year, tri) in sorted(buckets.keys()):
        linha = buckets[(year, tri)]
        tot, ind = separar_totais_e_indicadores_entrada(linha)
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
