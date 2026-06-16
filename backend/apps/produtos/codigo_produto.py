"""Montagem de código e descrição para produtos com regra por família."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.produtos.models import FamiliaProduto, Polegada, Produto, RoscaConexao, ScheduleEspessura


def _normalize_spaces(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip())


def expandir_siglas_valvula_descricao_base(text: str) -> str:
    """Apenas VEM/VEB/VET no início da descrição base (planilha) → texto comercial completo."""
    raw = (text or '').strip()
    if not raw:
        return ''
    upper = raw.upper()
    # Ordem: prefixos mais longos primeiro (VET/VEB/VEM são distintos).
    prefixos = (
        ('VET ', 'VALVULA ESFERA TRIPARTIDA '),
        ('VEB ', 'VALVULA ESFERA BIPARTIDA '),
        ('VEM ', 'VALVULA ESFERA MONOBLOCO '),
    )
    for pref, repl in prefixos:
        if upper.startswith(pref):
            rest = raw[len(pref) :].lstrip()
            return _normalize_spaces(repl + rest)
    for token, repl in (
        ('VET', 'VALVULA ESFERA TRIPARTIDA'),
        ('VEB', 'VALVULA ESFERA BIPARTIDA'),
        ('VEM', 'VALVULA ESFERA MONOBLOCO'),
    ):
        if upper == token:
            return repl
    return raw


def _base_descricao_comercial(familia: 'FamiliaProduto') -> str:
    from apps.produtos.descricao_norm import normalizar_descricao_produto

    raw = expandir_siglas_valvula_descricao_base(familia.descricao_base or '')
    return normalizar_descricao_produto(_normalize_spaces(raw))


def _token_in_text(text: str, token: str) -> bool:
    if not text or not token:
        return False
    escaped = re.escape(token.strip())
    return bool(re.search(rf'(^|[^A-Z0-9]){escaped}([^A-Z0-9]|$)', text.upper()))


def _descricao_rosca_comercial(rosca: RoscaConexao | None) -> str:
    if not rosca:
        return ''
    codigo = (rosca.codigo or '').strip().upper()
    if codigo == 'SW':
        return 'SW'
    desc_raw = _normalize_spaces((rosca.descricao or ''))
    desc_upper = desc_raw.upper()
    if 'PADRAO DA FAMILIA' in desc_upper or 'PADRÃO DA FAMÍLIA' in desc_upper:
        # Rosca padrão nunca deve vazar metadado interno para descrição comercial.
        return 'BSP'
    cleaned = desc_raw
    for frag in (
        '/ padrão da família',
        '/ padrao da familia',
        'padrão da família',
        'padrao da familia',
        'default',
        'sem rosca',
    ):
        cleaned = re.sub(re.escape(frag), '', cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_spaces(cleaned.strip(' /-'))
    if not cleaned and not codigo:
        return 'BSP'
    return cleaned or codigo


def _descricao_schedule_comercial(schedule: ScheduleEspessura | None) -> str:
    if not schedule:
        return ''
    desc = _normalize_spaces((schedule.descricao or ''))
    cod = _normalize_spaces((schedule.codigo or schedule.codigo_schedule or ''))
    return desc or cod


def _codigo_rosca(rosca: RoscaConexao | None) -> str:
    if not rosca:
        return ''
    codigo = (rosca.codigo or '').strip()
    if codigo.upper() == 'SW':
        return 'S'
    return codigo


def _codigo_schedule(sch: ScheduleEspessura | None) -> str:
    if not sch:
        return ''
    return (sch.codigo or sch.codigo_schedule or '').strip()


def _codigo_pol(p: Polegada | None, *, width: int = 2) -> str:
    if not p:
        return ''
    c = (getattr(p, 'codigo_oficial', '') or p.codigo or '').strip()
    if not c.isdigit():
        return c
    w = width if width in (2, 3) else 2
    if len(c) <= w:
        return c.zfill(w)
    return c


def _segmento_mm_codigo(val: Decimal | None, *, width: int = 2) -> str:
    if val is None:
        return ''
    n = int(val.quantize(Decimal('1')))
    s = str(abs(n))
    if width > 1 and len(s) <= width:
        return s.zfill(width)
    return s


def _prefixo_od(figura: str) -> str:
    f = (figura or '').strip()
    if not f:
        return ''
    return f if f.upper().endswith('OD') else f'{f}OD'


def _format_mm_descricao(val: Decimal | None) -> str:
    if val is None:
        return ''
    normalized = val.normalize()
    if normalized == normalized.to_integral():
        return f'{int(normalized)}MM'
    txt = format(normalized, 'f').rstrip('0').rstrip('.')
    return f'{txt.replace(".", ",")}MM'


def _format_dim_code_piece(val: Decimal | None) -> str:
    if val is None:
        return ''
    normalized = val.normalize()
    if normalized == normalized.to_integral():
        return str(int(normalized))
    txt = format(normalized, 'f').rstrip('0').rstrip('.')
    return txt.replace('.', 'P')


def _dimensao_decimal(dimensoes: dict | None, key: str) -> Decimal | None:
    if not isinstance(dimensoes, dict):
        return None
    raw = dimensoes.get(key)
    if raw in (None, ''):
        return None
    if isinstance(raw, str):
        raw = raw.strip().replace(',', '.')
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def montar_codigo_interno(
    familia: FamiliaProduto,
    *,
    rosca: RoscaConexao | None,
    schedule: ScheduleEspessura | None,
    polegada_principal: Polegada | None,
    polegada_secundaria: Polegada | None,
    od_mm: Decimal | None = None,
    espessura_mm: Decimal | None = None,
    dimensoes: dict | None = None,
) -> str:
    from apps.produtos.models import FamiliaProduto

    rule = familia.tipo_regra_codigo
    if rule == FamiliaProduto.TipoRegraCodigo.MANUAL_FABRICANTE:
        return ''
    td = familia.tipo_dimensional or FamiliaProduto.TipoDimensional.SIMPLES

    fig = (familia.codigo_figura or '').strip()
    rs = _codigo_rosca(rosca)
    sch = _codigo_schedule(schedule)
    id1 = _codigo_pol(polegada_principal, width=2)
    id2 = _codigo_pol(polegada_secundaria, width=2)
    sep = (familia.separador_base_medidas or '.')[:1] or '.'

    t = FamiliaProduto.TipoRegraCodigo
    td_new = FamiliaProduto.TipoDimensional

    if td == td_new.CHAPA_MM:
        esp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'espessura_mm'))
        lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
        comp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'comprimento_mm'))
        return f'{fig}{sep}{esp}X{lar}X{comp}' if esp and lar and comp else ''
    if td == td_new.CHAPA_FURO_MM:
        furo = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'furo_mm'))
        esp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'espessura_mm'))
        lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
        comp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'comprimento_mm'))
        return f'{fig}{sep}F{furo}X{esp}X{lar}X{comp}' if furo and esp and lar and comp else ''
    if td == td_new.BARRA_CHATA_MM:
        lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
        esp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'espessura_mm'))
        comp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'comprimento_mm'))
        if not lar or not esp:
            return ''
        return f'{fig}{sep}{lar}X{esp}X{comp}' if comp else f'{fig}{sep}{lar}X{esp}'
    if td == td_new.METALON_MM:
        lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
        alt = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'altura_mm'))
        esp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'espessura_mm'))
        return f'{fig}{sep}{lar}X{alt}X{esp}' if alt and lar and esp else ''
    if td == td_new.PERFIL_RETANGULAR_MM:
        alt = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'altura_mm'))
        lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
        esp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'espessura_mm'))
        return f'{fig}{sep}{alt}X{lar}X{esp}' if alt and lar and esp else ''
    if td == td_new.CANTONEIRA_MM:
        aba = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'aba_mm'))
        esp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'espessura_mm'))
        comp = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'comprimento_mm'))
        if not aba or not esp:
            return ''
        return f'{fig}{sep}{aba}X{esp}X{comp}' if comp else f'{fig}{sep}{aba}X{esp}'
    if td == td_new.CANTONEIRA_POLEGADA:
        aba = _codigo_pol(polegada_principal, width=2)
        esp = _codigo_pol(polegada_secundaria, width=2)
        if not aba or not esp:
            return ''
        return f'{fig}{sep}P{aba}X{esp}'
    if td == td_new.DIMENSIONAL_LIVRE_CONTROLADO:
        dim_code = _normalize_spaces(str((dimensoes or {}).get('dimensao_codigo') or '')).upper()
        if not dim_code:
            return ''
        return f'{fig}{sep}{dim_code}'

    if rule == t.BASE_DN_MM:
        mm = _segmento_mm_codigo(od_mm, width=3)
        return f'{fig}{sep}{mm}' if fig and mm else ''

    if rule == t.BASE_DN_MM_REDUCAO:
        ma = _segmento_mm_codigo(od_mm, width=3)
        me = _segmento_mm_codigo(espessura_mm, width=3)
        if not fig or not ma or not me:
            return ''
        return f'{fig}{sep}{ma}{me}'

    if rule == t.BASE_BITOLA_POLEGADA:
        return f'{fig}{sep}{id1}' if id1 else ''

    if rule == t.BASE_OD_MM:
        mm = _segmento_mm_codigo(od_mm, width=3)
        return f'{fig}{sep}{mm}' if fig and mm else ''

    if rule == t.BASE_OD_MM_REDUCAO:
        ma = _segmento_mm_codigo(od_mm, width=3)
        me = _segmento_mm_codigo(espessura_mm, width=3)
        if not fig or not ma or not me:
            return ''
        return f'{fig}{sep}{ma}{me}'

    if rule == t.BASE_OD_MM_X_ROSCA:
        mm = _segmento_mm_codigo(od_mm, width=3)
        tail = ''
        if rosca:
            tail += _codigo_rosca(rosca)
        if polegada_principal:
            tail += _codigo_pol(polegada_principal, width=2)
        if not fig or not mm or not tail:
            return ''
        return f'{fig}{sep}{mm}{tail}'

    if rule == t.BASE_ESPIGAO_FLANGE_NPS:
        cod_e = _codigo_pol(polegada_principal, width=2)
        cod_f = _codigo_pol(polegada_secundaria, width=2)
        if not cod_e or not cod_f:
            return ''
        return f'{fig}{sep}E{cod_e}F{cod_f}'

    if rule == t.BASE_POLEGADA:
        return f'{fig}{sep}{id1}' if id1 else ''

    if rule == t.BASE_ROSCA_POLEGADA:
        return f'{fig}{rs}{sep}{id1}' if id1 else ''

    if rule == t.BASE_DUAS_POLEGADAS:
        if not id1 or not id2:
            return ''
        return f'{fig}{sep}{id1}{id2}'

    if rule == t.BASE_ROSCA_DUAS_POLEGADAS:
        if not id1 or not id2:
            return ''
        return f'{fig}{rs}{sep}{id1}{id2}'

    if rule == t.BASE_SCHEDULE_POLEGADA:
        if not sch or not id1:
            return ''
        return f'{fig}{sch}{sep}{id1}'

    if rule == t.BASE_SCHEDULE_DUAS_POLEGADAS:
        if not sch or not id1 or not id2:
            return ''
        return f'{fig}{sch}{sep}{id1}{id2}'

    if rule == t.BASE_ROSCA_SCHEDULE_POLEGADA:
        if rosca is None or schedule is None or not sch or not id1:
            return ''
        return f'{fig}{rs}{sch}{sep}{id1}'

    if rule == t.BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS:
        if rosca is None or schedule is None or not sch or not id1 or not id2:
            return ''
        return f'{fig}{rs}{sch}{sep}{id1}{id2}'

    if rule == t.UNDERSCORE_POLEGADA:
        id_u = _codigo_pol(polegada_principal, width=3)
        if not id_u:
            return ''
        return f'{fig}_{id_u}'

    if rule == t.BASE_OD_MM_ESPESSURA:
        od_s = _segmento_mm_codigo(od_mm, width=2)
        esp_s = _segmento_mm_codigo(espessura_mm, width=2)
        if not od_s or not esp_s:
            return ''
        return f'{_prefixo_od(fig)}{sep}{od_s}{esp_s}'

    return ''


def montar_descricao_sugerida(
    familia: FamiliaProduto,
    *,
    rosca: RoscaConexao | None,
    schedule: ScheduleEspessura | None,
    polegada_principal: Polegada | None,
    polegada_secundaria: Polegada | None,
    od_mm: Decimal | None = None,
    espessura_mm: Decimal | None = None,
    comprimento_mm: Decimal | None = None,
    dimensoes: dict | None = None,
) -> str:
    from apps.produtos.descricao_norm import normalizar_descricao_produto
    from apps.produtos.dimensional_regra import familia_espigao_x_flange_nps, requisitos_efetivos_produto
    from apps.produtos.models import FamiliaProduto

    def _fin(texto: str) -> str:
        return normalizar_descricao_produto(_normalize_spaces(texto))

    req = requisitos_efetivos_produto(familia)
    td = familia.tipo_dimensional or FamiliaProduto.TipoDimensional.SIMPLES
    Td = FamiliaProduto.TipoDimensional
    schedule_eff = schedule if req['incluir_schedule_na_descricao'] else None

    if td == Td.OD_POLEGADA_X_ROSCA:
        partes_od: list[str] = []
        base = _base_descricao_comercial(familia)
        if base:
            partes_od.append(base)
        if polegada_principal and (polegada_principal.descricao or '').strip():
            partes_od.append(_normalize_spaces(polegada_principal.descricao))
        rosca_text = _descricao_rosca_comercial(rosca)
        if rosca_text:
            partes_od.append(f'X ROSCA {rosca_text}')
        if polegada_secundaria and (polegada_secundaria.descricao or '').strip():
            partes_od.append(_normalize_spaces(polegada_secundaria.descricao))
        return _fin(' '.join(partes_od))

    if familia_espigao_x_flange_nps(familia):
        base = _base_descricao_comercial(familia)
        d1 = _normalize_spaces((polegada_principal.descricao or '').strip()) if polegada_principal else ''
        d2 = _normalize_spaces((polegada_secundaria.descricao or '').strip()) if polegada_secundaria else ''
        rx = re.compile(r'\s+X\s+FLANGE\s+', re.IGNORECASE)
        m = rx.search(base)
        if m and (d1 or d2):
            left = base[: m.start()].rstrip()
            right = base[m.end() :].lstrip()
            left_with = _normalize_spaces(f'{left} {d1}'.strip())
            tail = _normalize_spaces(f'{right} {d2}'.strip())
            return _fin(f'{left_with} X FLANGE {tail}')
        chunks_ef: list[str] = []
        if base:
            chunks_ef.append(base)
        if d1:
            chunks_ef.append(d1)
        if d2:
            chunks_ef.append(d2)
        return _fin(' '.join(chunks_ef))

    if td in (Td.CHAPA_MM, Td.CHAPA_FURO_MM, Td.BARRA_CHATA_MM, Td.METALON_MM, Td.PERFIL_RETANGULAR_MM, Td.CANTONEIRA_MM):
        base = _base_descricao_comercial(familia)
        chunks: list[str] = []
        if td == Td.CHAPA_MM:
            for k in ('espessura_mm', 'largura_mm', 'comprimento_mm'):
                x = _format_mm_descricao(_dimensao_decimal(dimensoes, k))
                if x:
                    chunks.append(x)
        elif td == Td.CHAPA_FURO_MM:
            furo = _format_mm_descricao(_dimensao_decimal(dimensoes, 'furo_mm'))
            if furo:
                chunks.append(furo)
            for k in ('espessura_mm', 'largura_mm', 'comprimento_mm'):
                x = _format_mm_descricao(_dimensao_decimal(dimensoes, k))
                if x:
                    chunks.append(x)
        elif td == Td.BARRA_CHATA_MM:
            for k in ('largura_mm', 'espessura_mm', 'comprimento_mm'):
                x = _format_mm_descricao(_dimensao_decimal(dimensoes, k))
                if x:
                    chunks.append(x)
        elif td == Td.METALON_MM:
            lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
            alt = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'altura_mm'))
            esp = _format_mm_descricao(_dimensao_decimal(dimensoes, 'espessura_mm'))
            if alt and lar and esp:
                chunks.append(f'{lar} X {alt} X {esp}')
        elif td == Td.PERFIL_RETANGULAR_MM:
            alt = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'altura_mm'))
            lar = _format_dim_code_piece(_dimensao_decimal(dimensoes, 'largura_mm'))
            esp = _format_mm_descricao(_dimensao_decimal(dimensoes, 'espessura_mm'))
            if alt and lar and esp:
                chunks.append(f'{alt} X {lar} X {esp}')
        elif td == Td.CANTONEIRA_MM:
            for k in ('aba_mm', 'espessura_mm', 'comprimento_mm'):
                x = _format_mm_descricao(_dimensao_decimal(dimensoes, k))
                if x:
                    chunks.append(x)
        return _fin(' '.join([base, ' X '.join(chunks)]))

    if td == Td.CANTONEIRA_POLEGADA:
        partes_cp: list[str] = []
        base = _base_descricao_comercial(familia)
        if base:
            partes_cp.append(base)
        if polegada_principal and polegada_secundaria:
            partes_cp.append(f'{_normalize_spaces(polegada_principal.descricao)} X {_normalize_spaces(polegada_secundaria.descricao)}')
        return _fin(' '.join(partes_cp))
    if td == Td.DIMENSIONAL_LIVRE_CONTROLADO:
        base = _base_descricao_comercial(familia)
        dim_desc = normalizar_descricao_produto(str((dimensoes or {}).get('dimensao_descricao') or ''))
        return _fin(' '.join([base, dim_desc]))

    Tr = FamiliaProduto.TipoRegraCodigo
    tr = getattr(familia, 'tipo_regra_codigo', '') or ''

    if td == Td.DN_MM:
        base = _base_descricao_comercial(familia)
        mm = _format_mm_descricao(od_mm) if od_mm is not None else ''
        return _fin(' '.join([x for x in (base, mm) if x]))

    if td == Td.DN_MM_REDUCAO:
        base = _base_descricao_comercial(familia)
        d1 = _format_mm_descricao(od_mm) if od_mm is not None else ''
        d2 = _format_mm_descricao(espessura_mm) if espessura_mm is not None else ''
        if d1 and d2:
            return _fin(f'{base} {d1} X {d2}'.strip())
        return _fin(' '.join([x for x in (base, d1, d2) if x]))

    if td == Td.BITOLA_POLEGADA:
        base = _base_descricao_comercial(familia)
        pol = _normalize_spaces((polegada_principal.descricao or '').strip()) if polegada_principal else ''
        return _fin(' '.join([x for x in (base, pol) if x]))

    if td == Td.OD_MM_REDUCAO:
        base = _base_descricao_comercial(familia)
        d1 = _format_mm_descricao(od_mm) if od_mm is not None else ''
        d2 = _format_mm_descricao(espessura_mm) if espessura_mm is not None else ''
        if d1 and d2:
            return _fin(f'{base} {d1} X {d2}'.strip())
        return _fin(' '.join([x for x in (base, d1, d2) if x]))

    if td == Td.OD_MM_X_ROSCA:
        base = _base_descricao_comercial(familia)
        mm = _format_mm_descricao(od_mm) if od_mm is not None else ''
        pol_txt = _normalize_spaces((polegada_principal.descricao or '').strip()) if polegada_principal else ''
        rosca_txt = _descricao_rosca_comercial(rosca) if rosca else ''
        tail = pol_txt or rosca_txt
        if base and mm and tail:
            return _fin(f'{base} {mm} X {tail}')
        return _fin(' '.join([x for x in (base, mm, tail) if x]))

    if td in (Td.OD_MM, Td.OD_MM_X_ESPESSURA, Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO):
        partes_mm: list[str] = []
        base = _base_descricao_comercial(familia)
        if base:
            partes_mm.append(base)
        dim_chunks: list[str] = []
        if od_mm is not None:
            dim_chunks.append(_format_mm_descricao(od_mm))
        if espessura_mm is not None:
            dim_chunks.append(_format_mm_descricao(espessura_mm))
        if comprimento_mm is not None:
            dim_chunks.append(_format_mm_descricao(comprimento_mm))
        if dim_chunks:
            prefix = '' if (td == Td.OD_MM and tr == Tr.BASE_OD_MM) else 'OD '
            partes_mm.append(prefix + ' X '.join(dim_chunks))
        return _fin(' '.join(partes_mm))

    partes: list[str] = []
    base = _base_descricao_comercial(familia)
    base_upper = base.upper()
    if base:
        partes.append(base)
    rosca_text = _descricao_rosca_comercial(rosca)
    if rosca_text and not _token_in_text(base_upper, rosca_text):
        partes.append(rosca_text)
    schedule_text = _descricao_schedule_comercial(schedule_eff)
    if schedule_text and not _token_in_text(base_upper, schedule_text):
        partes.append(schedule_text)
    if td == Td.REDUCAO_NPS and polegada_principal and polegada_secundaria:
        p1 = _normalize_spaces(polegada_principal.descricao)
        p2 = _normalize_spaces(polegada_secundaria.descricao)
        if p1 and p2:
            partes.append(f'{p1} X {p2}')
        elif p1:
            partes.append(p1)
        elif p2:
            partes.append(p2)
    else:
        if polegada_principal and (polegada_principal.descricao or '').strip():
            partes.append(_normalize_spaces(polegada_principal.descricao))
        if polegada_secundaria and (polegada_secundaria.descricao or '').strip():
            partes.append(f'x {_normalize_spaces(polegada_secundaria.descricao)}')
    return _fin(' '.join(partes))


def codigo_interno_valido(codigo: str) -> bool:
    if not codigo or not codigo.strip():
        return False
    if '...' in codigo or '..' in codigo:
        return False
    return True


def produto_aplicar_codigo_completo(produto: Produto) -> None:
    from apps.produtos.models import Produto

    if produto.modo_codigo == Produto.ModoCodigo.MANUAL:
        produto.codigo_completo = (produto.codigo_completo or '').strip()
        return

    if produto.modo_codigo == Produto.ModoCodigo.LEGADO or produto.familia_id is None:
        produto.codigo_completo = produto.gerar_codigo_legado()
        return

    if not produto.familia_id:
        produto.codigo_completo = produto.gerar_codigo_legado()
        return

    familia = produto.familia
    codigo = montar_codigo_interno(
        familia,
        rosca=produto.rosca_conexao,
        schedule=produto.schedule_ref,
        polegada_principal=produto.polegada_principal_ref,
        polegada_secundaria=produto.polegada_secundaria_ref,
        od_mm=produto.od_mm,
        espessura_mm=produto.espessura_mm,
        dimensoes={
            **(produto.dimensoes_json or {}),
            'espessura_mm': produto.dim_espessura_mm,
            'largura_mm': produto.dim_largura_mm,
            'comprimento_mm': produto.dim_comprimento_mm,
            'altura_mm': produto.dim_altura_mm,
            'furo_mm': produto.dim_furo_mm,
            'aba_mm': produto.dim_aba_mm,
            'dimensao_codigo': produto.dimensao_codigo,
            'dimensao_descricao': produto.dimensao_descricao,
        },
    )
    produto.codigo_completo = codigo
