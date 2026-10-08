"""NF-e Saída 3.5.1 — diagnósticos de exibição (reforma/fiscal), sem recálculo."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.snapshot_fiscal_helpers import (
    get_reforma_tributaria_snapshot,
    reforma_configurada_no_snapshot,
)


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _origem_label(nf: NFeSaida) -> str:
    if nf.faturamento_pedido_venda_id:
        return 'FATURAMENTO'
    if nf.pedido_venda_id:
        return 'PEDIDO'
    return 'MANUAL'


def diagnostico_reforma_item(
    nf: NFeSaida,
    item: ItemNFeSaida,
    snap_f: dict | None,
    reforma_raw: dict | None,
) -> str:
    snap = snap_f or {}
    origem = _origem_label(nf)
    bloco_raw = snap.get('reforma_tributaria') or snap.get('ibs_cbs')

    if not snap:
        if origem == 'MANUAL':
            return 'Item manual sem snapshot fiscal.'
        return 'Sem bloco de snapshot fiscal no item.'

    if not bloco_raw and not reforma_configurada_no_snapshot(snap):
        if origem == 'MANUAL':
            return 'Item manual sem dados de reforma.'
        if _text(snap.get('origem_regra_fiscal_saida')):
            return 'Regra fiscal de saída sem IBS/CBS configurado.'
        return 'Sem bloco reforma_tributaria no snapshot fiscal.'

    norm = get_reforma_tributaria_snapshot(snap) or reforma_raw or {}
    if not _text(norm.get('cst_ibs_cbs')):
        return 'CST IBS/CBS ausente.'
    if not _text(norm.get('classificacao_tributaria')):
        return 'Classificação tributária ausente.'
    if not _text(norm.get('aliquota_cbs')) and not _text(norm.get('aliquota_ibs_estadual')):
        return 'Alíquotas IBS/CBS ausentes.'
    return ''


def alertas_fiscal_item(snap_f: dict | None, fiscal_atual: dict[str, Any]) -> list[str]:
    snap = snap_f or {}
    alertas: list[str] = []
    if not snap:
        alertas.append('Sem snapshot fiscal no item.')
        return alertas

    ncm = _text(fiscal_atual.get('ncm') if isinstance(fiscal_atual.get('ncm'), str) else '')
    if not ncm:
        icms = fiscal_atual.get('icms') or {}
        if not _text(icms.get('cst_icms') or icms.get('csosn')):
            alertas.append('Sem CST ICMS/CSOSN no snapshot.')

    def _zero_val(block: dict | None, key: str = 'valor') -> bool:
        if not block:
            return True
        raw = block.get(key)
        if raw in (None, ''):
            return True
        try:
            return Decimal(str(raw)) == 0
        except Exception:
            return True

    icms = fiscal_atual.get('icms') or {}
    ipi = fiscal_atual.get('ipi') or {}
    pis = fiscal_atual.get('pis') or {}
    cofins = fiscal_atual.get('cofins') or {}
    tem_aliquota = any(
        _text(x.get('aliquota'))
        for x in (icms, ipi, pis, cofins)
    )
    if tem_aliquota and all(
        [
            _zero_val(icms),
            _zero_val(ipi),
            _zero_val(pis),
            _zero_val(cofins),
        ],
    ):
        alertas.append('Valores fiscais zerados ou não informados no snapshot.')
        alertas.append('Confira a regra fiscal de saída do item.')

    pis_ded = pis.get('deduzir_icms_base')
    if pis_ded in (True, 'true', '1', 1):
        alertas.append('PIS com base deduzida do ICMS (configurado).')
    cofins_ded = cofins.get('deduzir_icms_base')
    if cofins_ded in (True, 'true', '1', 1):
        alertas.append('COFINS com base deduzida do ICMS (configurado).')

    return alertas


def alertas_fiscal_gerais(totais: dict[str, str]) -> list[str]:
    alertas: list[str] = []

    def _is_zero(key: str) -> bool:
        try:
            return Decimal(str(totais.get(key, '0'))) == 0
        except Exception:
            return True

    if all(_is_zero(k) for k in ('valor_icms', 'valor_ipi', 'valor_pis', 'valor_cofins', 'total_tributos_atuais')):
        alertas.append('Totais fiscais atuais zerados — conferir snapshots dos itens.')
    return alertas
