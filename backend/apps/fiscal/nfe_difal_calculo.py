"""Cálculo DIFAL/FCP destino (ICMSUFDest) para NF-e Saída — consumidor final não contribuinte."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.regras_fiscais.models import RegraFiscalSaida


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _dec(val) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _q2(val: Decimal) -> str:
    return str(val.quantize(Decimal('0.01')))


def _norm_uf(uf: str) -> str:
    return _text(uf).upper()[:2]


def deve_aplicar_difal(
    *,
    uf_origem: str,
    uf_destino: str,
    destinatario_contribuinte: str,
    consumidor_final: bool | None,
    regra: RegraFiscalSaida | None,
) -> bool:
    ufo = _norm_uf(uf_origem)
    ufd = _norm_uf(uf_destino)
    if len(ufo) != 2 or len(ufd) != 2 or ufo == ufd:
        return False
    if destinatario_contribuinte == RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE:
        return False
    if consumidor_final is not True:
        return False
    if regra is None or not regra.difal_aplicavel:
        return False
    return True


def validar_parametros_difal_regra(
    regra: RegraFiscalSaida,
    *,
    uf_destino: str = '',
    nome_item: str = '',
) -> list[str]:
    prefixo = f'Regra fiscal #{regra.pk}'
    if nome_item:
        prefixo = f'{nome_item} — {prefixo}'
    erros: list[str] = []
    if not regra.difal_aplicavel:
        return erros
    ali_inter = _dec(regra.aliquota_icms_interestadual)
    ali_dest = _dec(regra.aliquota_icms_interna_destino)
    if ali_inter <= 0:
        erros.append(f'{prefixo}: informe alíquota ICMS interestadual para DIFAL.')
    if ali_dest <= 0:
        ufd = _norm_uf(uf_destino) or 'destino'
        erros.append(f'{prefixo}: informe alíquota ICMS interna da UF {ufd} para DIFAL.')
    if regra.fcp_aplicavel and _dec(regra.aliquota_fcp) < 0:
        erros.append(f'{prefixo}: alíquota FCP destino inválida.')
    return erros


def calcular_difal_item(
    valor_base: Decimal,
    regra: RegraFiscalSaida,
) -> dict[str, Any]:
    """Retorna snapshot DIFAL por item (valores monetários em string com 2 casas)."""
    ali_inter = _dec(regra.aliquota_icms_interestadual)
    ali_dest = _dec(regra.aliquota_icms_interna_destino)
    base = max(valor_base, Decimal('0')).quantize(Decimal('0.01'))

    difal_pct = max(ali_dest - ali_inter, Decimal('0'))
    v_icms_uf_dest = (base * difal_pct / Decimal('100')).quantize(Decimal('0.01'))
    v_icms_uf_remet = Decimal('0')

    p_fcp = Decimal('0')
    v_fcp = Decimal('0')
    if regra.fcp_aplicavel:
        p_fcp = _dec(regra.aliquota_fcp)
        if p_fcp > 0:
            v_fcp = (base * p_fcp / Decimal('100')).quantize(Decimal('0.01'))

    return {
        'aplicavel': True,
        'v_bc_uf_dest': _q2(base),
        'v_bc_fcp_uf_dest': _q2(base),
        'p_fcp_uf_dest': _q2(p_fcp),
        'p_icms_uf_dest': _q2(ali_dest),
        'p_icms_inter': _q2(ali_inter),
        'p_icms_inter_part': '100.00',
        'v_fcp_uf_dest': _q2(v_fcp),
        'v_icms_uf_dest': _q2(v_icms_uf_dest),
        'v_icms_uf_remet': _q2(v_icms_uf_remet),
    }


def agregar_totais_difal(snapshots_difal: list[dict[str, Any]]) -> dict[str, str]:
    aplicaveis = [
        d
        for d in snapshots_difal
        if _dec(d.get('v_icms_uf_dest')) > 0 or _dec(d.get('v_fcp_uf_dest')) > 0
    ]
    if not aplicaveis:
        return {}
    v_fcp = sum(_dec(d.get('v_fcp_uf_dest')) for d in aplicaveis)
    v_dest = sum(_dec(d.get('v_icms_uf_dest')) for d in aplicaveis)
    v_remet = sum(_dec(d.get('v_icms_uf_remet')) for d in aplicaveis)
    return {
        'v_fcp_uf_dest': _q2(v_fcp),
        'v_icms_uf_dest': _q2(v_dest),
        'v_icms_uf_remet': _q2(v_remet),
    }


def texto_difal_inf_complementar(totais_difal: dict[str, str]) -> str:
    if not totais_difal:
        return ''
    v_dest = _dec(totais_difal.get('v_icms_uf_dest'))
    v_fcp = _dec(totais_difal.get('v_fcp_uf_dest'))
    if v_dest <= 0 and v_fcp <= 0:
        return ''
    partes: list[str] = []
    if v_dest > 0:
        partes.append(f'VALOR ICMS UF DESTINO R$ {_q2(v_dest)}')
    if v_fcp > 0:
        partes.append(f'VALOR FCP UF DESTINO R$ {_q2(v_fcp)}')
    return ' — '.join(partes)
