"""Catálogo canônico de roscas/conexões (uso em seed; sem escrita na API de listagem)."""

from __future__ import annotations

from apps.produtos.models import RoscaConexao

# (codigo, descricao, observacao)
ROSCAS_CONEXAO_CANONICAS: tuple[tuple[str, str, str], ...] = (
    ('', 'BSP / padrão da família', ''),
    ('N', 'NPT', ''),
    ('SW', 'Socket Weld / Solda de encaixe', ''),
    ('OD', 'OD / dupla anilha', ''),
    ('ODN', 'OD + NPT', ''),
    ('U', 'UNF', ''),
    ('JN', 'JIC x NPT', ''),
    ('NS', 'NPT x SW', ''),
    ('FN', 'Fêmea NPT', ''),
    ('FMN', 'Fêmea-macho NPT', ''),
    ('MFU', 'Macho-fêmea UNF x BSP', ''),
    ('FF', 'Fêmea-fêmea', ''),
    ('MMN', 'Macho-macho NPT', ''),
)


def seed_roscas_conexao_canonicas() -> None:
    """Cria/atualiza opções base via seed idempotente. Não altera registros legados (ex.: código S)."""
    for codigo, descricao, observacao in ROSCAS_CONEXAO_CANONICAS:
        RoscaConexao.objects.update_or_create(
            codigo=codigo,
            defaults={'descricao': descricao, 'observacao': observacao, 'ativo': True},
        )
