"""Composição física por barra na conferência NF-e entrada (Fase 1)."""

from __future__ import annotations

from decimal import Decimal

from apps.fiscal.models import ItemNFeEntradaConferencia, ItemNFeEntradaConferenciaEquivalencia

TOLERANCIA_COMPOSICAO = Decimal('0.001')

ORIGEM_COMPOSICAO_BARRAS = 'COMPOSICAO_BARRAS'
REGRA_KG_PARA_M_PESO_POR_METRO = 'KG_PARA_M_PESO_POR_METRO'


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))


def item_controla_composicao_fisica(item: ItemNFeEntradaConferencia) -> bool:
    if not item.produto_id:
        return False
    return bool(item.produto.get_controla_composicao_fisica_efetivo())


def _peso_por_metro_produto(item: ItemNFeEntradaConferencia) -> Decimal | None:
    if not item.produto_id:
        return None
    ppm = item.produto.get_peso_por_metro_kg_efetivo()
    if not ppm:
        return None
    val = _dec(ppm)
    return val if val > 0 else None


def quantidade_alvo_composicao_metros(
    item: ItemNFeEntradaConferencia,
) -> tuple[Decimal | None, str | None, dict]:
    """
    Retorna (metros_alvo, erro, metadados).
    metadados: regra_conversao, fator, unidade_nf, quantidade_nf, metros_convertidos_nf
    """
    u = (item.unidade_nf or '').strip().upper()
    qty = _dec(item.quantidade_nf)
    meta: dict = {
        'unidade_nf_original': u,
        'quantidade_nf_original': str(qty),
        'regra_conversao': None,
        'fator_conversao_utilizado': None,
        'metros_convertidos_nf': None,
    }
    if u == 'M':
        meta['metros_convertidos_nf'] = str(qty)
        return qty, None, meta
    if u in ('KG', 'TON'):
        ppm = _peso_por_metro_produto(item)
        if not ppm:
            return (
                None,
                'Informe peso por metro no cadastro do produto/família para converter KG em metros.',
                meta,
            )
        kg = qty * Decimal('1000') if u == 'TON' else qty
        metros = (kg / ppm).quantize(Decimal('0.001'))
        meta['regra_conversao'] = REGRA_KG_PARA_M_PESO_POR_METRO
        meta['fator_conversao_utilizado'] = str(ppm)
        meta['metros_convertidos_nf'] = str(metros)
        return metros, None, meta
    return (
        None,
        f'Composição física na conferência ainda não suporta NF em {u or "unidade indefinida"}.',
        meta,
    )


def _equivalencias_rows(
    item: ItemNFeEntradaConferencia,
    equivalencias_payload: list[dict] | None = None,
) -> list[dict | ItemNFeEntradaConferenciaEquivalencia]:
    if equivalencias_payload is not None:
        return [row for row in equivalencias_payload if isinstance(row, dict)]
    if hasattr(item, '_prefetched_objects_cache') and 'equivalencias' in item._prefetched_objects_cache:
        return sorted(item.equivalencias.all(), key=lambda e: (e.ordem, e.id))
    return list(item.equivalencias.order_by('ordem', 'id'))


def _metros_sub_linha(row: dict | ItemNFeEntradaConferenciaEquivalencia) -> Decimal:
    if isinstance(row, dict):
        return _dec(row.get('metros'))
    return _dec(row.metros)


def validar_composicao_fisica_equivalencias(
    item: ItemNFeEntradaConferencia,
    equivalencias_payload: list[dict] | None = None,
) -> list[str]:
    """Valida soma dos comprimentos reais (metros) contra alvo da NF (direto ou convertido de KG)."""
    rows = _equivalencias_rows(item, equivalencias_payload)
    if not rows:
        return []

    erros: list[str] = []
    alvo, erro_alvo, _meta = quantidade_alvo_composicao_metros(item)
    if erro_alvo:
        return [erro_alvo]

    soma_metros = sum(_metros_sub_linha(row) for row in rows)
    if alvo is not None and abs(soma_metros - alvo) > TOLERANCIA_COMPOSICAO:
        erros.append(
            f'A soma dos comprimentos das barras ({soma_metros:.3f} M) deve ser igual à '
            f'quantidade da NF em metros ({alvo:.3f} M).',
        )

    for idx, row in enumerate(rows, start=1):
        ordem = int(row.get('ordem') or idx) if isinstance(row, dict) else row.ordem
        metros = _metros_sub_linha(row)
        if metros <= 0:
            erros.append(f'Barra {ordem}: informe o comprimento real em metros.')
        barras = _dec(row.get('barras') if isinstance(row, dict) else row.barras)
        if barras > 0:
            erros.append(
                f'Barra {ordem}: use apenas comprimento em metros; quantidade em BR não é usada na composição.',
            )
    return erros


def montar_auditoria_composicao_fisica(
    item: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> dict:
    _alvo, _erro, meta = quantidade_alvo_composicao_metros(item)
    metros_total = sum(_dec(e.metros or 0) for e in equivs)
    composicao = [
        {
            'ordem': e.ordem,
            'metros': str(e.metros) if e.metros is not None else None,
            'peso_kg': str(e.peso_kg) if e.peso_kg is not None else None,
            'peso_por_metro_utilizado': (
                str(e.peso_por_metro_utilizado) if e.peso_por_metro_utilizado is not None else None
            ),
        }
        for e in equivs
    ]
    ppm = _peso_por_metro_produto(item)
    peso_total = sum(_dec(e.peso_kg or 0) for e in equivs)
    if peso_total <= 0 and ppm and metros_total > 0:
        peso_total = metros_total * ppm

    return {
        **meta,
        'unidade_estoque_calculada': 'M',
        'quantidade_estoque_calculada': str(metros_total),
        'origem_conversao': ORIGEM_COMPOSICAO_BARRAS,
        'barras_informadas': len(equivs),
        'metros_total_composicao': str(metros_total),
        'peso_total_kg_estimado': str(peso_total.quantize(Decimal('0.001'))) if peso_total else None,
        'composicao': composicao,
    }


def aplicar_totais_composicao_fisica_item(
    item_conf: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> None:
    """Define estoque calculado em M a partir da composição informada."""
    metros_total = sum(_dec(e.metros or 0) for e in equivs)
    ppm = _peso_por_metro_produto(item_conf)
    peso_total = sum(_dec(e.peso_kg or 0) for e in equivs)
    if peso_total <= 0 and ppm and metros_total > 0:
        peso_total = metros_total * ppm

    item_conf.unidade_estoque_calculada = 'M'
    item_conf.quantidade_estoque_calculada = metros_total
    item_conf.metros_total = metros_total
    item_conf.barras_total = Decimal(len(equivs))
    item_conf.peso_total_kg = peso_total
    item_conf.toneladas_total = (
        (peso_total / Decimal('1000')).quantize(Decimal('0.001')) if peso_total else Decimal('0')
    )
    item_conf.conversao_estoque_auditoria = montar_auditoria_composicao_fisica(item_conf, equivs)
