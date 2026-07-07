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


MSG_EQUIV_LEGADO_REMOVIDA = (
    'Equivalência antiga (BR/kg) removida: informe a composição por grupo de barras (qtd × comprimento em M).'
)


def equivalencias_sao_legado_para_composicao(
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> bool:
    """True quando sub-linhas usam formato antigo (BR/kg) em vez de composição por grupo."""
    if not equivs:
        return False
    for equiv in equivs:
        if _dec(equiv.peso_kg) > 0:
            return True
        has_novo = bool(equiv.qtd_barras) and _dec(equiv.comprimento_unitario_m) > 0
        if has_novo:
            continue
        if _dec(equiv.barras) > 0:
            return True
        if _dec(equiv.metros) > 0 and not equiv.qtd_barras and not _dec(equiv.comprimento_unitario_m):
            return True
    return False


def limpar_equivalencias_legado_se_composicao_fisica(
    item: ItemNFeEntradaConferencia,
) -> bool:
    """
    Remove equivalências gravadas no formato antigo quando o produto passou a usar composição física.
    Retorna True se houve limpeza.
    """
    if not item_controla_composicao_fisica(item):
        return False
    if item.estoque_aplicado_em:
        return False
    equivs = list(item.equivalencias.order_by('ordem', 'id'))
    if not equivalencias_sao_legado_para_composicao(equivs):
        return False
    item.equivalencias.all().delete()
    item.quantidade_estoque_calculada = Decimal('0')
    item.metros_total = Decimal('0')
    item.barras_total = Decimal('0')
    item.peso_total_kg = Decimal('0')
    item.toneladas_total = Decimal('0')
    item.conversao_estoque_auditoria = {}
    return True


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


def _qtd_barras_row(row: dict | ItemNFeEntradaConferenciaEquivalencia) -> int:
    if isinstance(row, dict):
        raw = row.get('qtd_barras')
        if raw in (None, ''):
            return 0
        return int(_dec(raw))
    if row.qtd_barras:
        return int(row.qtd_barras)
    return 0


def _comprimento_unitario_row(row: dict | ItemNFeEntradaConferenciaEquivalencia) -> Decimal:
    if isinstance(row, dict):
        comp = row.get('comprimento_unitario_m')
        if comp not in (None, ''):
            return _dec(comp)
        metros = _dec(row.get('metros'))
        qtd = _qtd_barras_row(row)
        if qtd == 1 and metros > 0:
            return metros
        return Decimal('0')
    if row.comprimento_unitario_m is not None:
        return _dec(row.comprimento_unitario_m)
    metros = _dec(row.metros)
    qtd = _qtd_barras_row(row)
    if qtd == 1 and metros > 0:
        return metros
    return Decimal('0')


def total_linha_composicao_m(row: dict | ItemNFeEntradaConferenciaEquivalencia) -> Decimal:
    """total_linha_m = qtd_barras × comprimento_unitario_m"""
    qtd = _qtd_barras_row(row)
    comp = _comprimento_unitario_row(row)
    if qtd > 0 and comp > 0:
        return (Decimal(qtd) * comp).quantize(Decimal('0.001'))
    return _dec(row.get('metros') if isinstance(row, dict) else row.metros)


def total_barras_composicao(
    rows: list[dict | ItemNFeEntradaConferenciaEquivalencia],
) -> int:
    return sum(_qtd_barras_row(row) for row in rows)


def expandir_barras_fisicas_composicao(
    equiv: ItemNFeEntradaConferenciaEquivalencia,
) -> list[Decimal]:
    """Expande um grupo em N comprimentos individuais (uma barra física cada)."""
    qtd = _qtd_barras_row(equiv)
    comp = _comprimento_unitario_row(equiv)
    if qtd <= 0 or comp <= 0:
        return []
    return [comp] * qtd


def normalizar_linha_composicao_payload(row: dict) -> dict:
    """Preenche metros (total da linha) a partir de qtd × comprimento."""
    out = dict(row)
    qtd = _qtd_barras_row(row)
    comp = _comprimento_unitario_row(row)
    if qtd > 0 and comp > 0:
        total = (Decimal(qtd) * comp).quantize(Decimal('0.001'))
        out['qtd_barras'] = qtd
        out['comprimento_unitario_m'] = str(comp.quantize(Decimal('0.001')))
        out['metros'] = str(total)
    elif _dec(row.get('metros')) > 0 and qtd <= 0:
        metros = _dec(row.get('metros'))
        out['qtd_barras'] = 1
        out['comprimento_unitario_m'] = str(metros.quantize(Decimal('0.001')))
        out['metros'] = str(metros.quantize(Decimal('0.001')))
    out['barras'] = None
    out['peso_kg'] = None
    return out


def validar_composicao_fisica_equivalencias(
    item: ItemNFeEntradaConferencia,
    equivalencias_payload: list[dict] | None = None,
) -> list[str]:
    """Valida Σ(qtd_barras × comprimento_unitario_m) contra alvo da NF em metros."""
    rows = _equivalencias_rows(item, equivalencias_payload)
    if not rows:
        return []

    erros: list[str] = []
    alvo, erro_alvo, _meta = quantidade_alvo_composicao_metros(item)
    if erro_alvo:
        return [erro_alvo]

    soma_metros = sum(total_linha_composicao_m(row) for row in rows)
    if alvo is not None and abs(soma_metros - alvo) > TOLERANCIA_COMPOSICAO:
        erros.append(
            f'A soma total em metros ({soma_metros:.3f} M) deve ser igual à '
            f'quantidade da NF em metros ({alvo:.3f} M).',
        )

    for idx, row in enumerate(rows, start=1):
        ordem = int(row.get('ordem') or idx) if isinstance(row, dict) else row.ordem
        qtd = _qtd_barras_row(row)
        comp = _comprimento_unitario_row(row)
        if qtd <= 0:
            erros.append(f'Grupo {ordem}: informe a quantidade de barras (número inteiro ≥ 1).')
        elif Decimal(qtd) != Decimal(int(qtd)):
            erros.append(f'Grupo {ordem}: quantidade de barras deve ser um número inteiro.')
        if comp <= 0:
            erros.append(f'Grupo {ordem}: informe o comprimento unitário da barra em metros.')
        peso = _dec(row.get('peso_kg') if isinstance(row, dict) else row.peso_kg)
        if peso > 0:
            erros.append(f'Grupo {ordem}: use qtd. barras e comprimento unitário (M); peso (kg) não se aplica.')
        leg_barras = _dec(row.get('barras') if isinstance(row, dict) else row.barras)
        if leg_barras > 0 and qtd <= 0:
            erros.append(f'Grupo {ordem}: use o campo quantidade de barras, não BR legado.')
    return erros


def montar_auditoria_composicao_fisica(
    item: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> dict:
    _alvo, _erro, meta = quantidade_alvo_composicao_metros(item)
    metros_total = sum(total_linha_composicao_m(e) for e in equivs)
    barras_total = total_barras_composicao(equivs)
    composicao = [
        {
            'ordem': e.ordem,
            'qtd_barras': e.qtd_barras,
            'comprimento_unitario_m': (
                str(e.comprimento_unitario_m) if e.comprimento_unitario_m is not None else None
            ),
            'total_linha_m': str(total_linha_composicao_m(e)),
            'metros': str(total_linha_composicao_m(e)),
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
        'grupos_informados': len(equivs),
        'barras_informadas': barras_total,
        'metros_total_composicao': str(metros_total),
        'peso_total_kg_estimado': str(peso_total.quantize(Decimal('0.001'))) if peso_total else None,
        'composicao': composicao,
    }


def aplicar_totais_composicao_fisica_item(
    item_conf: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> None:
    """Define estoque calculado em M a partir da composição informada."""
    metros_total = sum(total_linha_composicao_m(e) for e in equivs)
    barras_total = Decimal(total_barras_composicao(equivs))
    ppm = _peso_por_metro_produto(item_conf)
    peso_total = sum(_dec(e.peso_kg or 0) for e in equivs)
    if peso_total <= 0 and ppm and metros_total > 0:
        peso_total = metros_total * ppm

    for equiv in equivs:
        total = total_linha_composicao_m(equiv)
        equiv.metros = total
        if equiv.qtd_barras and equiv.comprimento_unitario_m:
            equiv.barras = None
            equiv.peso_kg = None

    item_conf.unidade_estoque_calculada = 'M'
    item_conf.quantidade_estoque_calculada = metros_total
    item_conf.metros_total = metros_total
    item_conf.barras_total = barras_total
    item_conf.peso_total_kg = peso_total
    item_conf.toneladas_total = (
        (peso_total / Decimal('1000')).quantize(Decimal('0.001')) if peso_total else Decimal('0')
    )
    item_conf.conversao_estoque_auditoria = montar_auditoria_composicao_fisica(item_conf, equivs)
    if equivs:
        ItemNFeEntradaConferenciaEquivalencia.objects.bulk_update(
            equivs,
            ['metros', 'barras', 'peso_kg'],
        )
