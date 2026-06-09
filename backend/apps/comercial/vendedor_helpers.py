"""Comercial 2.3.2 — vendedor cadastrado e compatibilidade com texto legado."""

from __future__ import annotations

from apps.comercial.models import PedidoVenda, Proposta, Vendedor
from apps.text_normalize import to_operational_upper


def nome_vendedor_exibicao(obj: Proposta | PedidoVenda) -> str:
    if getattr(obj, 'vendedor_ref_id', None):
        ref = obj.vendedor_ref
        if ref is not None:
            return ref.nome or ''
    return (obj.vendedor or '').strip()


def sincronizar_texto_vendedor(attrs: dict) -> None:
    """Espelha nome do cadastro no campo texto operacional (relatórios/legado)."""
    if 'vendedor_ref' not in attrs:
        return
    ref = attrs.get('vendedor_ref')
    if ref is not None:
        attrs['vendedor'] = to_operational_upper(ref.nome or '') or ''
    elif ref is None:
        attrs.setdefault('vendedor', '')


def aplicar_vendedor_padrao_usuario(attrs: dict, *, request=None, instance=None) -> None:
    if instance is not None or attrs.get('vendedor_ref'):
        return
    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return
    from apps.cadastros.colaborador_sync import sincronizar_vendedor_colaborador
    from apps.cadastros.models import Colaborador

    colab = (
        Colaborador.objects.filter(usuario=request.user, ativo=True, eh_vendedor=True)
        .order_by('pk')
        .first()
    )
    if colab:
        v = sincronizar_vendedor_colaborador(colab) or Vendedor.objects.filter(colaborador=colab).first()
        if v:
            attrs['vendedor_ref'] = v
            attrs['vendedor'] = to_operational_upper(v.nome or '') or ''
            return
    v = Vendedor.objects.filter(usuario=request.user, ativo=True).order_by('pk').first()
    if v:
        attrs['vendedor_ref'] = v
        attrs['vendedor'] = to_operational_upper(v.nome or '') or ''
