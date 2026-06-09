"""Obter/criar conferência de NF-e entrada histórica (mesma lógica da tela fiscal)."""

from __future__ import annotations

from decimal import Decimal

from apps.fiscal.models import (
    ItemNFeEntradaHistoricaImportada,
    NFeEntradaConferencia,
    NFeEntradaHistoricaImportada,
)


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _extract_item_nf(prod_json: dict) -> dict:
    return {
        'unidade_nf': (prod_json.get('uCom') or prod_json.get('uTrib') or '').upper(),
        'quantidade_nf': _dec(prod_json.get('qCom') or prod_json.get('qTrib') or 0),
        'valor_unitario_nf': _dec(prod_json.get('vUnCom') or prod_json.get('vUnTrib') or 0),
        'valor_total_nf': _dec(prod_json.get('vProd') or 0),
    }


def get_or_build_conferencia_for_nf_historica(nf: NFeEntradaHistoricaImportada) -> NFeEntradaConferencia:
    conferencia, created = NFeEntradaConferencia.objects.get_or_create(nf_entrada_historica=nf)
    if created and nf.fornecedor_emitente_id:
        conferencia.pedido_compra = (
            nf.fornecedor_emitente.pedidos_compra.order_by('-data', '-id').first()
        )
        conferencia.save(update_fields=['pedido_compra'])
    for item_nf in nf.itens.all():
        item_conf, was_created = conferencia.itens.get_or_create(item_nfe_historico=item_nf)
        if was_created:
            fields = _extract_item_nf(item_nf.prod_json or {})
            for key, value in fields.items():
                setattr(item_conf, key, value)
            item_conf.save(
                update_fields=['unidade_nf', 'quantidade_nf', 'valor_unitario_nf', 'valor_total_nf'],
            )
    return conferencia


def map_itens_conferencia_por_n_item(conferencia: NFeEntradaConferencia) -> dict[int, object]:
    return {
        ic.item_nfe_historico.n_item: ic
        for ic in conferencia.itens.select_related(
            'item_nfe_historico',
            'produto',
            'item_pedido_compra__pedido',
            'item_pedido_compra__produto',
        ).all()
    }
