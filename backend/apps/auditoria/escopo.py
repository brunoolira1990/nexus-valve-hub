"""Constantes de escopo do MVP de auditoria."""

from __future__ import annotations

# Chaves sempre em minúsculas: (app_label, model_name).
# model_name é o nome lowercase da classe (NFeSaida -> 'nfesaida'), igual a 'familiaproduto'.
MODELOS_AUDITADOS: frozenset[tuple[str, str]] = frozenset(
    {
        ('cadastros', 'cliente'),
        ('cadastros', 'fornecedor'),
        ('cadastros', 'transportadora'),
        ('produtos', 'produto'),
        ('produtos', 'familiaproduto'),
        # Documentos (Sprint 3.18): só os modelos com caminho de escrita real. CTeEntrada existe
        # mas o viewset é ReadOnly e a tela CT-e lista CTeHistoricoImportado, então fica fora.
        ('comercial', 'cotacaofornecedor'),
        ('comercial', 'proposta'),
        ('comercial', 'pedidovenda'),
        ('comercial', 'pedidocompra'),
        ('fiscal', 'nfesaida'),
        ('fiscal', 'nfeentrada'),
        # Fase 1 do redesenho da entrada de terceiros: documentos de entrada com
        # caminho de escrita real (importação de XML + actions de conferência).
        # CTeEntrada continua fora (viewset ReadOnly, sem escrita em produção).
        ('fiscal', 'nfeentradahistoricaimportada'),
        ('fiscal', 'nfeentradaconferencia'),
        ('fiscal', 'ctehistoricoimportado'),
    }
)


def entidade_auditada_permitida(app_label: str, model_name: str) -> tuple[str, str] | None:
    """Normaliza e valida app/model; retorna a chave canônica ou None."""
    chave = ((app_label or '').strip().lower(), (model_name or '').strip().lower())
    if chave not in MODELOS_AUDITADOS:
        return None
    return chave
