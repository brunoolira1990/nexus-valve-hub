"""
Reforma tributária (CBS, IBS, IS): extração a partir de JSON fiel ao XML da NF-e/CT-e.

Caminhos mapeados (layout NT / reforma):
- NF-e item: det/imposto/IBSCBS (CST, cClassTrib, gIBSCBS/…)
- NF-e total: total/IBSCBSTot (vBCIBSCBS, gIBS/…, gCBS/…)
- CT-e: infCte/imp/IBSCBS (mesma árvore gIBSCBS quando presente)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .imposto_item_xml import dec

_ZERO = Decimal('0')


def coercer_mapping_json(val: Any) -> dict[str, Any]:
    """Garante dict a partir de JSONField (dict), string JSON ou vazio."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return {}
        try:
            j = json.loads(s)
        except json.JSONDecodeError:
            return {}
        return j if isinstance(j, dict) else {}
    return {}


def coercer_imposto_item_json(imp: Any) -> dict[str, Any]:
    """
    imposto_json do item costuma ser o conteúdo de <imposto> (ICMS, PIS, IBSCBS…).
    Aceita string JSON ou envelope legado {'imposto': {...}}.
    """
    d = coercer_mapping_json(imp)
    if not d:
        return {}
    if _get_ibscbs_node(d):
        return d
    inner = d.get('imposto')
    if isinstance(inner, dict) and _get_ibscbs_node(inner):
        return inner
    return d


def _resolver_bloco_ibscbstot(totais_json: Any) -> dict[str, Any] | None:
    """Localiza o dict IBSCBSTot em totais_json achatado, aninhado em `total` ou chave camelCase alternativa."""
    root = coercer_mapping_json(totais_json)
    if not root:
        return None
    for k in ('IBSCBSTot', 'ibscbstot'):
        n = root.get(k)
        if isinstance(n, dict):
            return n
    inner = root.get('total')
    if isinstance(inner, dict):
        for k in ('IBSCBSTot', 'ibscbstot'):
            n = inner.get(k)
            if isinstance(n, dict):
                return n
    return None


def _dget(obj: Any, *keys: str) -> Any:
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _get_ibscbs_node(imposto: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(imposto, dict):
        return None
    for k in ('IBSCBS', 'ibscbs'):
        v = imposto.get(k)
        if isinstance(v, dict):
            return v
    return None


def _dec_any(v: Any) -> Decimal:
    if v is None:
        return _ZERO
    if isinstance(v, (int, float, Decimal)):
        try:
            return Decimal(str(v))
        except Exception:
            return _ZERO
    return dec(v) if v else _ZERO


def extrair_ibscbs_item_imposto(imposto: Any) -> dict[str, Any]:
    """
    Normaliza um bloco IBSCBS de item (imposto_json) para auditoria e soma.
    Retorna chaves numéricas em Decimal serializáveis depois para float na API.
    """
    imposto_d = coercer_imposto_item_json(imposto) if imposto is not None else {}
    ib = _get_ibscbs_node(imposto_d)
    if not ib:
        return {'presente': False}
    cst = str(ib.get('CST') or '').strip()
    cclass = str(ib.get('cClassTrib') or '').strip()
    g = ib.get('gIBSCBS') if isinstance(ib.get('gIBSCBS'), dict) else ib.get('gibscbs')
    base = _ZERO
    v_cbs = _ZERO
    v_ibsuf = _ZERO
    v_ibsmun = _ZERO
    v_ibs = _ZERO
    p_cbs = None
    p_ibsuf = None
    p_ibsmun = None
    if isinstance(g, dict):
        base = _dec_any(g.get('vBC'))
        guf = g.get('gIBSUF')
        if isinstance(guf, dict):
            v_ibsuf = _dec_any(guf.get('vIBSUF'))
            p_ibsuf = guf.get('pIBSUF')
        gmun = g.get('gIBSMun')
        if isinstance(gmun, dict):
            v_ibsmun = _dec_any(gmun.get('vIBSMun'))
            p_ibsmun = gmun.get('pIBSMun')
        v_ibs = _dec_any(g.get('vIBS'))
        gcbs = g.get('gCBS')
        if isinstance(gcbs, dict):
            v_cbs = _dec_any(gcbs.get('vCBS'))
            p_cbs = gcbs.get('pCBS')
    tem_tag = bool(cst or cclass or (isinstance(g, dict) and len(g) > 0))
    tem_valor = (base + v_cbs + v_ibsuf + v_ibsmun + v_ibs) > _ZERO
    return {
        'presente': tem_tag,
        'cst': cst or None,
        'cclass_trib': cclass or None,
        'base': float(base.quantize(Decimal('0.01'))),
        'ibs_uf_aliquota': float(_dec_any(p_ibsuf)) if p_ibsuf is not None else None,
        'ibs_uf_valor': float(v_ibsuf.quantize(Decimal('0.01'))),
        'ibs_mun_aliquota': float(_dec_any(p_ibsmun)) if p_ibsmun is not None else None,
        'ibs_mun_valor': float(v_ibsmun.quantize(Decimal('0.01'))),
        'ibs_valor': float(v_ibs.quantize(Decimal('0.01'))),
        'cbs_aliquota': float(_dec_any(p_cbs)) if p_cbs is not None else None,
        'cbs_valor': float(v_cbs.quantize(Decimal('0.01'))),
        '_tem_valor_nao_zero': tem_valor,
    }


def extrair_ibscbstot_totais_json(totais_json: Any) -> dict[str, Any] | None:
    """Lê total/IBSCBSTot já materializado em totais_json (filhos de total/)."""
    ib = _resolver_bloco_ibscbstot(totais_json)
    if not isinstance(ib, dict):
        return None
    base = _dec_any(ib.get('vBCIBSCBS'))
    gibs = ib.get('gIBS')
    v_ibsuf = _ZERO
    v_ibsmun = _ZERO
    v_ibs = _ZERO
    if isinstance(gibs, dict):
        v_ibsuf = _dec_any(_dget(gibs, 'gIBSUF', 'vIBSUF'))
        v_ibsmun = _dec_any(_dget(gibs, 'gIBSMun', 'vIBSMun'))
        v_ibs = _dec_any(gibs.get('vIBS'))
    gcbs = ib.get('gCBS')
    v_cbs = _dec_any(gcbs.get('vCBS')) if isinstance(gcbs, dict) else _ZERO
    return {
        'presente': True,
        'base': float(base.quantize(Decimal('0.01'))),
        'ibs_uf_valor': float(v_ibsuf.quantize(Decimal('0.01'))),
        'ibs_mun_valor': float(v_ibsmun.quantize(Decimal('0.01'))),
        'ibs_total': float(v_ibs.quantize(Decimal('0.01'))),
        'cbs_valor': float(v_cbs.quantize(Decimal('0.01'))),
    }


def enriquecer_reforma_e_outros_json_nf(
    totais_json: dict[str, Any] | None,
    reforma_e_outros_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Acrescenta `ibscbs_total` (snapshot de total/IBSCBSTot) sem remover chaves extras vindas do infNFe."""
    base = dict(reforma_e_outros_json) if isinstance(reforma_e_outros_json, dict) else {}
    j = extrair_ibscbstot_totais_json(totais_json)
    if j:
        base['ibscbs_total'] = j
    return base


def enriquecer_reforma_e_outros_json_cte(
    imposto_json: dict[str, Any] | None,
    reforma_e_outros_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Acrescenta `ibscbs` a partir de infCte/imp (IBSCBS no mesmo formato da NF-e item)."""
    base = dict(reforma_e_outros_json) if isinstance(reforma_e_outros_json, dict) else {}
    snap = extrair_ibscbs_item_imposto(imposto_json if isinstance(imposto_json, dict) else None)
    if snap.get('presente'):
        base['ibscbs'] = {k: v for k, v in snap.items() if not str(k).startswith('_')}
    return base


def _flatten_keys(obj: Any, prefix: str = '') -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f'{prefix}.{k}' if prefix else str(k)
            keys.add(p)
            keys |= _flatten_keys(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:20]):
            keys |= _flatten_keys(v, f'{prefix}[{i}]')
    return keys


def _try_sum_known_reforma_totals(reforma_json: dict[str, Any]) -> dict[str, Decimal]:
    """Legado: chaves soltas em reforma_e_outros_json (infNFe fora do núcleo)."""
    out = {
        'valor_cbs': _ZERO,
        'valor_ibs_uf': _ZERO,
        'valor_ibs_municipio': _ZERO,
        'valor_is': _ZERO,
        'base_ibs': _ZERO,
        'base_cbs': _ZERO,
    }
    if not reforma_json:
        return out
    for k in ('vCBS', 'CBS'):
        if k in reforma_json and not isinstance(reforma_json[k], (dict, list)):
            out['valor_cbs'] += dec(reforma_json.get(k))
    for k in ('vIBS', 'IBS'):
        if k in reforma_json and not isinstance(reforma_json[k], (dict, list)):
            out['valor_ibs_uf'] += dec(reforma_json.get(k))
    for k in ('vIS', 'IS', 'vImpostoSeletivo'):
        if k in reforma_json and not isinstance(reforma_json[k], (dict, list)):
            out['valor_is'] += dec(reforma_json.get(k))
    return out


def processar_reforma_nfe_historica(
    totais_json: Any,
    reforma_e_outros_json: Any,
    itens_imposto_jsons: list[Any],
) -> tuple[dict[str, Decimal], list[str], dict[str, int]]:
    """
    Consolida CBS/IBS/IS de uma NF-e histórica: soma itens (gIBSCBS) e complementa com IBSCBSTot.

    Retorna:
    - dict para merge_totais_reforma (valores + bases)
    - alertas informativos do documento
    - estatísticas incrementais (contadores por nota)
    """
    alertas: list[str] = []
    stats = {
        'itens_com_tags_ibscbs': 0,
        'itens_com_valores_ibscbs': 0,
        'nota_com_ibscbstot': 0,
    }

    sum_base = _ZERO
    sum_cbs = _ZERO
    sum_ibsuf = _ZERO
    sum_ibsmun = _ZERO
    sum_ibs = _ZERO
    sum_is = _ZERO

    tem_item_g = False
    tem_item_so_cst = False

    for imp_raw in itens_imposto_jsons:
        imp = coercer_imposto_item_json(imp_raw)
        ib = _get_ibscbs_node(imp)
        if not ib:
            continue
        g = ib.get('gIBSCBS') if isinstance(ib.get('gIBSCBS'), dict) else ib.get('gibscbs')
        cst = str(ib.get('CST') or '').strip()
        cct = str(ib.get('cClassTrib') or '').strip()
        if isinstance(g, dict) and len(g) > 0:
            tem_item_g = True
            stats['itens_com_tags_ibscbs'] += 1
            ex = extrair_ibscbs_item_imposto(imp)
            if ex.get('_tem_valor_nao_zero'):
                stats['itens_com_valores_ibscbs'] += 1
            sum_base += _dec_any(_dget(g, 'vBC'))
            gcbs = g.get('gCBS')
            if isinstance(gcbs, dict):
                sum_cbs += _dec_any(gcbs.get('vCBS'))
            guf = g.get('gIBSUF')
            if isinstance(guf, dict):
                sum_ibsuf += _dec_any(guf.get('vIBSUF'))
            gmun = g.get('gIBSMun')
            if isinstance(gmun, dict):
                sum_ibsmun += _dec_any(gmun.get('vIBSMun'))
            sum_ibs += _dec_any(g.get('vIBS'))
        elif cst or cct:
            stats['itens_com_tags_ibscbs'] += 1
            tem_item_so_cst = True

    tot_doc = extrair_ibscbstot_totais_json(totais_json)
    if tot_doc:
        stats['nota_com_ibscbstot'] = 1

    usar_tot_doc = (not tem_item_g) and bool(tot_doc)
    if usar_tot_doc and tot_doc:
        sum_base = _dec_any(tot_doc.get('base'))
        sum_cbs = _dec_any(tot_doc.get('cbs_valor'))
        sum_ibsuf = _dec_any(tot_doc.get('ibs_uf_valor'))
        sum_ibsmun = _dec_any(tot_doc.get('ibs_mun_valor'))
        sum_ibs = _dec_any(tot_doc.get('ibs_total'))

    if tem_item_g and tot_doc:
        # Ambos: itens são fonte principal; tot documento para conferência silenciosa
        pass

    leg = _try_sum_known_reforma_totals(coercer_mapping_json(reforma_e_outros_json))
    if not tem_item_g and not usar_tot_doc:
        sum_cbs += leg['valor_cbs']
        sum_ibsuf += leg['valor_ibs_uf']
        sum_ibsmun += leg['valor_ibs_municipio']
        sum_is += leg['valor_is']

    if tem_item_so_cst and not tem_item_g:
        if tot_doc and sum_cbs + sum_ibsuf + sum_ibsmun + sum_ibs <= _ZERO:
            alertas.append(
                'Tags CBS/IBS encontradas, mas valores zerados no XML '
                '(CST/cClassTrib em IBSCBS no item; totais IBSCBSTot zerados ou sem gIBSCBS no item).'
            )
        elif not tot_doc:
            alertas.append(
                'Tags CBS/IBS encontradas no item (CST/cClassTrib em IBSCBS), sem grupo gIBSCBS e sem IBSCBSTot no total.'
            )

    if stats['itens_com_tags_ibscbs'] and stats['itens_com_valores_ibscbs'] == 0 and not tot_doc:
        if not alertas:
            alertas.append('Tags CBS/IBS encontradas nos itens, mas valores zerados no XML.')

    out_tot = {
        'valor_cbs': sum_cbs,
        'valor_ibs_uf': sum_ibsuf,
        'valor_ibs_municipio': sum_ibsmun,
        'valor_is': sum_is,
        'base_ibs': sum_base,
        'base_cbs': sum_base,
    }

    rj_outros = coercer_mapping_json(reforma_e_outros_json)
    if (
        not stats['itens_com_tags_ibscbs']
        and not tot_doc
        and rj_outros
        and not (out_tot['valor_cbs'] or out_tot['valor_ibs_uf'] or out_tot['valor_ibs_municipio'])
    ):
        keys_sample = sorted(list(_flatten_keys(rj_outros)))[:20]
        alertas.append(
            'Reforma tributária: reforma_e_outros_json presente sem IBSCBS nos itens/totais mapeados. '
            f'Amostra de chaves: {", ".join(keys_sample)}'
        )

    return out_tot, alertas, stats


def processar_reforma_cte_imposto(imposto_json: Any) -> tuple[dict[str, Decimal], list[str], dict[str, int]]:
    """Extrai CBS/IBS do CT-e (imposto_json = infCte/imp). Não usado na soma da apuração fiscal atual."""
    stats = {'cte_com_tags_ibscbs': 0, 'cte_com_valores_ibscbs': 0}
    imp = coercer_imposto_item_json(imposto_json)
    ib = _get_ibscbs_node(imp)
    if not ib:
        return {k: _ZERO for k in ('valor_cbs', 'valor_ibs_uf', 'valor_ibs_municipio', 'valor_is', 'base_ibs', 'base_cbs')}, [], stats
    stats['cte_com_tags_ibscbs'] = 1
    g = ib.get('gIBSCBS') if isinstance(ib.get('gIBSCBS'), dict) else ib.get('gibscbs')
    if not isinstance(g, dict):
        return {
            'valor_cbs': _ZERO,
            'valor_ibs_uf': _ZERO,
            'valor_ibs_municipio': _ZERO,
            'valor_is': _ZERO,
            'base_ibs': _ZERO,
            'base_cbs': _ZERO,
        }, [], stats
    base = _dec_any(g.get('vBC'))
    guf = g.get('gIBSUF')
    v_ibsuf = _dec_any(guf.get('vIBSUF')) if isinstance(guf, dict) else _ZERO
    gmun = g.get('gIBSMun')
    v_ibsmun = _dec_any(gmun.get('vIBSMun')) if isinstance(gmun, dict) else _ZERO
    v_ibs = _dec_any(g.get('vIBS'))
    gcbs = g.get('gCBS')
    v_cbs = _dec_any(gcbs.get('vCBS')) if isinstance(gcbs, dict) else _ZERO
    if base + v_cbs + v_ibsuf + v_ibsmun + v_ibs > _ZERO:
        stats['cte_com_valores_ibscbs'] = 1
    return {
        'valor_cbs': v_cbs,
        'valor_ibs_uf': v_ibsuf,
        'valor_ibs_municipio': v_ibsmun,
        'valor_is': _ZERO,
        'base_ibs': base,
        'base_cbs': base,
    }, [], stats


def processar_reforma_documento(reforma_e_outros_json: dict[str, Any] | None) -> tuple[dict[str, Decimal], list[str]]:
    """Compat: apenas JSON extra do infNFe (sem totais/itens). Preferir processar_reforma_nfe_historica na apuração."""
    rj = reforma_e_outros_json if isinstance(reforma_e_outros_json, dict) else {}
    leg = _try_sum_known_reforma_totals(rj)
    tot = {
        'valor_cbs': leg['valor_cbs'],
        'valor_ibs_uf': leg['valor_ibs_uf'],
        'valor_ibs_municipio': leg['valor_ibs_municipio'],
        'valor_is': leg['valor_is'],
        'base_ibs': leg['base_ibs'],
        'base_cbs': leg['base_cbs'],
    }
    alertas: list[str] = []
    if any(leg.values()):
        alertas.append('Reforma tributária: valores em chaves legadas em reforma_e_outros_json.')
    return tot, alertas


@dataclass
class TotaisReformaTributaria:
    base_cbs: Decimal = _ZERO
    aliquota_cbs: Decimal | None = None
    valor_cbs: Decimal = _ZERO
    base_ibs: Decimal = _ZERO
    aliquota_ibs_uf: Decimal | None = None
    valor_ibs_uf: Decimal = _ZERO
    aliquota_ibs_municipio: Decimal | None = None
    valor_ibs_municipio: Decimal = _ZERO
    base_is: Decimal = _ZERO
    aliquota_is: Decimal | None = None
    valor_is: Decimal = _ZERO
    notas_com_bloco_extra: int = 0
    itens_com_imposto_extra: int = 0
    itens_com_tags_ibscbs: int = 0
    itens_com_valores_ibscbs: int = 0
    notas_com_ibscbstot: int = 0
    notas_tags_ibscbs_zeradas: int = 0
    cte_com_ibscbs_tags: int = 0
    cte_com_ibscbs_valores: int = 0
    alertas: list[str] = field(default_factory=list)

    def to_serializable(self) -> dict[str, Any]:
        def f_money(d: Decimal) -> float:
            return float(d.quantize(Decimal('0.01')))

        def f_aliq(a: Decimal | None) -> float | None:
            if a is None:
                return None
            return float(a.quantize(Decimal('0.0001')))

        valor_ibs_total = self.valor_ibs_uf + self.valor_ibs_municipio
        return {
            'base_cbs': f_money(self.base_cbs),
            'aliquota_cbs': f_aliq(self.aliquota_cbs),
            'valor_cbs': f_money(self.valor_cbs),
            'base_ibs': f_money(self.base_ibs),
            'aliquota_ibs_uf': f_aliq(self.aliquota_ibs_uf),
            'valor_ibs_uf': f_money(self.valor_ibs_uf),
            'aliquota_ibs_municipio': f_aliq(self.aliquota_ibs_municipio),
            'valor_ibs_municipio': f_money(self.valor_ibs_municipio),
            'valor_ibs_total': f_money(valor_ibs_total),
            'base_is': f_money(self.base_is),
            'aliquota_is': f_aliq(self.aliquota_is),
            'valor_is': f_money(self.valor_is),
            'cst_reforma': None,
            'classificacao_tributaria': None,
            'cclass_trib': None,
            'notas_com_reforma_e_outros_json': self.notas_com_bloco_extra,
            'itens_com_tags_nao_mapeadas_imposto': self.itens_com_imposto_extra,
            'itens_com_tags_ibscbs': self.itens_com_tags_ibscbs,
            'itens_com_valores_ibscbs': self.itens_com_valores_ibscbs,
            'notas_com_ibscbstot': self.notas_com_ibscbstot,
            'notas_tags_ibscbs_zeradas': self.notas_tags_ibscbs_zeradas,
            'cte_com_tags_ibscbs': self.cte_com_ibscbs_tags,
            'cte_com_valores_ibscbs': self.cte_com_ibscbs_valores,
        }


def merge_totais_reforma(acum: TotaisReformaTributaria, doc_tot: dict[str, Any]) -> None:
    acum.valor_cbs += doc_tot.get('valor_cbs', _ZERO)
    acum.valor_ibs_uf += doc_tot.get('valor_ibs_uf', _ZERO)
    acum.valor_ibs_municipio += doc_tot.get('valor_ibs_municipio', _ZERO)
    acum.valor_is += doc_tot.get('valor_is', _ZERO)
    acum.base_ibs += doc_tot.get('base_ibs', _ZERO)
    acum.base_cbs += doc_tot.get('base_cbs', _ZERO)


def merge_stats_reforma_ibscbs(acum: TotaisReformaTributaria, stats: dict[str, int]) -> None:
    acum.itens_com_tags_ibscbs += int(stats.get('itens_com_tags_ibscbs', 0))
    acum.itens_com_valores_ibscbs += int(stats.get('itens_com_valores_ibscbs', 0))
    acum.notas_com_ibscbstot += int(stats.get('nota_com_ibscbstot', 0))
    if int(stats.get('itens_com_tags_ibscbs', 0)) > 0 and int(stats.get('itens_com_valores_ibscbs', 0)) == 0:
        acum.notas_tags_ibscbs_zeradas += 1


def merge_stats_reforma_cte(acum: TotaisReformaTributaria, stats: dict[str, int]) -> None:
    acum.cte_com_ibscbs_tags += int(stats.get('cte_com_tags_ibscbs', 0))
    acum.cte_com_ibscbs_valores += int(stats.get('cte_com_valores_ibscbs', 0))
