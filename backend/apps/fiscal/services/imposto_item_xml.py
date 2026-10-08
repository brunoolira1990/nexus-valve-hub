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


def _primeiro_bloco_imposto(root: dict[str, Any], key: str) -> dict[str, Any]:
    """Primeiro bloco filho (ex.: ICMS00) para leitura de campos não agregados."""
    node = root.get(key)
    if node is None:
        return {}
    if isinstance(node, list):
        node = node[0] if node else {}
    node = _dictish(node)
    blocks = _first_dict_children(node)
    return blocks[0] if blocks else {}


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
    icms_blk = _primeiro_bloco_imposto(imp, 'ICMS')
    cst_icms = str(icms.get('CST') or icms_blk.get('CST') or '').strip()
    csosn = str(icms.get('CSOSN') or icms_blk.get('CSOSN') or '').strip()
    cst_pis = str(pis.get('CST') or '').strip()
    cst_cofins = str(cofins.get('CST') or '').strip()
    cst_ipi = str(ipi.get('CST') or '').strip()
    ipi_blk = _primeiro_bloco_imposto(imp, 'IPI')
    pis_blk = _primeiro_bloco_imposto(imp, 'PIS')
    cofins_blk = _primeiro_bloco_imposto(imp, 'COFINS')

    def _dec_opcional(blk: dict[str, Any], key: str) -> Decimal | None:
        if blk.get(key) in (None, ''):
            return None
        return dec(blk.get(key))

    icms_st_nf = bool(
        icms_blk.get('pMVAST') not in (None, '')
        or icms_blk.get('vBCST') not in (None, '')
        or icms_blk.get('pICMSST') not in (None, '')
        or icms_blk.get('vICMSST') not in (None, '')
    )
    fcp_presente_nf = any(
        icms_blk.get(tag) not in (None, '')
        for tag in ('pFCP', 'vFCP', 'pFCPST', 'vFCPST', 'vBCFCP', 'vBCFCPST')
    )

    # ICMS-ST / FCP-ST (valores do XML — não misturar com vICMS próprio)
    base_icms_st = dec(icms_blk.get('vBCST'))
    valor_icms_st = dec(icms_blk.get('vICMSST'))
    valor_fcp_st = dec(icms_blk.get('vFCPST'))
    valor_fcp = dec(icms_blk.get('vFCP'))

    # DIFAL — ICMSUFDest
    uf_dest = imp.get('ICMSUFDest')
    if isinstance(uf_dest, list):
        uf_dest = uf_dest[0] if uf_dest else {}
    uf_dest = _dictish(uf_dest)
    base_uf_dest = dec(uf_dest.get('vBCUFDest'))
    valor_icms_uf_dest = dec(uf_dest.get('vICMSUFDest'))
    valor_icms_uf_remet = dec(uf_dest.get('vICMSUFRemet'))
    valor_fcp_uf_dest = dec(uf_dest.get('vFCPUFDest'))

    return {
        'cst_icms': cst_icms,
        'cst_icms_detalhe': csosn if cst_icms and csosn else '',
        'csosn': csosn,
        'base_icms': dec(icms.get('vBC')),
        'aliquota_icms': dec(icms.get('pICMS')) if icms.get('pICMS') is not None else None,
        'valor_icms': dec(icms.get('vICMS')),
        'modalidade_bc_icms': str(icms_blk.get('modBC') or '').strip(),
        'reducao_bc_icms': _dec_opcional(icms_blk, 'pRedBC'),
        'motivo_desoneracao_icms': str(icms_blk.get('motDesICMS') or '').strip(),
        'codigo_beneficio_icms': str(
            icms_blk.get('cBenefRBC') or icms_blk.get('cBenef') or '',
        ).strip(),
        'icms_st_aplicavel_nf': icms_st_nf,
        'cst_icms_st_nf': str(icms_blk.get('CST') or '').strip() if icms_st_nf else '',
        'aliquota_icms_st': _dec_opcional(icms_blk, 'pICMSST'),
        'mva_st': _dec_opcional(icms_blk, 'pMVAST'),
        'reducao_bc_st': _dec_opcional(icms_blk, 'pRedBCST'),
        'base_icms_st': base_icms_st,
        'valor_icms_st': valor_icms_st,
        'valor_fcp_st': valor_fcp_st,
        'valor_fcp': valor_fcp,
        'aliquota_fcp': _dec_opcional(icms_blk, 'pFCP'),
        'aliquota_fcp_st': _dec_opcional(icms_blk, 'pFCPST'),
        'reducao_bc_fcp': _dec_opcional(icms_blk, 'pRedBCFCP')
        or _dec_opcional(icms_blk, 'pRedBCFCPST'),
        'valor_fcp_unidade': _dec_opcional(icms_blk, 'vFCPUni')
        or _dec_opcional(icms_blk, 'vFCPSTUni'),
        'fcp_presente_nf': fcp_presente_nf,
        'base_uf_dest': base_uf_dest,
        'valor_icms_uf_dest': valor_icms_uf_dest,
        'valor_icms_uf_remet': valor_icms_uf_remet,
        'valor_fcp_uf_dest': valor_fcp_uf_dest,
        'base_ipi': dec(ipi.get('vBC')),
        'aliquota_ipi': dec(ipi.get('pIPI')) if ipi.get('pIPI') is not None else None,
        'valor_ipi': dec(ipi.get('vIPI')),
        'enquadramento_ipi': str(ipi_blk.get('cEnq') or '').strip(),
        'valor_ipi_unidade': _dec_opcional(ipi_blk, 'vUnid'),
        'base_pis': dec(pis.get('vBC')),
        'aliquota_pis': dec(pis.get('pPIS')) if pis.get('pPIS') is not None else None,
        'valor_pis': dec(pis.get('vPIS')),
        'reducao_base_pis': _dec_opcional(pis_blk, 'pRedBC'),
        'base_cofins': dec(cofins.get('vBC')),
        'aliquota_cofins': dec(cofins.get('pCOFINS')) if cofins.get('pCOFINS') is not None else None,
        'valor_cofins': dec(cofins.get('vCOFINS')),
        'reducao_base_cofins': _dec_opcional(cofins_blk, 'pRedBC'),
        'cst_pis': cst_pis,
        'cst_cofins': cst_cofins,
        'cst_ipi': cst_ipi,
    }
