"""Perfil fiscal Lucro Presumido — devolução/recusa de venda (entrada própria finNFe=4)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from apps.fiscal.snapshot_fiscal_helpers import get_ipi_snapshot, get_reforma_tributaria_snapshot

Q2 = Decimal('0.01')
Q4 = Decimal('0.0001')

# PIS/COFINS em devolução (LP): CST 98 (Outras Entradas) com alíquotas espelhadas da saída.
CST_PIS_DEVOLUCAO_LP = '98'
CST_COFINS_DEVOLUCAO_LP = '98'
CST_IPI_DEVOLUCAO = '49'
P_DEVOL_PADRAO = '100.00'


def _digits(val: Any, *, max_len: int | None = None) -> str:
    out = ''.join(c for c in str(val or '') if c.isdigit())
    if max_len is not None:
        return out[:max_len]
    return out


def _dec(val: Any) -> Decimal | None:
    if val is None or val == '':
        return None
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return None


def _money(val: Decimal) -> str:
    return str(val.quantize(Q2, rounding=ROUND_HALF_UP))


def _pct(val: Decimal) -> str:
    return str(val.quantize(Q4, rounding=ROUND_HALF_UP))


def cfop_entrada_devolucao_from_saida(
    cfop_saida: str,
    *,
    mesma_uf: bool | None = None,
) -> str:
    """
    Mapeia CFOP da venda original → CFOP de devolução/recusa:

    - Mesma UF + produção própria (…01) → 1201
    - Mesma UF + revenda de terceiros (…02 ou demais) → 1202
    - Outra UF + produção própria → 2201
    - Outra UF + revenda de terceiros → 2202

    ``mesma_uf`` sobrescreve o dígito 5/6 do CFOP quando informado (UF emitente × destinatário).
    """
    digits = _digits(cfop_saida, max_len=4)
    if mesma_uf is None:
        interestadual = digits.startswith('6')
    else:
        interestadual = not mesma_uf

    # Produção própria: CFOPs de saída …01 (5101, 6101, 5401…).
    # Revenda: …02 (5102, 6102…) — default quando sufixo não é 01.
    sufixo = digits[2:4] if len(digits) == 4 else '02'
    producao_propria = sufixo == '01'

    if interestadual:
        return '2201' if producao_propria else '2202'
    return '1201' if producao_propria else '1202'


def _bloco_ou_vazio(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def reforma_tributaria_from_snapshot_saida(snapshot_fiscal: dict[str, Any] | None) -> dict[str, Any] | None:
    """Copia bloco reforma calculado da saída (CBS 0,9% / IBS 0,1% na transição 2026)."""
    ref = get_reforma_tributaria_snapshot(snapshot_fiscal)
    if not ref:
        return None
    return dict(ref)


def reforma_tributaria_from_imposto_xml(imposto_json: dict[str, Any] | None) -> dict[str, Any] | None:
    """Converte IBSCBS do XML importado para o shape de reforma_tributaria do ERP."""
    from apps.fiscal.services.reforma_tributaria import extrair_ibscbs_item_imposto

    ext = extrair_ibscbs_item_imposto(imposto_json)
    if not ext.get('presente'):
        return None
    out: dict[str, Any] = {
        'cst_ibs_cbs': str(ext.get('cst') or '000'),
        'classificacao_tributaria': str(ext.get('cclass_trib') or '000001'),
    }
    if ext.get('base') is not None:
        out['base_cbs'] = str(ext['base'])
        out['base_ibs'] = str(ext['base'])
        out['base_ibs_estadual'] = str(ext['base'])
    if ext.get('cbs_aliquota') is not None:
        out['aliquota_cbs'] = str(ext['cbs_aliquota'])
    if ext.get('cbs_valor') is not None:
        out['valor_cbs'] = str(ext['cbs_valor'])
    if ext.get('ibs_uf_aliquota') is not None:
        out['aliquota_ibs_estadual'] = str(ext['ibs_uf_aliquota'])
    if ext.get('ibs_uf_valor') is not None:
        out['valor_ibs_estadual'] = str(ext['ibs_uf_valor'])
    if ext.get('ibs_mun_aliquota') is not None:
        out['aliquota_ibs_municipal'] = str(ext['ibs_mun_aliquota'])
    if ext.get('ibs_mun_valor') is not None:
        out['valor_ibs_municipal'] = str(ext['ibs_mun_valor'])
    return out


def aplicar_perfil_impostos_devolucao_lucro_presumido(
    impostos: dict[str, Any] | None,
    *,
    snapshot_fiscal_saida: dict[str, Any] | None = None,
    reforma_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Ajusta impostos espelhados da saída para o perfil LP de devolução/recusa:

    - PIS/COFINS → CST 98, mantendo base/alíquota/valor da saída
    - ICMS → inalterado (CST e destaque da saída)
    - IPI → CST 49 + imposto_devol (vIPIDevol) quando a saída tinha IPI
    - Reforma → replica CBS/IBS calculados na saída
    """
    out = dict(impostos) if isinstance(impostos, dict) else {}
    pis = _bloco_ou_vazio(out.get('pis'))
    cof = _bloco_ou_vazio(out.get('cofins'))
    icms = _bloco_ou_vazio(out.get('icms'))
    ipi = _bloco_ou_vazio(out.get('ipi'))

    if pis:
        pis = {**pis, 'cst': CST_PIS_DEVOLUCAO_LP}
    else:
        pis = {'cst': CST_PIS_DEVOLUCAO_LP}
    if cof:
        cof = {**cof, 'cst': CST_COFINS_DEVOLUCAO_LP}
    else:
        cof = {'cst': CST_COFINS_DEVOLUCAO_LP}

    # IPI da saída (nested ou flat no snapshot)
    if not ipi.get('valor') and not ipi.get('base') and snapshot_fiscal_saida:
        snap_ipi = get_ipi_snapshot(snapshot_fiscal_saida)
        if snap_ipi.get('valor') or snap_ipi.get('base') or snap_ipi.get('aliquota'):
            ipi = {
                'cst': snap_ipi.get('cst') or '',
                'base': snap_ipi.get('base') or None,
                'aliquota': snap_ipi.get('aliquota') or None,
                'valor': snap_ipi.get('valor') or None,
            }

    v_ipi = _dec(ipi.get('valor'))
    if v_ipi is not None and v_ipi > 0:
        ipi = {
            **ipi,
            'cst': CST_IPI_DEVOLUCAO,
        }
        p_devol = out.get('imposto_devol') if isinstance(out.get('imposto_devol'), dict) else {}
        p_pct = _dec(p_devol.get('p_devol') or p_devol.get('pDevol')) or Decimal('100')
        out['imposto_devol'] = {
            'p_devol': _pct(p_pct) if p_pct != Decimal('100') else P_DEVOL_PADRAO,
            'v_ipi_devol': _money(v_ipi),
        }
        out['ipi'] = ipi
    elif ipi.get('cst') or ipi.get('base') or ipi.get('aliquota'):
        # IPI informado sem valor — ainda assim marca CST 49 para devolução
        out['ipi'] = {**ipi, 'cst': CST_IPI_DEVOLUCAO or ipi.get('cst')}

    out['pis'] = pis
    out['cofins'] = cof
    if icms:
        out['icms'] = icms

    reforma = reforma_extra
    if reforma is None and snapshot_fiscal_saida:
        reforma = reforma_tributaria_from_snapshot_saida(snapshot_fiscal_saida)
    if reforma:
        out['reforma_tributaria'] = reforma

    meta = out.get('_meta') if isinstance(out.get('_meta'), dict) else {}
    out['_meta'] = {
        **meta,
        'perfil_devolucao': 'lucro_presumido_2026',
    }
    return out
