"""Material de produto: rótulos de exibição e valores canônicos persistidos."""

from __future__ import annotations

from apps.text_normalize import to_operational_upper

# Valor persistido (uppercase sem acento) → rótulo de exibição
MATERIAL_CANONICO_PARA_LABEL: dict[str, str] = {
    'ACO CARBONO': 'Aço Carbono',
    'ACO INOXIDAVEL': 'Aço Inoxidável',
    'ACO LIGA': 'Aço Liga',
    'FERRO FUNDIDO': 'Ferro Fundido',
    'BRONZE': 'Bronze',
    'LATAO': 'Latão',
}

# Rótulos aceitos no formulário (frontend MATERIAIS)
MATERIAL_LABELS_FORM: tuple[str, ...] = tuple(MATERIAL_CANONICO_PARA_LABEL.values())

_LABEL_PARA_CANONICO: dict[str, str] = {
    label.upper(): canon for canon, label in MATERIAL_CANONICO_PARA_LABEL.items()
}
_LABEL_PARA_CANONICO.update({canon: canon for canon in MATERIAL_CANONICO_PARA_LABEL})


def material_label_de_valor(valor: str | None) -> str:
    """Rótulo amigável para listagem/detalhe; vazio se ausente."""
    bruto = (valor or '').strip()
    if not bruto:
        return ''
    chave = to_operational_upper(bruto)
    if chave in MATERIAL_CANONICO_PARA_LABEL:
        return MATERIAL_CANONICO_PARA_LABEL[chave]
    for canon, label in MATERIAL_CANONICO_PARA_LABEL.items():
        if canon in chave or label.upper() == chave:
            return label
    if bruto.isupper() and len(bruto) > 2:
        return bruto.title()
    return bruto


def material_valor_para_form(valor: str | None) -> str:
    """Valor inicial do select (deve coincidir com MATERIAIS do frontend)."""
    label = material_label_de_valor(valor)
    if label in MATERIAL_LABELS_FORM:
        return label
    bruto = (valor or '').strip()
    if bruto in MATERIAL_LABELS_FORM:
        return bruto
    return label or bruto


def material_canonico_de_entrada(valor: str | None) -> str:
    """Normaliza entrada da API/formulário para persistência."""
    bruto = (valor or '').strip()
    if not bruto:
        return ''
    chave = to_operational_upper(bruto)
    if chave in _LABEL_PARA_CANONICO:
        return _LABEL_PARA_CANONICO[chave]
    for label in MATERIAL_LABELS_FORM:
        if to_operational_upper(label) == chave:
            return _LABEL_PARA_CANONICO[label.upper()]
    return chave
