"""NF-e Saída 3.4 — origem comercial travada e dados complementares editáveis."""

from __future__ import annotations

from apps.fiscal.models import NFeSaida

STATUS_NFE_RASCUNHO = 'RASCUNHO'

_STATUS_EMITIDA = frozenset({'EMITIDA', 'EMITIDO', 'AUTORIZADA_INTERNA', 'AUTORIZADA'})
_STATUS_CANCELADA = frozenset({'CANCELADA', 'CANCELADO', 'CANCELADA_INTERNA'})

MSG_ITENS_ORIGEM_COMERCIAL = (
    'Itens herdados do faturamento/pedido não podem ser alterados. '
    'Para corrigir produtos ou quantidades, estorne a NF-e e gere novo faturamento.'
)
MSG_DADOS_COMPLEMENTARES_BLOQUEADOS = (
    'NF-e autorizada ou cancelada não permite alteração de dados complementares.'
)

CAMPOS_COMPLEMENTARES_NFE = frozenset(
    {
        'transportadora',
        'modalidade_frete',
        'valor_frete',
        'quantidade_volumes',
        'peso_bruto',
        'peso_liquido',
        'especie_volumes',
        'marca_volumes',
        'numeracao_volumes',
        'placa_veiculo',
        'uf_veiculo',
        'observacoes_nfe',
        'informacoes_adicionais',
        'informacoes_fisco',
        'observacoes_internas',
        'pedido_cliente_numero',
        'pedido_cliente_observacao',
    },
)

CAMPOS_COMPLEMENTARES_ITEM_NFE = frozenset(
    {
        'pedido_cliente_numero',
        'pedido_cliente_item',
        'observacao_item',
        'informacao_adicional_item',
    },
)


def _status_normalizado(status: str | None) -> str:
    return (status or '').strip().upper()


def origem_comercial_travada(nf: NFeSaida) -> bool:
    return bool(nf.faturamento_pedido_venda_id or nf.pedido_venda_id)


def nf_ja_finalizada_operacionalmente(nf: NFeSaida) -> bool:
    st = _status_normalizado(nf.status)
    if st in _STATUS_EMITIDA or st in _STATUS_CANCELADA:
        return True
    return bool(nf.efeitos_autorizacao_aplicados_em)


def dados_complementares_editaveis(nf: NFeSaida) -> bool:
    if nf_ja_finalizada_operacionalmente(nf):
        return False
    return _status_normalizado(nf.status) == STATUS_NFE_RASCUNHO


def pode_atualizar_impostos_nfe(nf: NFeSaida, *, itens_count: int | None = None) -> bool:
    """
    Permite atualizar snapshot fiscal em rascunho (independente de origem comercial travada,
    reforma configurada ou regra fiscal encontrada — o preview informa regra/alterações).
    """
    if nf_ja_finalizada_operacionalmente(nf):
        return False
    if _status_normalizado(nf.status) != STATUS_NFE_RASCUNHO:
        return False
    if itens_count is not None:
        return itens_count > 0
    return nf.itens.exists()


def itens_comerciais_editaveis(nf: NFeSaida) -> bool:
    if origem_comercial_travada(nf):
        return False
    if nf_ja_finalizada_operacionalmente(nf):
        return False
    return _status_normalizado(nf.status) == STATUS_NFE_RASCUNHO
