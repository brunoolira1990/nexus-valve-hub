"""Resolve empresa emitente da NF-e de saída."""

from __future__ import annotations

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSaida


def resolver_empresa_emitente_nfe(nf: NFeSaida) -> Empresa:
    if nf.empresa_emitente_id:
        if getattr(nf, 'empresa_emitente', None):
            return nf.empresa_emitente
        return Empresa.objects.get(pk=nf.empresa_emitente_id)
    pedido = getattr(nf, 'pedido_venda', None)
    if pedido and pedido.empresa_emitente_id:
        if getattr(pedido, 'empresa_emitente', None):
            return pedido.empresa_emitente
        from apps.cadastros.models import Empresa

        return Empresa.objects.get(pk=pedido.empresa_emitente_id)
    emp = Empresa.objects.order_by('pk').first()
    if not emp:
        raise ValueError('Nenhuma empresa cadastrada para emissão da NF-e.')
    return emp
