"""Constantes de escopo do MVP de auditoria."""

from __future__ import annotations

# Únicas entidades consultáveis via API nesta fase.
# Chaves sempre em minúsculas: (app_label, model_name).
MODELOS_AUDITADOS: frozenset[tuple[str, str]] = frozenset(
    {
        ('cadastros', 'cliente'),
        ('produtos', 'produto'),
    }
)


def entidade_auditada_permitida(app_label: str, model_name: str) -> tuple[str, str] | None:
    """Normaliza e valida app/model; retorna a chave canônica ou None."""
    chave = ((app_label or '').strip().lower(), (model_name or '').strip().lower())
    if chave not in MODELOS_AUDITADOS:
        return None
    return chave
