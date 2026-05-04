"""
Regras de família/figura: `tipo_regra_codigo` é a fonte da verdade.
As flags `usa_*` são sempre derivadas do tipo — não editáveis independentemente.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from apps.produtos.models import FamiliaProduto


class FlagsFamilia(TypedDict):
    usa_rosca_conexao: bool
    usa_schedule: bool
    usa_polegada_principal: bool
    usa_polegada_secundaria: bool


def flags_por_tipo_regra(tipo: str) -> FlagsFamilia:
    """Retorna as flags obrigatórias para o tipo de regra (única fonte da verdade)."""
    from apps.produtos.models import FamiliaProduto

    t = FamiliaProduto.TipoRegraCodigo
    table: dict[str, FlagsFamilia] = {
        t.BASE_POLEGADA: FlagsFamilia(
            usa_rosca_conexao=False,
            usa_schedule=False,
            usa_polegada_principal=True,
            usa_polegada_secundaria=False,
        ),
        t.BASE_ROSCA_POLEGADA: FlagsFamilia(
            usa_rosca_conexao=True,
            usa_schedule=False,
            usa_polegada_principal=True,
            usa_polegada_secundaria=False,
        ),
        t.BASE_DUAS_POLEGADAS: FlagsFamilia(
            usa_rosca_conexao=False,
            usa_schedule=False,
            usa_polegada_principal=True,
            usa_polegada_secundaria=True,
        ),
        t.BASE_ROSCA_DUAS_POLEGADAS: FlagsFamilia(
            usa_rosca_conexao=True,
            usa_schedule=False,
            usa_polegada_principal=True,
            usa_polegada_secundaria=True,
        ),
        t.BASE_SCHEDULE_POLEGADA: FlagsFamilia(
            usa_rosca_conexao=False,
            usa_schedule=True,
            usa_polegada_principal=True,
            usa_polegada_secundaria=False,
        ),
        t.BASE_SCHEDULE_DUAS_POLEGADAS: FlagsFamilia(
            usa_rosca_conexao=False,
            usa_schedule=True,
            usa_polegada_principal=True,
            usa_polegada_secundaria=True,
        ),
        t.BASE_ROSCA_SCHEDULE_POLEGADA: FlagsFamilia(
            usa_rosca_conexao=True,
            usa_schedule=True,
            usa_polegada_principal=True,
            usa_polegada_secundaria=False,
        ),
        t.BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS: FlagsFamilia(
            usa_rosca_conexao=True,
            usa_schedule=True,
            usa_polegada_principal=True,
            usa_polegada_secundaria=True,
        ),
        t.UNDERSCORE_POLEGADA: FlagsFamilia(
            usa_rosca_conexao=False,
            usa_schedule=False,
            usa_polegada_principal=True,
            usa_polegada_secundaria=False,
        ),
        t.MANUAL_FABRICANTE: FlagsFamilia(
            usa_rosca_conexao=False,
            usa_schedule=False,
            usa_polegada_principal=False,
            usa_polegada_secundaria=False,
        ),
    }
    if tipo not in table:
        raise ValueError(f'tipo_regra_codigo desconhecido: {tipo!r}')
    return table[tipo]


def aplicar_flags_derivadas_na_instancia(familia: FamiliaProduto) -> None:
    flags = flags_por_tipo_regra(familia.tipo_regra_codigo)
    familia.usa_rosca_conexao = flags['usa_rosca_conexao']
    familia.usa_schedule = flags['usa_schedule']
    familia.usa_polegada_principal = flags['usa_polegada_principal']
    familia.usa_polegada_secundaria = flags['usa_polegada_secundaria']


def aplicar_flags_derivadas_no_dict(attrs: dict, tipo: str) -> None:
    flags = flags_por_tipo_regra(tipo)
    attrs['usa_rosca_conexao'] = flags['usa_rosca_conexao']
    attrs['usa_schedule'] = flags['usa_schedule']
    attrs['usa_polegada_principal'] = flags['usa_polegada_principal']
    attrs['usa_polegada_secundaria'] = flags['usa_polegada_secundaria']
