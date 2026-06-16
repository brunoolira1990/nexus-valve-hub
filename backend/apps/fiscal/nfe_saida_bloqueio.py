"""NF-e Saída 3.4 — origem comercial travada e dados complementares editáveis."""

from __future__ import annotations

from apps.fiscal.models import NFeSaida

STATUS_NFE_RASCUNHO = 'RASCUNHO'

_STATUS_EMITIDA = frozenset({'EMITIDA', 'EMITIDO', 'AUTORIZADA_INTERNA', 'AUTORIZADA'})
_STATUS_AUTORIZADA_TRAVA = frozenset({'AUTORIZADA_INTERNA', 'AUTORIZADA'})
_STATUS_CANCELADA = frozenset({
    'CANCELADA',
    'CANCELADO',
    'CANCELADA_INTERNA',
    'CANCELADA_HOMOLOGACAO',
    'CANCELADA_PRODUCAO',
})
_STATUS_AUTORIZADA_HOMOLOG = frozenset({'AUTORIZADA_HOMOLOGACAO'})

MSG_ITENS_ORIGEM_COMERCIAL = (
    'Itens herdados do faturamento/pedido não podem ser alterados. '
    'Para corrigir produtos ou quantidades, estorne a NF-e e gere novo faturamento.'
)
MSG_DADOS_COMPLEMENTARES_BLOQUEADOS = (
    'NF-e autorizada ou cancelada não permite alteração de dados complementares.'
)
MSG_DADOS_COMPLEMENTARES_BLOQUEADOS_HOMOLOG = (
    'NF-e autorizada em homologação não permite alteração de dados complementares.'
)

CAMPOS_COMPLEMENTARES_NFE = frozenset(
    {
        'transportadora',
        'transportadora_id',
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
        'ind_final',
        'ind_pres',
        'indicadores_fiscais_confirmados',
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


def nf_autorizada_homologacao(nf: NFeSaida) -> bool:
    if (nf.status_emissao_sefaz or '').strip() == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        return True
    return (nf.status or '').strip().upper() in _STATUS_AUTORIZADA_HOMOLOG


def nf_autorizada_producao(nf: NFeSaida) -> bool:
    if (nf.status_emissao_sefaz or '').strip() == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO:
        return True
    return (nf.status or '').strip().upper() == 'AUTORIZADA_PRODUCAO'


def nf_cancelada_operacional(nf: NFeSaida) -> bool:
    st = _status_normalizado(nf.status)
    if st in _STATUS_CANCELADA:
        return True
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()
    return 'CANCEL' in sefaz


def origem_comercial_travada(nf: NFeSaida) -> bool:
    return bool(nf.faturamento_pedido_venda_id or nf.pedido_venda_id)


def nf_ja_finalizada_operacionalmente(nf: NFeSaida) -> bool:
    """Trava edição estrutural após autorização real — não confunde status legado EMITIDA com SEFAZ."""
    if nf_autorizada_homologacao(nf) or nf_autorizada_producao(nf):
        return True
    st = _status_normalizado(nf.status)
    if st in _STATUS_CANCELADA:
        return True
    if st in _STATUS_AUTORIZADA_TRAVA or st in _STATUS_AUTORIZADA_HOMOLOG:
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
