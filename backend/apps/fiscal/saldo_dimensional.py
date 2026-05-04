from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from apps.produtos.conversao_medidas import ConversaoErro, converter_quantidade_produto
from apps.produtos.models import Produto

QTY_Q = Decimal('0.001')


def _dec(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _q(v: Decimal) -> Decimal:
    return v.quantize(QTY_Q, rounding=ROUND_HALF_UP)


def _safe_convert(produto: Produto, quantidade: Decimal, unidade_origem: str, unidade_destino: str, alertas: list[str]) -> Decimal | None:
    try:
        out = converter_quantidade_produto(produto, quantidade, unidade_origem, unidade_destino)
        return _q(_dec(out.quantidade_destino))
    except ConversaoErro as exc:
        msg = str(exc).strip()
        if msg:
            alertas.append(msg)
        return None


def _alertas_fatores_faltando(produto: Produto, unidade_saldo: str) -> list[str]:
    if not produto.get_usa_conversao_dimensional_efetivo():
        return []
    msgs: list[str] = []
    peso_metro = produto.get_peso_por_metro_kg_efetivo()
    comprimento = produto.get_comprimento_padrao_barra_m_efetivo()
    if (unidade_saldo in {'KG', 'M', 'BR', 'TON'}) and not peso_metro:
        msgs.append('Informe peso por metro para calcular KG ↔ M.')
    if unidade_saldo in {'M', 'BR'} and not comprimento:
        msgs.append('Informe comprimento padrão da barra para calcular M ↔ BR.')
    if unidade_saldo in {'KG', 'BR'} and (not peso_metro or not comprimento):
        msgs.append('Informe peso por metro e comprimento da barra para calcular KG ↔ BR.')
    return msgs


def calcular_saldo_dimensional(produto: Produto, quantidade_saldo, unidade_saldo: str) -> dict:
    saldo = _q(_dec(quantidade_saldo))
    unidade = (unidade_saldo or '').strip().upper() or (produto.get_unidade_estoque_efetiva() or produto.unidade or 'UN').upper()
    alertas: list[str] = []
    usa_conv = bool(produto.get_usa_conversao_dimensional_efetivo())
    codigo = (produto.codigo_completo or '').strip()

    payload = {
        'produto_id': produto.id,
        'codigo': codigo,
        'descricao': produto.descricao,
        'saldo_principal': _q(saldo),
        'unidade_principal': unidade,
        'peso_kg': None,
        'metros': None,
        'barras': None,
        'toneladas': None,
        'pecas': None,
        'chapas': None,
        'usa_conversao_dimensional': usa_conv,
        'alertas': [],
    }

    # Produto simples: mantém leitura atual sem obrigar conversão.
    if not usa_conv:
        if unidade == 'KG':
            payload['peso_kg'] = _q(saldo)
        elif unidade == 'M':
            payload['metros'] = _q(saldo)
        elif unidade == 'BR':
            payload['barras'] = _q(saldo)
        elif unidade == 'TON':
            payload['toneladas'] = _q(saldo)
        elif unidade == 'PC':
            payload['pecas'] = _q(saldo)
        elif unidade == 'CH':
            payload['chapas'] = _q(saldo)
        return payload

    payload['alertas'] = _alertas_fatores_faltando(produto, unidade)

    payload['peso_kg'] = _safe_convert(produto, saldo, unidade, 'KG', alertas)
    payload['metros'] = _safe_convert(produto, saldo, unidade, 'M', alertas)
    payload['barras'] = _safe_convert(produto, saldo, unidade, 'BR', alertas)
    payload['toneladas'] = _safe_convert(produto, saldo, unidade, 'TON', alertas)
    payload['pecas'] = _safe_convert(produto, saldo, unidade, 'PC', alertas)
    payload['chapas'] = _safe_convert(produto, saldo, unidade, 'CH', alertas)

    payload['alertas'] = list(dict.fromkeys([*payload['alertas'], *alertas]))
    return payload
