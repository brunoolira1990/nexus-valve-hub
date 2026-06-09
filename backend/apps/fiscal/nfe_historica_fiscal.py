"""
Consolidação fiscal/gerencial de **faturamento** a partir de NFeSaidaHistoricaImportada.

Importante: no XML de NF-e, o fornecedor emite compra com tpNF=1 (saída **do emitente**).
Essas notas **não** devem entrar nesta base de consolidação: a query deve ser filtrada para
considerar apenas notas em que o **emitente do XML** foi reconhecido como uma Empresa do ERP
(`empresa_emitente` preenchido). Assim, notas de compra importadas por engano na tabela de
saída não distorcem o faturamento.

IRPJ/CSLL: não há extração por item/nota a partir do XML nesta camada; apenas base
de faturamento realizado para estimativas gerenciais futuras.

Totais de ICMS/IPI/PIS/COFINS: preferencialmente do grupo ICMSTot em totais_json
(layout NF-e). Ausência de bloco ou de campo não é mascarada nos contadores
`notas_sem_bloco_icmstot`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from .models import NFeSaidaHistoricaImportada


def queryset_faturamento_nf_saida_historica(qs: QuerySet[NFeSaidaHistoricaImportada]) -> QuerySet[NFeSaidaHistoricaImportada]:
    """Empresa emitente vinculada + produção autorizada (exclui homologação para precificação/gerencial)."""
    from apps.fiscal.dfe_classificacao import filtrar_queryset_precificacao_historica_saida

    return filtrar_queryset_precificacao_historica_saida(qs.filter(empresa_emitente__isnull=False))


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _icms_tot_dict(totais_json: dict[str, Any] | None) -> dict[str, Any]:
    if not totais_json or not isinstance(totais_json, dict):
        return {}
    raw = totais_json.get('ICMSTot')
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw if isinstance(raw, dict) else {}


def documento_tem_icmstot(totais_json: dict[str, Any] | None) -> bool:
    return bool(_icms_tot_dict(totais_json))


def extrair_totais_fiscais_documento(totais_json: dict[str, Any] | None) -> dict[str, Decimal]:
    """Valores agregados no nível do documento (ICMSTot), quando presentes no XML importado."""
    icms = _icms_tot_dict(totais_json)
    return {
        'icms_base': _dec(icms.get('vBC')),
        'icms_valor': _dec(icms.get('vICMS')),
        'ipi_valor': _dec(icms.get('vIPI')),
        'pis_valor': _dec(icms.get('vPIS')),
        'cofins_valor': _dec(icms.get('vCOFINS')),
    }


@dataclass
class LinhaConsolidada:
    faturamento_bruto: Decimal = Decimal('0')
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
    clientes_vinculados_distintos: set[int] = field(default_factory=set)
    notas_com_reforma_json: int = 0

    def add_nota(self, nf: NFeSaidaHistoricaImportada) -> None:
        self.quantidade_notas += 1
        self.faturamento_bruto += nf.valor_total_nf or Decimal('0')
        self.valor_produtos += nf.valor_produtos or Decimal('0')
        self.frete += nf.v_frete or Decimal('0')
        self.desconto += nf.v_desc or Decimal('0')

        tot = nf.totais_json or {}
        if not _icms_tot_dict(tot):
            self.notas_sem_icmstot += 1
        ext = extrair_totais_fiscais_documento(tot)
        self.icms_base += ext['icms_base']
        self.icms_valor += ext['icms_valor']
        self.ipi_valor += ext['ipi_valor']
        self.pis_valor += ext['pis_valor']
        self.cofins_valor += ext['cofins_valor']

        if nf.cliente_id:
            self.clientes_vinculados_distintos.add(nf.cliente_id)

        rj = nf.reforma_e_outros_json
        if isinstance(rj, dict) and len(rj) > 0:
            self.notas_com_reforma_json += 1


def _money_float(d: Decimal) -> float:
    return float(d.quantize(Decimal('0.01')))


def _pct(numer: Decimal, denom: Decimal) -> float | None:
    if denom <= 0:
        return None
    return float((numer / denom * Decimal('100')).quantize(Decimal('0.0001')))


def consolidar_queryset(qs: QuerySet[NFeSaidaHistoricaImportada]) -> LinhaConsolidada:
    linha = LinhaConsolidada()
    for nf in qs.iterator(chunk_size=500):
        linha.add_nota(nf)
    return linha


def serializar_linha(linha: LinhaConsolidada) -> dict[str, Any]:
    """Campos numéricos agregados + contadores de qualidade dos dados."""
    fat = linha.faturamento_bruto
    trib_total = linha.icms_valor + linha.ipi_valor + linha.pis_valor + linha.cofins_valor
    return {
        'faturamento_bruto': _money_float(linha.faturamento_bruto),
        'valor_produtos': _money_float(linha.valor_produtos),
        'frete': _money_float(linha.frete),
        'desconto': _money_float(linha.desconto),
        'icms_base': _money_float(linha.icms_base),
        'icms_valor': _money_float(linha.icms_valor),
        'ipi_valor': _money_float(linha.ipi_valor),
        'pis_valor': _money_float(linha.pis_valor),
        'cofins_valor': _money_float(linha.cofins_valor),
        'quantidade_notas': linha.quantidade_notas,
        'quantidade_clientes_vinculados': len(linha.clientes_vinculados_distintos),
        'notas_sem_bloco_icmstot': linha.notas_sem_icmstot,
        'notas_com_reforma_e_outros_json': linha.notas_com_reforma_json,
        'indicadores_gerenciais': {
            'aliquota_efetiva_media_icms_sobre_faturamento_pct': _pct(linha.icms_valor, fat),
            'aliquota_efetiva_media_pis_sobre_faturamento_pct': _pct(linha.pis_valor, fat),
            'aliquota_efetiva_media_cofins_sobre_faturamento_pct': _pct(linha.cofins_valor, fat),
            'carga_tributaria_media_total_observada_pct': _pct(trib_total, fat),
        },
    }


def separar_totais_e_indicadores(linha: LinhaConsolidada) -> tuple[dict[str, Any], dict[str, Any]]:
    """Separa totais agregados dos percentuais gerenciais para payloads da API."""
    full = serializar_linha(linha)
    ind = full.pop('indicadores_gerenciais', {})
    return full, ind


def agrupar_por_mes(qs: QuerySet[NFeSaidaHistoricaImportada]) -> list[dict[str, Any]]:
    buckets: dict[str, LinhaConsolidada] = defaultdict(LinhaConsolidada)
    for nf in qs.iterator(chunk_size=500):
        d = nf.dh_emissao.date()
        key = f'{d.year:04d}-{d.month:02d}'
        buckets[key].add_nota(nf)
    out = []
    for ano_mes in sorted(buckets.keys()):
        linha = buckets[ano_mes]
        tot, ind = separar_totais_e_indicadores(linha)
        out.append({'ano_mes': ano_mes, 'totais': tot, 'indicadores_gerenciais': ind})
    return out


def agrupar_por_trimestre(qs: QuerySet[NFeSaidaHistoricaImportada]) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int], LinhaConsolidada] = defaultdict(LinhaConsolidada)
    for nf in qs.iterator(chunk_size=500):
        d = nf.dh_emissao.date()
        tri = (d.month - 1) // 3 + 1
        buckets[(d.year, tri)].add_nota(nf)
    out = []
    for (year, tri) in sorted(buckets.keys()):
        linha = buckets[(year, tri)]
        tot, ind = separar_totais_e_indicadores(linha)
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
