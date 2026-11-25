"""Duplicatas/fatura da NF-e Entrada importada (XML) — cópia operacional para financeiro."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from apps.comercial.payment_terms import compute_due_dates
from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada
from apps.fiscal.nfe_import.parser import _element_to_jsonable, _find_child, _local

CENTAVO = Decimal('0.01')

ORIGEM_PARCELAS_XML = 'XML'
ORIGEM_PARCELAS_PEDIDO = 'PEDIDO'
ORIGEM_PARCELAS_FALLBACK = 'EMISSAO'

MSG_XML_SEM_DUPLICATAS = (
    'O XML da NF-e não trouxe duplicatas válidas (cobr/dup). '
    'As parcelas foram sugeridas conforme pedido de compra ou data de emissão.'
)


def _round_money(v: Decimal | str | float | int) -> Decimal:
    return Decimal(str(v)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _parse_iso_date(value: str | date | None) -> date | None:
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _normalize_dup_list(cobr: dict[str, Any]) -> list[dict[str, Any]]:
    dup_raw = cobr.get('dup')
    if not dup_raw:
        return []
    if isinstance(dup_raw, list):
        return [d for d in dup_raw if isinstance(d, dict)]
    if isinstance(dup_raw, dict):
        return [dup_raw]
    return []


def _extrair_cobr_de_xml_texto(xml_text: str) -> dict[str, Any] | None:
    texto = (xml_text or '').strip()
    if not texto:
        return None
    try:
        root = ET.fromstring(texto)
    except ET.ParseError:
        return None

    inf = None
    for el in root.iter():
        if _local(el.tag) == 'infNFe':
            inf = el
            break
    if inf is None:
        return None

    cobr_el = _find_child(inf, 'cobr')
    if cobr_el is None:
        return None
    cobr_json = _element_to_jsonable(cobr_el)
    return cobr_json if isinstance(cobr_json, dict) else None


def _persistir_cobr_em_reforma(nf: NFeEntradaHistoricaImportada, cobr: dict[str, Any]) -> None:
    extra = dict(nf.reforma_e_outros_json or {})
    if extra.get('cobr') == cobr:
        return
    extra['cobr'] = cobr
    nf.reforma_e_outros_json = extra
    nf.save(update_fields=['reforma_e_outros_json'])


def obter_cobr_nf_entrada(nf: NFeEntradaHistoricaImportada) -> dict[str, Any] | None:
    """Retorna bloco cobr do JSON persistido ou parseado de xml_conteudo."""
    extra = nf.reforma_e_outros_json or {}
    cobr = extra.get('cobr')
    if isinstance(cobr, dict) and _normalize_dup_list(cobr):
        return cobr

    if (nf.xml_conteudo or '').strip():
        cobr_xml = _extrair_cobr_de_xml_texto(nf.xml_conteudo)
        if isinstance(cobr_xml, dict) and _normalize_dup_list(cobr_xml):
            _persistir_cobr_em_reforma(nf, cobr_xml)
            return cobr_xml

    return cobr if isinstance(cobr, dict) else None


def extrair_duplicatas_xml_nf_entrada(nf: NFeEntradaHistoricaImportada) -> list[dict[str, Any]]:
    """Extrai duplicatas do bloco cobr (reforma_e_outros_json ou xml_conteudo)."""
    cobr = obter_cobr_nf_entrada(nf)
    if not isinstance(cobr, dict):
        return []

    dups: list[dict[str, Any]] = []
    for idx, dup in enumerate(_normalize_dup_list(cobr), start=1):
        valor = _round_money(dup.get('vDup') or dup.get('valor') or 0)
        if valor <= 0:
            continue
        venc = _parse_iso_date(dup.get('dVenc') or dup.get('vencimento'))
        if not venc:
            continue
        num_raw = dup.get('nDup') or dup.get('numero') or idx
        try:
            numero = f'{int(str(num_raw).lstrip("0") or idx):03d}'
        except (TypeError, ValueError):
            numero = str(num_raw)
        dups.append(
            {
                'numero': numero,
                'n_dup': str(num_raw),
                'vencimento': venc.isoformat(),
                'valor': valor,
            },
        )
    return dups


def classificar_origem_parcelas_nf_entrada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> str:
    if extrair_duplicatas_xml_nf_entrada(nf):
        return ORIGEM_PARCELAS_XML
    if _parcelas_pedido_compra(nf, conferencia):
        return ORIGEM_PARCELAS_PEDIDO
    return ORIGEM_PARCELAS_FALLBACK


def _parcelas_pedido_compra(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None,
) -> list[dict[str, Any]]:
    pedido = conferencia.pedido_compra if conferencia and conferencia.pedido_compra_id else None
    if not pedido:
        return []

    vencs = [v for v in (pedido.vencimentos_previstos or []) if v]
    if not vencs and pedido.dias_parcelas:
        base = nf.dh_emissao.date() if nf.dh_emissao else date.today()
        vencs = compute_due_dates(base, list(pedido.dias_parcelas))
    if not vencs:
        return []

    total = _round_money(nf.valor_total_nf or 0)
    if total <= 0:
        return []

    count = len(vencs)
    quota = _round_money(total / Decimal(count))
    parcelas: list[dict[str, Any]] = []
    accumulated = Decimal('0.00')
    for idx, due in enumerate(vencs, start=1):
        if idx < count:
            amount = quota
            accumulated += amount
        else:
            amount = _round_money(total - accumulated)
        if amount <= 0:
            continue
        parcelas.append({'numero': f'{idx:03d}', 'vencimento': due.isoformat(), 'valor': amount})
    return parcelas


def montar_parcelas_sugeridas_nf_entrada(
    nf: NFeEntradaHistoricaImportada,
    conferencia: NFeEntradaConferencia | None = None,
) -> tuple[list[dict[str, Any]], str, str]:
    """
    Retorna (parcelas, origem, aviso).
    origem: XML | PEDIDO | EMISSAO
    """
    dups = extrair_duplicatas_xml_nf_entrada(nf)
    if dups:
        parcelas = [
            {
                'numero_parcela': int(d['numero']) if str(d['numero']).isdigit() else i,
                'n_dup': d.get('n_dup', d['numero']),
                'vencimento': d['vencimento'],
                'valor': str(d['valor']),
                'observacoes': '',
            }
            for i, d in enumerate(dups, start=1)
        ]
        return parcelas, ORIGEM_PARCELAS_XML, ''

    pedido_parcelas = _parcelas_pedido_compra(nf, conferencia)
    if pedido_parcelas:
        parcelas = [
            {
                'numero_parcela': int(d['numero']) if str(d['numero']).isdigit() else i,
                'vencimento': d['vencimento'],
                'valor': str(d['valor']),
                'observacoes': '',
            }
            for i, d in enumerate(pedido_parcelas, start=1)
        ]
        return parcelas, ORIGEM_PARCELAS_PEDIDO, MSG_XML_SEM_DUPLICATAS

    venc = nf.dh_emissao.date() if nf.dh_emissao else date.today()
    total = _round_money(nf.valor_total_nf or 0)
    if total <= 0:
        return [], ORIGEM_PARCELAS_FALLBACK, MSG_XML_SEM_DUPLICATAS
    parcelas = [
        {
            'numero_parcela': 1,
            'vencimento': venc.isoformat(),
            'valor': str(total),
            'observacoes': '',
        },
    ]
    return parcelas, ORIGEM_PARCELAS_FALLBACK, MSG_XML_SEM_DUPLICATAS
