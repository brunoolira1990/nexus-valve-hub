"""Cálculo e normalização da Reforma Tributária (IBS/CBS) no snapshot da NF-e rascunho."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from apps.regras_fiscais.reforma_tributaria_config import (
    REFORMA_PERCENT_KEYS,
    REFORMA_TRIBUTARIA_KEYS,
    normalizar_percentual_reforma,
    normalizar_reforma_tributaria,
    percentual_reforma_para_snapshot,
    reforma_tributaria_preenchida,
)

REFORMA_VALOR_KEYS = frozenset(
    {
        'valor_cbs',
        'valor_ibs_estadual',
        'valor_ibs_municipal',
        'valor_ibs_uf',
        'valor_ibs_mun',
        'base_cbs',
        'base_ibs',
    },
)


def _q2(v: Decimal) -> str:
    return str(v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _q4(v: Decimal) -> str:
    return str(v.quantize(Decimal('0.0001')))


def normalizar_reforma_percentuais_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    """Normaliza chaves percentuais de um bloco reforma (vírgula -> ponto)."""
    if not data:
        return {}
    out = dict(data)
    for key in REFORMA_PERCENT_KEYS:
        if key not in out:
            continue
        raw = out[key]
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        out[key] = percentual_reforma_para_snapshot(raw)
    return out


def calcular_valor_percentual(
    base: Decimal,
    aliquota: Any,
    *,
    reducao: Any = None,
    diferimento: Any = None,
) -> Decimal:
    """Valor = base × alíquota% com redução/diferimento opcionais."""
    ali = normalizar_percentual_reforma(aliquota)
    if ali <= 0 or base <= 0:
        return Decimal('0')
    valor = base * ali / Decimal('100')
    red = normalizar_percentual_reforma(reducao)
    if red > 0:
        valor = valor * (Decimal('100') - red) / Decimal('100')
    dif = normalizar_percentual_reforma(diferimento)
    if dif > 0:
        valor = valor * (Decimal('100') - dif) / Decimal('100')
    return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_base_reforma_item(valor_produto: Decimal) -> Decimal:
    """Legado — preferir calcular_base_ibs_cbs_2026."""
    return max(valor_produto, Decimal('0')).quantize(Decimal('0.01'))


def aplicar_reforma_tributaria_item(
    reforma_raw: Any,
    *,
    valor_produto: Decimal,
    valor_icms: Decimal = Decimal('0'),
    valor_pis: Decimal = Decimal('0'),
    valor_cofins: Decimal = Decimal('0'),
    valor_ipi: Decimal = Decimal('0'),
    valor_iss: Decimal = Decimal('0'),
) -> dict[str, str] | None:
    """
    Monta bloco reforma_tributaria para snapshot com bases e valores calculados.
    """
    from apps.fiscal.reforma_tributaria.base_ibs_cbs import (
        ContextoBaseIbsCbs,
        calcular_base_ibs_cbs_2026,
        diagnosticar_base_reforma_cenarios,
    )

    norm = normalizar_reforma_tributaria(reforma_raw)
    if not norm:
        return None
    norm = normalizar_reforma_percentuais_dict(norm)
    if not _text(norm.get('cst_ibs_cbs')) and not _text(norm.get('classificacao_tributaria')):
        return None

    ctx = ContextoBaseIbsCbs(
        valor_produto=valor_produto,
        valor_icms=valor_icms,
        valor_pis=valor_pis,
        valor_cofins=valor_cofins,
        valor_ipi=valor_ipi,
        valor_iss=valor_iss,
    )
    base_res = calcular_base_ibs_cbs_2026(ctx, norm)
    base = base_res.base_ibs_cbs
    ali_cbs = normalizar_percentual_reforma(norm.get('aliquota_cbs'))
    ali_ibs = normalizar_percentual_reforma(norm.get('aliquota_ibs_estadual'))
    ali_mun = normalizar_percentual_reforma(norm.get('aliquota_ibs_municipal'))

    v_cbs = calcular_valor_percentual(
        base,
        ali_cbs,
        reducao=norm.get('reducao_cbs'),
        diferimento=norm.get('diferimento_cbs'),
    )
    v_ibs = calcular_valor_percentual(
        base,
        ali_ibs,
        reducao=norm.get('reducao_ibs'),
        diferimento=norm.get('diferimento_ibs'),
    )
    v_mun = calcular_valor_percentual(
        base,
        ali_mun,
        reducao=norm.get('reducao_ibs'),
        diferimento=norm.get('diferimento_ibs'),
    )

    out: dict[str, str] = {}
    for key in REFORMA_TRIBUTARIA_KEYS:
        if key in norm and norm[key] not in (None, ''):
            out[key] = str(norm[key]) if not isinstance(norm[key], str) else norm[key]

    out.update(base_res.para_snapshot())
    out['base_cbs'] = _q2(base)
    out['base_ibs'] = _q2(base)
    out['base_ibs_estadual'] = _q2(base)
    out['base_ibs_municipal'] = _q2(base)
    out['valor_cbs'] = _q2(v_cbs)
    out['valor_ibs_estadual'] = _q2(v_ibs)
    out['valor_ibs_municipal'] = _q2(v_mun)
    out['valor_total_ibs_cbs'] = _q2(v_cbs + v_ibs + v_mun)
    cenarios = diagnosticar_base_reforma_cenarios(
        ctx,
        aliquota_cbs=ali_cbs,
        aliquota_ibs_uf=ali_ibs,
        aliquota_ibs_mun=ali_mun,
    )
    if cenarios:
        import json

        out['diagnosticos_base_reforma'] = json.dumps(cenarios, ensure_ascii=False)
    return out


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def tem_aliquota_reforma_configurada(reforma: dict[str, Any] | None) -> bool:
    if not reforma:
        return False
    return any(
        normalizar_percentual_reforma(reforma.get(k)) > 0
        for k in ('aliquota_cbs', 'aliquota_ibs_estadual', 'aliquota_ibs_municipal')
    )


def reforma_valores_calculados(reforma: dict[str, Any] | None) -> bool:
    if not reforma:
        return False
    total = (
        normalizar_percentual_reforma(reforma.get('valor_cbs'))
        + normalizar_percentual_reforma(reforma.get('valor_ibs_estadual'))
        + normalizar_percentual_reforma(reforma.get('valor_ibs_municipal'))
    )
    return total > 0


def status_reforma_snapshot(reforma: dict[str, Any] | None) -> str:
    """
    NAO_CONFIGURADA | PENDENTE | SEM_CALCULO | ATENCAO | CALCULADA
    """
    if not reforma_tributaria_preenchida(reforma):
        return 'NAO_CONFIGURADA'
    norm = reforma or {}
    if not _text(norm.get('cst_ibs_cbs')) or not _text(norm.get('classificacao_tributaria')):
        return 'PENDENTE'
    if not tem_aliquota_reforma_configurada(norm):
        return 'SEM_CALCULO'
    if reforma_valores_calculados(norm):
        return 'CALCULADA'
    if tem_aliquota_reforma_configurada(norm):
        return 'ATENCAO'
    return 'SEM_CALCULO'


def diagnosticar_reforma_calculo(
    reforma: dict[str, Any] | None,
    *,
    valor_produto: Decimal | None = None,
) -> str:
    st = status_reforma_snapshot(reforma)
    if st == 'NAO_CONFIGURADA':
        return 'Reforma não configurada neste item.'
    if st == 'PENDENTE':
        return 'CST ou classificação tributária ausente.'
    if st == 'SEM_CALCULO':
        return 'Reforma configurada sem alíquotas de cálculo. Revise a regra fiscal.'
    if st == 'ATENCAO':
        return (
            'Alíquota da Reforma informada, mas valor calculado ficou zerado. '
            'Verifique parsing/cálculo e base do item.'
        )
    if st == 'CALCULADA' and valor_produto is not None:
        norm = reforma or {}
        v_cbs = normalizar_percentual_reforma(norm.get('valor_cbs'))
        v_ibs = normalizar_percentual_reforma(norm.get('valor_ibs_estadual'))
        partes = []
        if v_cbs > 0:
            partes.append(f'CBS R$ {v_cbs:.2f}'.replace('.', ','))
        if v_ibs > 0:
            partes.append(f'IBS UF R$ {v_ibs:.2f}'.replace('.', ','))
        if partes:
            return f'Reforma configurada e calculada: {" · ".join(partes)}.'
    return ''


def mensagem_reforma_aplicada(reforma: dict[str, Any] | None) -> str:
    if not reforma_valores_calculados(reforma):
        if tem_aliquota_reforma_configurada(reforma):
            return (
                'Reforma possui alíquota configurada, mas o cálculo resultou zero. '
                'Verifique base e parsing.'
            )
        if reforma_tributaria_preenchida(reforma):
            return 'Regra fiscal aplicada, mas Reforma Tributária está sem alíquotas de cálculo.'
        return ''
    norm = reforma or {}
    v_cbs = normalizar_percentual_reforma(norm.get('valor_cbs'))
    v_ibs = normalizar_percentual_reforma(norm.get('valor_ibs_estadual'))
    partes = []
    if v_cbs > 0:
        partes.append(f'CBS R$ {_q2(v_cbs)}')
    if v_ibs > 0:
        partes.append(f'IBS UF R$ {_q2(v_ibs)}')
    if not partes:
        return ''
    return f'Reforma calculada: {" · ".join(partes)}.'


def montar_resumo_reforma_nfe(itens_reforma: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega totais e status geral a partir de linhas de conferência."""
    tot_cbs = tot_ibs = tot_mun = Decimal('0')
    com = calc = alerta = 0
    for row in itens_reforma:
        if not row.get('reforma_configurada'):
            continue
        com += 1
        st = row.get('status_reforma') or status_reforma_snapshot(row.get('reforma_tributaria'))
        if st == 'CALCULADA':
            calc += 1
        elif st == 'ATENCAO':
            alerta += 1
        fr = row.get('reforma_tributaria') or {}
        tot_cbs += normalizar_percentual_reforma(fr.get('valor_cbs'))
        tot_ibs += normalizar_percentual_reforma(fr.get('valor_ibs_estadual'))
        tot_mun += normalizar_percentual_reforma(fr.get('valor_ibs_municipal'))

    status = 'NAO_CONFIGURADA'
    if com:
        if alerta:
            status = 'ATENCAO'
        elif calc == com:
            status = 'OK'
        elif calc:
            status = 'ATENCAO'
        else:
            status = 'PENDENTE' if any(
                status_reforma_snapshot(r.get('reforma_tributaria')) == 'PENDENTE'
                for r in itens_reforma
                if r.get('reforma_configurada')
            ) else 'SEM_CALCULO'

    return {
        'status': status,
        'itens_com_reforma': com,
        'valor_cbs': _q2(tot_cbs),
        'valor_ibs_estadual': _q2(tot_ibs),
        'valor_ibs_municipal': _q2(tot_mun),
        'total_ibs_cbs': _q2(tot_cbs + tot_ibs + tot_mun),
    }
