"""Cálculo isolado Reforma Tributária por item NF-e — sem alterar ICMS/PIS/COFINS."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.core.pdf.formatters import dec
from apps.fiscal.reforma_tributaria.config import reforma_nfe_config
from apps.fiscal.snapshot_fiscal_helpers import get_reforma_tributaria_snapshot, montar_reforma_item_exibicao
from apps.regras_fiscais.reforma_tributaria_config import reforma_tributaria_preenchida


def _money(v: Decimal) -> str:
    return str(v.quantize(Decimal('0.01')))


def _rate(v: Any) -> str:
    try:
        d = dec(v)
        return str(d.quantize(Decimal('0.0001')))
    except Exception:
        return '0.0000'


def calcular_reforma_tributaria_nfe_item(item, contexto: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Helper neutro — valores derivados de snapshot/regra, não de alíquotas fixas no código.
    Não persiste nem altera financeiro/estoque.
    """
    _ = contexto
    cfg = reforma_nfe_config()
    snap = getattr(item, 'snapshot_fiscal', None) or {}
    reforma = get_reforma_tributaria_snapshot(snap)
    valor_produto = dec(getattr(item, 'valor', 0)) * dec(getattr(item, 'quantidade', 0))

    if not reforma_tributaria_preenchida(reforma):
        return {
            'aplicavel': False,
            'cst': '',
            'classificacao_tributaria': '',
            'base_calculo': '0.00',
            'ibs': {
                'uf': {'aliquota': '0.0000', 'valor': '0.00'},
                'municipio': {'aliquota': '0.0000', 'valor': '0.00'},
                'total': '0.00',
            },
            'cbs': {'aliquota': '0.0000', 'valor': '0.00'},
            'imposto_seletivo': {
                'aplicavel': False,
                'base_calculo': '0.00',
                'aliquota': '0.0000',
                'valor': '0.00',
            },
            'observacoes': ['Reforma Tributária não configurada no item.'],
            'modo': cfg['modo'],
        }

    ex = montar_reforma_item_exibicao(reforma, valor_produto=valor_produto)
    ibs_uf = dec(ex.get('valor_ibs_estadual', 0))
    ibs_mun = dec(ex.get('valor_ibs_municipal', 0))
    cbs = dec(ex.get('valor_cbs', 0))

    return {
        'aplicavel': True,
        'cst': str(reforma.get('cst_ibs_cbs') or ''),
        'classificacao_tributaria': str(reforma.get('classificacao_tributaria') or ''),
        'base_calculo': _money(dec(ex.get('base_calculo', valor_produto))),
        'ibs': {
            'uf': {
                'aliquota': _rate(reforma.get('aliquota_ibs_estadual')),
                'valor': _money(ibs_uf),
            },
            'municipio': {
                'aliquota': _rate(reforma.get('aliquota_ibs_municipal')),
                'valor': _money(ibs_mun),
            },
            'total': _money(ibs_uf + ibs_mun),
        },
        'cbs': {
            'aliquota': _rate(reforma.get('aliquota_cbs')),
            'valor': _money(cbs),
        },
        'imposto_seletivo': {
            'aplicavel': False,
            'base_calculo': '0.00',
            'aliquota': '0.0000',
            'valor': '0.00',
        },
        'observacoes': list(ex.get('observacoes') or [])[:5],
        'modo': cfg['modo'],
    }
