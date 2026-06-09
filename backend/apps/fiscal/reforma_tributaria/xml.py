"""Builders XML Reforma Tributária (IBSCBS / IBSCBSTot) — camada central NF-e."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from apps.fiscal.nfe_saida_reforma_calculo import status_reforma_snapshot
from apps.fiscal.reforma_tributaria.validacoes import reforma_deve_serializar_no_xml
from apps.fiscal.snapshot_fiscal_helpers import get_reforma_tributaria_snapshot


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _fmt2(val: Any) -> str | None:
    d = _dec(val)
    if d == 0 and (val is None or _text(val) == ''):
        return None
    return f'{d.quantize(Decimal("0.01")):.2f}'


def _fmt4(val: Any) -> str | None:
    d = _dec(val)
    if d == 0 and (val is None or _text(val) == ''):
        return None
    return f'{d.quantize(Decimal("0.0001")):.4f}'


def reforma_calculada_no_item(linha: dict[str, Any] | None) -> bool:
    """True quando o snapshot do item possui Reforma calculada (CST + classificação + valores)."""
    if not linha:
        return False
    snap = linha.get('snapshot_fiscal') or {}
    reforma = get_reforma_tributaria_snapshot(snap)
    return status_reforma_snapshot(reforma) == 'CALCULADA'


def nf_tem_reforma_calculada(itens: list[dict[str, Any]] | None) -> bool:
    return any(reforma_calculada_no_item(l) for l in itens or [])


def _reforma_snapshot_item(linha: dict[str, Any]) -> dict[str, Any]:
    return get_reforma_tributaria_snapshot(linha.get('snapshot_fiscal') or {}) or {}


def build_reforma_tributaria_item_bindings(
    linha: dict[str, Any] | None,
    contexto: dict[str, Any] | None = None,
) -> Any | None:
    """
    Retorna bindings ``TtribNfe`` (imposto/IBSCBS) quando flags RTC e snapshot permitem serialização.
    """
    _ = contexto
    if not reforma_deve_serializar_no_xml():
        return None
    if not linha or not reforma_calculada_no_item(linha):
        return None

    from nfelib.nfe.bindings.v4_0 import dfe_tipos_basicos_v1_00 as dfe

    ref = _reforma_snapshot_item(linha)
    cst = _text(ref.get('cst_ibs_cbs')) or '000'
    cclass = _text(ref.get('classificacao_tributaria')) or '000001'
    base = _fmt2(ref.get('base_cbs') or ref.get('base_ibs') or ref.get('base_ibs_estadual'))
    v_cbs = _fmt2(ref.get('valor_cbs'))
    v_ibs_uf = _fmt2(ref.get('valor_ibs_estadual') or ref.get('valor_ibs_uf'))
    v_ibs_mun = _fmt2(ref.get('valor_ibs_municipal') or ref.get('valor_ibs_mun'))
    p_cbs = _fmt4(ref.get('aliquota_cbs'))
    p_ibs_uf = _fmt4(ref.get('aliquota_ibs_estadual'))
    p_ibs_mun = _fmt4(ref.get('aliquota_ibs_municipal'))

    v_ibs = _fmt2(ref.get('valor_ibs'))
    if not v_ibs:
        soma = _dec(v_ibs_uf) + _dec(v_ibs_mun)
        v_ibs = f'{soma.quantize(Decimal("0.01")):.2f}' if soma > 0 else '0.00'

    gibsuf = None
    if p_ibs_uf or v_ibs_uf:
        gibsuf = dfe.Tcibs.GIbsuf(
            pIBSUF=p_ibs_uf,
            vIBSUF=v_ibs_uf or '0.00',
        )

    gibsmun = None
    if p_ibs_mun or _dec(v_ibs_mun) > 0:
        gibsmun = dfe.Tcibs.GIbsmun(
            pIBSMun=p_ibs_mun or '0.0000',
            vIBSMun=v_ibs_mun or '0.00',
        )

    gcbs = None
    if p_cbs or v_cbs:
        gcbs = dfe.Tcibs.GCbs(
            pCBS=p_cbs,
            vCBS=v_cbs or '0.00',
        )

    return dfe.TtribNfe(
        CST=cst.zfill(3)[:3],
        cClassTrib=cclass.zfill(6)[:6],
        gIBSCBS=dfe.Tcibs(
            vBC=base or '0.00',
            gIBSUF=gibsuf,
            gIBSMun=gibsmun,
            vIBS=v_ibs or '0.00',
            gCBS=gcbs,
        ),
    )


def _agregar_totais_reforma_itens(itens: list[dict[str, Any]]) -> dict[str, Decimal] | None:
    base = v_cbs = v_ibs_uf = v_ibs_mun = v_ibs = v_total = Decimal('0')
    tem = False
    for linha in itens:
        if not reforma_calculada_no_item(linha):
            continue
        ref = _reforma_snapshot_item(linha)
        tem = True
        base += _dec(ref.get('base_cbs') or ref.get('base_ibs') or ref.get('base_ibs_estadual'))
        v_cbs += _dec(ref.get('valor_cbs'))
        v_ibs_uf += _dec(ref.get('valor_ibs_estadual') or ref.get('valor_ibs_uf'))
        v_ibs_mun += _dec(ref.get('valor_ibs_municipal') or ref.get('valor_ibs_mun'))
        v_total += _dec(ref.get('valor_total_ibs_cbs'))
    if not tem:
        return None
    v_ibs = v_ibs_uf + v_ibs_mun
    if v_total <= 0:
        v_total = v_cbs + v_ibs
    return {
        'base': base,
        'valor_cbs': v_cbs,
        'valor_ibs_uf': v_ibs_uf,
        'valor_ibs_mun': v_ibs_mun,
        'valor_ibs': v_ibs,
        'valor_total_ibs_cbs': v_total,
    }


def build_reforma_tributaria_total_bindings(
    itens: list[dict[str, Any]] | None,
    contexto: dict[str, Any] | None = None,
) -> Any | None:
    """Retorna bindings ``TibscbsmonoTot`` (total/IBSCBSTot) quando flags RTC permitem serialização."""
    _ = contexto
    if not reforma_deve_serializar_no_xml():
        return None
    agg = _agregar_totais_reforma_itens(list(itens or []))
    if not agg:
        return None

    from nfelib.nfe.bindings.v4_0 import dfe_tipos_basicos_v1_00 as dfe

    return dfe.TibscbsmonoTot(
        vBCIBSCBS=_fmt2(agg['base']) or '0.00',
        gIBS=dfe.TibscbsmonoTot.GIbs(
            gIBSUF=dfe.TibscbsmonoTot.GIbs.GIbsuf(
                vIBSUF=_fmt2(agg['valor_ibs_uf']) or '0.00',
            ),
            gIBSMun=dfe.TibscbsmonoTot.GIbs.GIbsmun(
                vIBSMun=_fmt2(agg['valor_ibs_mun']) or '0.00',
            ),
            vIBS=_fmt2(agg['valor_ibs']) or '0.00',
        ),
        gCBS=dfe.TibscbsmonoTot.GCbs(
            vCBS=_fmt2(agg['valor_cbs']) or '0.00',
        ),
    )


def xml_contem_reforma_tributaria(xml: str) -> bool:
    """Detecta presença de grupos oficiais IBSCBS / IBSCBSTot no XML serializado."""
    if not xml:
        return False
    low = xml.lower()
    return 'ibscbs' in low or 'ibscbstot' in low


def _xml_valor_tag(xml: str, tag: str) -> Decimal | None:
    m = re.search(rf'<(?:[\w]{{1,12}}:)?{re.escape(tag)}>([^<]+)</', xml, re.IGNORECASE)
    if not m:
        return None
    return _dec(m.group(1))


def extrair_resumo_reforma_xml(xml: str) -> dict[str, Any] | None:
    """Extrai valores CBS/IBS UF do XML para exibição/diagnóstico."""
    if not xml_contem_reforma_tributaria(xml):
        return None
    v_cbs = _xml_valor_tag(xml, 'vCBS')
    v_ibs_uf = _xml_valor_tag(xml, 'vIBSUF')
    v_ibs_mun = _xml_valor_tag(xml, 'vIBSMun')
    v_ibs = _xml_valor_tag(xml, 'vIBS')
    return {
        'presente': True,
        'valor_cbs': float(v_cbs) if v_cbs is not None else None,
        'valor_ibs_uf': float(v_ibs_uf) if v_ibs_uf is not None else None,
        'valor_ibs_mun': float(v_ibs_mun) if v_ibs_mun is not None else None,
        'valor_ibs': float(v_ibs) if v_ibs is not None else None,
    }


def mensagem_reforma_xml_ok(resumo: dict[str, Any] | None) -> str | None:
    if not resumo or not resumo.get('presente'):
        return None
    partes: list[str] = []
    if resumo.get('valor_cbs') is not None:
        partes.append(f"CBS R$ {resumo['valor_cbs']:.2f}".replace('.', ','))
    if resumo.get('valor_ibs_uf') is not None:
        partes.append(f"IBS UF R$ {resumo['valor_ibs_uf']:.2f}".replace('.', ','))
    if not partes:
        return 'XML contém Reforma Tributária (IBSCBS).'
    return f"XML contém Reforma Tributária: {' · '.join(partes)}."


def totais_reforma_esperados_itens(itens: list[dict[str, Any]] | None) -> dict[str, Decimal] | None:
    return _agregar_totais_reforma_itens(list(itens or []))


def validar_reforma_serializada_em_xml(
    xml: str,
    *,
    itens: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """
    Compara snapshot calculado com grupos IBSCBS no XML.
    Retorna lista de {tipo, codigo, mensagem}.
    """
    if not nf_tem_reforma_calculada(itens):
        return []
    if not reforma_deve_serializar_no_xml():
        if xml_contem_reforma_tributaria(xml):
            return [
                {
                    'tipo': 'PENDENCIA',
                    'codigo': 'REFORMA_XML_INESPERADA',
                    'mensagem': 'XML contém IBSCBS, mas flags RTC não permitem serialização.',
                }
            ]
        return []
    erros: list[dict[str, str]] = []
    if not xml_contem_reforma_tributaria(xml):
        return [
            {
                'tipo': 'PENDENCIA',
                'codigo': 'REFORMA_AUSENTE_XML',
                'mensagem': 'Reforma calculada na conferência, mas ausente no XML.',
            }
        ]
    resumo = extrair_resumo_reforma_xml(xml)
    esperado = totais_reforma_esperados_itens(itens)
    if esperado and resumo:
        tol = Decimal('0.02')
        if abs(_dec(resumo.get('valor_cbs')) - esperado['valor_cbs']) > tol:
            erros.append(
                {
                    'tipo': 'PENDENCIA',
                    'codigo': 'REFORMA_XML_CBS_DIVERGENTE',
                    'mensagem': (
                        f'Valor CBS no XML ({resumo.get("valor_cbs")}) diverge do snapshot '
                        f'({esperado["valor_cbs"]}).'
                    ),
                },
            )
        if abs(_dec(resumo.get('valor_ibs_uf')) - esperado['valor_ibs_uf']) > tol:
            erros.append(
                {
                    'tipo': 'PENDENCIA',
                    'codigo': 'REFORMA_XML_IBS_UF_DIVERGENTE',
                    'mensagem': (
                        f'Valor IBS UF no XML ({resumo.get("valor_ibs_uf")}) diverge do snapshot '
                        f'({esperado["valor_ibs_uf"]}).'
                    ),
                },
            )
    msg_ok = mensagem_reforma_xml_ok(resumo)
    if msg_ok and not erros:
        return [
            {
                'tipo': 'INFO',
                'codigo': 'REFORMA_XML_OK',
                'mensagem': msg_ok,
            }
        ]
    return erros


def xml_deve_permanecer_sem_reforma(itens: list[dict[str, Any]] | None = None) -> bool:
    """True quando nenhum item possui Reforma calculada no snapshot."""
    return not nf_tem_reforma_calculada(itens)
