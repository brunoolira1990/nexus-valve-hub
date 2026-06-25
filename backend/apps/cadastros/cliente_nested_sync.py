"""Sincronização de endereços de entrega e contatos nested no cadastro de Cliente."""

from __future__ import annotations

from apps.cadastros.models import ContatoCliente, EnderecoEntregaCliente


def _sync_nested(cliente, *, related_name: str, model_cls, items: list[dict]) -> None:
    manager = getattr(cliente, related_name)
    existing = {obj.pk: obj for obj in manager.all()}
    kept_ids: set[int] = set()

    for raw in items:
        data = dict(raw)
        pk = data.pop('id', None)
        if pk is not None:
            try:
                pk = int(pk)
            except (TypeError, ValueError):
                pk = None

        if pk and pk in existing:
            obj = existing[pk]
            for field, value in data.items():
                setattr(obj, field, value)
            obj.save()
            kept_ids.add(pk)
        else:
            obj = model_cls.objects.create(cliente=cliente, **data)
            kept_ids.add(obj.pk)

    for pk, obj in existing.items():
        if pk not in kept_ids:
            obj.delete()


def sincronizar_enderecos_entrega(cliente, items: list[dict]) -> None:
    _sync_nested(cliente, related_name='enderecos_entrega', model_cls=EnderecoEntregaCliente, items=items)


def sincronizar_contatos_cliente(cliente, items: list[dict]) -> None:
    _sync_nested(cliente, related_name='contatos', model_cls=ContatoCliente, items=items)
