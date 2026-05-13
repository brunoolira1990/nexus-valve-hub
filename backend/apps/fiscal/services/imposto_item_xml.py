"""
Extração de tributos por item a partir de prod_json / imposto_json (NF-e importada).

Não inventa valores: apenas lê chaves presentes no JSON fiel ao XML.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _dictish(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _first_dict_children(node: Any) -> list[dict[str, Any]]:
    """Filhos que são dict (ex.: ICMS.{ICMS00: {...}})."""
    if isinstance(node, list):
        out: list[dict[str, Any]] = []
        for x in node:
            out.extend(_first_dict_children(x))
        return out
    if not isinstance(node, dict):
        return []
    blocks: list[dict[str, Any]] = []
    for v in node.values():
        if isinstance(v, dict):
            blocks.append(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    blocks.append(x)
    return blocks


def _merge_icms_like_blocks(root: dict[str, Any], key: str) -> dict[str, Any]:
    """Une vBC, vICMS, pICMS, CST/CSOSN dos blocos ICMS* / PIS* / COFINS* / IPI*."""
    node = root.get(key)
    if node is None:
        return {}
    if isinstance(node, list):
        node = node[0] if node else {}
    node = _dictish(node)
    merged: dict[str, Any] = {}
    v_bc = Decimal('0')
    v_imp = Decimal('0')
    p_imp: Decimal | None = None
    cst = ''
    csosn = ''
    for blk in _first_dict_children(node):
        cst = cst or str(blk.get('CST') or '').strip()
        csosn = csosn or str(blk.get('CSOSN') or '').strip()
        v_bc += dec(blk.get('vBC'))
        if key == 'IPI':
            v_imp += dec(blk.get('vIPI'))
            if blk.get('pIPI') not in (None, ''):
                p_imp = dec(blk.get('pIPI'))
        elif key == 'ICMS':
            v_imp += dec(blk.get('vICMS'))
            if blk.get('pICMS') not in (None, ''):
                p_imp = dec(blk.get('pICMS'))
        elif key == 'PIS':
            v_imp += dec(blk.get('vPIS'))
            if blk.get('pPIS') not in (None, ''):
                p_imp = dec(blk.get('pPIS'))
        elif key == 'COFINS':
            v_imp += dec(blk.get('vCOFINS'))
            if blk.get('pCOFINS') not in (None, ''):
                p_imp = dec(blk.get('pCOFINS'))
    merged['CST'] = cst
    merged['CSOSN'] = csosn
    merged['vBC'] = v_bc
    if key == 'IPI':
        merged['vIPI'] = v_imp
        merged['pIPI'] = p_imp
    elif key == 'ICMS':
        merged['vICMS'] = v_imp
        merged['pICMS'] = p_imp
    elif key == 'PIS':
        merged['vPIS'] = v_imp
        merged['pPIS'] = p_imp
    elif key == 'COFINS':
        merged['vCOFINS'] = v_imp
        merged['pCOFINS'] = p_imp
    return merged


def extrair_produto_item(prod_json: dict[str, Any] | None) -> dict[str, Any]:
    pj = _dictish(prod_json)
    return {
        'ncm': str(pj.get('NCM') or '').strip(),
        'cfop': str(pj.get('CFOP') or '').strip(),
        'c_prod': str(pj.get('cProd') or '').strip(),
        'x_prod': str(pj.get('xProd') or '').strip(),
        'valor_prod': dec(pj.get('vProd')),
    }


def extrair_tributos_item(
    prod_json: dict[str, Any] | None,
    imposto_json: dict[str, Any] | None,
) -> dict[str, Any]:
    imp = _dictish(imposto_json)
    icms = _merge_icms_like_blocks(imp, 'ICMS')
    ipi = _merge_icms_like_blocks(imp, 'IPI')
    pis = _merge_icms_like_blocks(imp, 'PIS')
    cofins = _merge_icms_like_blocks(imp, 'COFINS')
    cst_icms = str(icms.get('CST') or icms.get('CSOSN') or '').strip()
    cst_pis = str(pis.get('CST') or '').strip()
    cst_cofins = str(cofins.get('CST') or '').strip()
    return {
        'cst_icms': cst_icms,
        'cst_icms_detalhe': str(icms.get('CSOSN') or '').strip() if icms.get('CST') else '',
        'base_icms': dec(icms.get('vBC')),
        'aliquota_icms': dec(icms.get('pICMS')) if icms.get('pICMS') is not None else None,
        'valor_icms': dec(icms.get('vICMS')),
        'base_ipi': dec(ipi.get('vBC')),
        'aliquota_ipi': dec(ipi.get('pIPI')) if ipi.get('pIPI') is not None else None,
        'valor_ipi': dec(ipi.get('vIPI')),
        'base_pis': dec(pis.get('vBC')),
        'aliquota_pis': dec(pis.get('pPIS')) if pis.get('pPIS') is not None else None,
        'valor_pis': dec(pis.get('vPIS')),
        'base_cofins': dec(cofins.get('vBC')),
        'aliquota_cofins': dec(cofins.get('pCOFINS')) if cofins.get('pCOFINS') is not None else None,
        'valor_cofins': dec(cofins.get('vCOFINS')),
        'cst_pis': cst_pis,
        'cst_cofins': cst_cofins,
    }
