"""Composição física por barra na conferência NF-e entrada (Fase 1)."""

from __future__ import annotations

from decimal import Decimal

from apps.fiscal.models import ItemNFeEntradaConferencia, ItemNFeEntradaConferenciaEquivalencia

TOLERANCIA_COMPOSICAO = Decimal('0.001')

ORIGEM_COMPOSICAO_BARRAS = 'COMPOSICAO_BARRAS'
ORIGEM_COMPOSICAO_PECAS_KG = 'COMPOSICAO_PECAS_KG'
REGRA_KG_PARA_M_PESO_POR_METRO = 'KG_PARA_M_PESO_POR_METRO'

TIPO_BARRA_M = 'BARRA_M'
TIPO_PECA_KG = 'PECA_KG'


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    return Decimal(str(v))


def item_controla_composicao_fisica(item: ItemNFeEntradaConferencia) -> bool:
    if not item.produto_id:
        return False
    return bool(item.produto.get_controla_composicao_fisica_efetivo())


def item_tipo_composicao_fisica(item: ItemNFeEntradaConferencia) -> str:
    """Retorna BARRA_M ou PECA_KG conforme cadastro efetivo do produto."""
    if not item.produto_id:
        return TIPO_BARRA_M
    return item.produto.get_tipo_composicao_fisica_efetivo()


def item_e_peca_kg(item: ItemNFeEntradaConferencia) -> bool:
    return item_tipo_composicao_fisica(item) == TIPO_PECA_KG


MSG_EQUIV_LEGADO_REMOVIDA = (
    'Equivalência antiga (BR/kg) removida: informe a composição por grupo de barras (qtd × comprimento em M).'
)


def equivalencias_sao_legado_para_composicao(
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
    tipo: str = TIPO_BARRA_M,
) -> bool:
    """True quando sub-linhas usam formato antigo incompatível com o tipo de composição atual."""
    if not equivs:
        return False
    if tipo == TIPO_PECA_KG:
        # Peça/chapa usa peso_real_kg (peso_kg) por linha; metros/barras são legado incompatível.
        for equiv in equivs:
            if _dec(equiv.peso_kg) > 0:
                continue
            if _dec(equiv.metros) > 0 or _dec(equiv.barras) > 0 or _dec(equiv.comprimento_unitario_m) > 0:
                return True
            if not _dec(equiv.peso_kg):
                return True
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
    if not equivalencias_sao_legado_para_composicao(equivs, item_tipo_composicao_fisica(item)):
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


def quantidade_alvo_composicao_kg(
    item: ItemNFeEntradaConferencia,
) -> tuple[Decimal | None, str | None, dict]:
    """Alvo em KG para composição PECA_KG. Suporta NF em KG ou TON."""
    u = (item.unidade_nf or '').strip().upper()
    qty = _dec(item.quantidade_nf)
    meta: dict = {
        'unidade_nf_original': u,
        'quantidade_nf_original': str(qty),
        'regra_conversao': None,
        'fator_conversao_utilizado': None,
        'kg_convertidos_nf': None,
    }
    if u == 'KG':
        meta['kg_convertidos_nf'] = str(qty)
        return qty, None, meta
    if u == 'TON':
        kg = (qty * Decimal('1000')).quantize(Decimal('0.001'))
        meta['regra_conversao'] = 'TON_PARA_KG'
        meta['fator_conversao_utilizado'] = '1000'
        meta['kg_convertidos_nf'] = str(kg)
        return kg, None, meta
    return (
        None,
        f'Composição por peça/chapa (KG) não suporta NF em {u or "unidade indefinida"}.',
        meta,
    )


def _peso_real_row(row: dict | ItemNFeEntradaConferenciaEquivalencia) -> Decimal:
    """Peso real da peça/chapa (KG). Usa peso_kg como campo principal para PECA_KG."""
    if isinstance(row, dict):
        val = row.get('peso_real_kg')
        if val in (None, ''):
            val = row.get('peso_kg')
        return _dec(val)
    return _dec(row.peso_kg)


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


def expandir_pecas_fisicas_composicao(
    equiv: ItemNFeEntradaConferenciaEquivalencia,
) -> list[Decimal]:
    """Cada linha PECA_KG representa exatamente 1 peça física com seu peso real (KG)."""
    peso = _peso_real_row(equiv)
    if peso <= 0:
        return []
    return [peso.quantize(Decimal('0.001'))]


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


def normalizar_linha_peca_kg_payload(row: dict) -> dict:
    """Peça/chapa: mantém apenas peso_real_kg (gravado em peso_kg); zera campos de barra."""
    out = dict(row)
    peso = _peso_real_row(row)
    out['peso_kg'] = str(peso.quantize(Decimal('0.001'))) if peso > 0 else None
    out['metros'] = None
    out['barras'] = None
    out['qtd_barras'] = None
    out['comprimento_unitario_m'] = None
    return out


def validar_composicao_pecas_kg_equivalencias(
    item: ItemNFeEntradaConferencia,
    equivalencias_payload: list[dict] | None = None,
) -> list[str]:
    """Valida Σ(peso_real_kg das peças) contra a quantidade da NF em KG."""
    rows = _equivalencias_rows(item, equivalencias_payload)
    if not rows:
        return []

    erros: list[str] = []
    alvo, erro_alvo, _meta = quantidade_alvo_composicao_kg(item)
    if erro_alvo:
        return [erro_alvo]

    soma_kg = sum(_peso_real_row(row) for row in rows)
    if alvo is not None and abs(soma_kg - alvo) > TOLERANCIA_COMPOSICAO:
        erros.append(
            f'A soma dos pesos das peças ({soma_kg:.3f} KG) deve ser igual à '
            f'quantidade da NF em KG ({alvo:.3f} KG).',
        )

    for idx, row in enumerate(rows, start=1):
        ordem = int(row.get('ordem') or idx) if isinstance(row, dict) else row.ordem
        peso = _peso_real_row(row)
        if peso <= 0:
            erros.append(f'Peça {ordem}: informe o peso real da peça em KG (maior que zero).')
    return erros


def validar_composicao_fisica_equivalencias(
    item: ItemNFeEntradaConferencia,
    equivalencias_payload: list[dict] | None = None,
) -> list[str]:
    """Valida a composição contra a NF, escolhendo a regra por tipo (barra em M ou peça em KG)."""
    if item_e_peca_kg(item):
        return validar_composicao_pecas_kg_equivalencias(item, equivalencias_payload)
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


def montar_auditoria_composicao_pecas_kg(
    item: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> dict:
    _alvo, _erro, meta = quantidade_alvo_composicao_kg(item)
    peso_total = sum(_peso_real_row(e) for e in equivs)
    composicao = [
        {
            'ordem': e.ordem,
            'peso_real_kg': str(_peso_real_row(e).quantize(Decimal('0.001'))),
        }
        for e in equivs
    ]
    return {
        **meta,
        'unidade_estoque_calculada': 'KG',
        'quantidade_estoque_calculada': str(peso_total.quantize(Decimal('0.001'))),
        'origem_conversao': ORIGEM_COMPOSICAO_PECAS_KG,
        'pecas_informadas': len(equivs),
        'peso_total_kg_composicao': str(peso_total.quantize(Decimal('0.001'))),
        'composicao': composicao,
    }


def aplicar_totais_composicao_pecas_kg_item(
    item_conf: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> None:
    """Define estoque calculado em KG a partir das peças informadas (1 linha = 1 peça)."""
    peso_total = sum(_peso_real_row(e) for e in equivs)
    for equiv in equivs:
        equiv.metros = None
        equiv.barras = None
        equiv.qtd_barras = None
        equiv.comprimento_unitario_m = None

    item_conf.unidade_estoque_calculada = 'KG'
    item_conf.quantidade_estoque_calculada = peso_total
    item_conf.metros_total = Decimal('0')
    item_conf.barras_total = Decimal(len(equivs))
    item_conf.peso_total_kg = peso_total
    item_conf.toneladas_total = (
        (peso_total / Decimal('1000')).quantize(Decimal('0.001')) if peso_total else Decimal('0')
    )
    item_conf.conversao_estoque_auditoria = montar_auditoria_composicao_pecas_kg(item_conf, equivs)
    if equivs:
        ItemNFeEntradaConferenciaEquivalencia.objects.bulk_update(
            equivs,
            ['metros', 'barras', 'qtd_barras', 'comprimento_unitario_m'],
        )


def montar_auditoria_composicao_fisica(
    item: ItemNFeEntradaConferencia,
    equivs: list[ItemNFeEntradaConferenciaEquivalencia],
) -> dict:
    if item_e_peca_kg(item):
        return montar_auditoria_composicao_pecas_kg(item, equivs)
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
    """Define estoque calculado a partir da composição informada (M para barra, KG para peça)."""
    if item_e_peca_kg(item_conf):
        aplicar_totais_composicao_pecas_kg_item(item_conf, equivs)
        return
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
