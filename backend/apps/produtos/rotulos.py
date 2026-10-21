"""Rótulos de exibição derivados dos próprios models — nenhuma etiqueta inventada aqui."""

from __future__ import annotations

from django.apps import apps as django_apps


def nome_familia_produto(familia) -> str:
    """Rótulo da família no formato '0013 — FLANGE CEGO...'; usado pelo cadastro e pela auditoria."""
    figura = (getattr(familia, 'codigo_figura', '') or '').strip()
    descricao = (getattr(familia, 'descricao_base', '') or '').strip()
    return f'{figura} — {descricao}'.strip(' —') or str(familia)


def rotulo_de_choices(app_label: str, model_name: str, campo: str, valor) -> str | None:
    """Rótulo oficial da choices para o código; None se o campo não tem choices ou o código é desconhecido."""
    if valor in (None, ''):
        return None
    try:
        campo_modelo = django_apps.get_model(app_label, model_name)._meta.get_field(campo)
    except LookupError:
        return None
    for codigo, rotulo in (campo_modelo.choices or []):
        if str(codigo) == str(valor):
            return str(rotulo)
    return None


def rotulo_polegada(polegada) -> str:
    """Rótulo da polegada, idêntico ao usado no CRUD de polegadas."""
    if polegada is None:
        return ''
    tipo = polegada.tipo_medida or ''
    mm = f' — {polegada.valor_mm} mm' if polegada.valor_mm is not None else ''
    return f'{tipo} {polegada.codigo_oficial} — {polegada.descricao}{mm}'.strip()
