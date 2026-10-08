"""Sincroniza registro comercial Vendedor a partir de Colaborador (Comercial 2.4)."""

from __future__ import annotations

from apps.cadastros.models import Colaborador


def vendedor_id_colaborador(colaborador: Colaborador | None) -> int | None:
    if colaborador is None:
        return None
    v = colaborador.vendedores.order_by('pk').first()
    return v.pk if v else None


def sincronizar_vendedor_colaborador(colaborador: Colaborador):
    """Mantém Vendedor espelhado quando colaborador tem função de vendedor."""
    from apps.comercial.models import Vendedor

    qs = Vendedor.objects.filter(colaborador=colaborador)
    if not colaborador.eh_vendedor:
        qs.update(ativo=False)
        return None
    v, _created = Vendedor.objects.update_or_create(
        colaborador=colaborador,
        defaults={
            'nome': colaborador.nome,
            'codigo': colaborador.codigo,
            'email': colaborador.email,
            'telefone': colaborador.telefone,
            'ativo': colaborador.ativo,
            'usuario': colaborador.usuario,
        },
    )
    return v
