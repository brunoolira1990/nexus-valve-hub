"""
Tipo dimensional da família: significado dos campos / UI / descrição.
`tipo_regra_codigo` continua sendo a única fonte de como o código é montado.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from apps.produtos.familia_regra import flags_por_tipo_regra

if TYPE_CHECKING:
    from apps.produtos.models import FamiliaProduto


def familia_espigao_x_flange_nps(familia: 'FamiliaProduto') -> bool:
    """Família no fluxo espigão × flange (E…F…): allowlist de polegadas na família é opcional até existir cadastro."""
    from apps.produtos.models import FamiliaProduto

    td = FamiliaProduto.TipoDimensional.ESPIGAO_X_FLANGE
    tr = FamiliaProduto.TipoRegraCodigo.BASE_ESPIGAO_FLANGE_NPS
    raw_td = getattr(familia, 'tipo_dimensional', None)
    raw_tr = getattr(familia, 'tipo_regra_codigo', None)
    if raw_tr == tr or raw_td == td:
        return True
    tr_norm = str(getattr(raw_tr, 'value', raw_tr) or '').strip().upper()
    td_norm = str(getattr(raw_td, 'value', raw_td) or '').strip().upper()
    return tr_norm == tr.value or td_norm == td.value


class RequisitosEfetivosProduto(TypedDict):
    """Flags efetivas após combinar regra de código + tipo dimensional."""

    usa_rosca_conexao: bool
    usa_schedule: bool
    usa_polegada_principal: bool
    usa_polegada_secundaria: bool
    exige_od_mm: bool
    exige_espessura_mm: bool
    exige_comprimento_mm: bool
    incluir_schedule_na_descricao: bool


def _schedule_code_rules():
    from apps.produtos.models import FamiliaProduto

    t = FamiliaProduto.TipoRegraCodigo
    return frozenset(
        {
            t.BASE_SCHEDULE_POLEGADA,
            t.BASE_SCHEDULE_DUAS_POLEGADAS,
            t.BASE_ROSCA_SCHEDULE_POLEGADA,
            t.BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS,
        },
    )


def validar_tipo_dimensional_x_regra(*, tipo_dimensional: str, tipo_regra_codigo: str) -> str | None:
    """Retorna mensagem de erro ou None se a combinação é aceita."""
    from apps.produtos.models import FamiliaProduto

    Td = FamiliaProduto.TipoDimensional
    Tr = FamiliaProduto.TipoRegraCodigo

    if tipo_dimensional in ('', None):
        return None
    if tipo_dimensional in (Td.MANUAL, Td.LEGADO):
        return None
    if tipo_dimensional == Td.SIMPLES:
        return None

    sch_rules = _schedule_code_rules()

    if tipo_dimensional == Td.NPS_SCHEDULE and tipo_regra_codigo not in sch_rules:
        return 'NPS/SCH exige uma regra de código com schedule (opções 5 a 8).'

    if tipo_dimensional == Td.REDUCAO_NPS and tipo_regra_codigo not in {
        Tr.BASE_SCHEDULE_DUAS_POLEGADAS,
        Tr.BASE_ROSCA_SCHEDULE_DUAS_POLEGADAS,
    }:
        return 'Redução NPS/SCH exige regra 6 ou 8 (base + schedule + duas polegadas).'

    if tipo_dimensional in (Td.OD_POLEGADA, Td.OD_POLEGADA_X_ROSCA) and tipo_regra_codigo in sch_rules:
        return 'OD não é NPS/SCH: use regra sem schedule no código (por exemplo 1 ou 4).'

    if tipo_dimensional == Td.OD_POLEGADA and tipo_regra_codigo not in {
        Tr.BASE_POLEGADA,
        Tr.UNDERSCORE_POLEGADA,
    }:
        return 'OD em polegada combina com regra 1 (base + polegada) ou 9 (underscore).'

    if tipo_dimensional == Td.OD_POLEGADA_X_ROSCA and tipo_regra_codigo != Tr.BASE_ROSCA_DUAS_POLEGADAS:
        return 'OD x Rosca exige regra 4 (base + rosca + duas polegadas).'

    if tipo_dimensional in (Td.OD_MM, Td.OD_MM_X_ESPESSURA, Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO):
        if tipo_regra_codigo != Tr.BASE_OD_MM_ESPESSURA:
            return 'OD em mm exige regra 11 (base + OD mm + espessura mm).'

    if tipo_dimensional == Td.NPS_X_ROSCA and tipo_regra_codigo != Tr.BASE_ROSCA_POLEGADA:
        return 'NPS x Rosca exige regra 2 (base + rosca + polegada).'

    if tipo_dimensional == Td.ESPIGAO_X_FLANGE and tipo_regra_codigo != Tr.BASE_ESPIGAO_FLANGE_NPS:
        return 'Espigão x Flange exige a regra Base + espigão NPS + flange NPS (E…F…).'

    if tipo_regra_codigo == Tr.BASE_ESPIGAO_FLANGE_NPS and tipo_dimensional != Td.ESPIGAO_X_FLANGE:
        return 'A regra E…F… (espigão x flange) exige o tipo dimensional Espigão x Flange.'

    if tipo_regra_codigo == Tr.BASE_OD_MM_ESPESSURA and tipo_dimensional not in (
        Td.OD_MM,
        Td.OD_MM_X_ESPESSURA,
        Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO,
    ):
        return 'Regra 11 exige tipo dimensional OD em mm (OD_MM, OD_MM_X_ESPESSURA ou OD_MM_X_ESPESSURA_X_COMPRIMENTO).'

    return None


def requisitos_efetivos_produto(familia: FamiliaProduto) -> RequisitosEfetivosProduto:
    from apps.produtos.models import FamiliaProduto

    flags = flags_por_tipo_regra(familia.tipo_regra_codigo)
    td = familia.tipo_dimensional or FamiliaProduto.TipoDimensional.SIMPLES
    Td = FamiliaProduto.TipoDimensional
    Tr = FamiliaProduto.TipoRegraCodigo

    r: RequisitosEfetivosProduto = {
        'usa_rosca_conexao': flags['usa_rosca_conexao'],
        'usa_schedule': flags['usa_schedule'],
        'usa_polegada_principal': flags['usa_polegada_principal'],
        'usa_polegada_secundaria': flags['usa_polegada_secundaria'],
        'exige_od_mm': False,
        'exige_espessura_mm': False,
        'exige_comprimento_mm': False,
        'incluir_schedule_na_descricao': bool(flags['usa_schedule']),
    }

    if familia.tipo_regra_codigo == Tr.BASE_OD_MM_ESPESSURA:
        r['usa_rosca_conexao'] = False
        r['usa_schedule'] = False
        r['usa_polegada_principal'] = False
        r['usa_polegada_secundaria'] = False
        r['exige_od_mm'] = True
        r['exige_espessura_mm'] = True
        r['incluir_schedule_na_descricao'] = False
        if td == Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO:
            r['exige_comprimento_mm'] = True
        return r

    if td in (
        Td.OD_POLEGADA,
        Td.OD_POLEGADA_X_ROSCA,
        Td.OD_MM,
        Td.OD_MM_X_ESPESSURA,
        Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO,
        Td.CHAPA_MM,
        Td.CHAPA_FURO_MM,
        Td.BARRA_CHATA_MM,
        Td.METALON_MM,
        Td.PERFIL_RETANGULAR_MM,
        Td.CANTONEIRA_MM,
        Td.DIMENSIONAL_LIVRE_CONTROLADO,
    ):
        r['usa_schedule'] = False
        r['incluir_schedule_na_descricao'] = False

    if td == Td.NPS_SCHEDULE:
        r['usa_schedule'] = True
        r['usa_polegada_principal'] = True
        r['incluir_schedule_na_descricao'] = True

    if td == Td.REDUCAO_NPS:
        r['usa_schedule'] = True
        r['usa_polegada_principal'] = True
        r['usa_polegada_secundaria'] = True
        r['incluir_schedule_na_descricao'] = True

    if td == Td.NPS:
        r['incluir_schedule_na_descricao'] = bool(flags['usa_schedule'])

    if td == Td.NPS_X_ROSCA:
        r['usa_rosca_conexao'] = True
        r['usa_polegada_principal'] = True
        r['usa_schedule'] = False
        r['incluir_schedule_na_descricao'] = False

    if familia_espigao_x_flange_nps(familia):
        r['usa_rosca_conexao'] = False
        r['usa_schedule'] = False
        r['usa_polegada_principal'] = True
        r['usa_polegada_secundaria'] = True
        r['incluir_schedule_na_descricao'] = False

    if td == Td.OD_POLEGADA:
        r['usa_polegada_principal'] = True
        r['usa_polegada_secundaria'] = False

    if td == Td.OD_POLEGADA_X_ROSCA:
        r['usa_rosca_conexao'] = True
        r['usa_polegada_principal'] = True
        r['usa_polegada_secundaria'] = True

    if td in (Td.OD_MM, Td.OD_MM_X_ESPESSURA, Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO):
        r['exige_od_mm'] = True
        r['exige_espessura_mm'] = td != Td.OD_MM
        r['exige_comprimento_mm'] = td == Td.OD_MM_X_ESPESSURA_X_COMPRIMENTO
        r['usa_polegada_principal'] = False
        r['usa_polegada_secundaria'] = False
        r['usa_rosca_conexao'] = False
        r['usa_schedule'] = False

    if td in (
        Td.CHAPA_MM,
        Td.CHAPA_FURO_MM,
        Td.BARRA_CHATA_MM,
        Td.METALON_MM,
        Td.PERFIL_RETANGULAR_MM,
        Td.CANTONEIRA_MM,
        Td.DIMENSIONAL_LIVRE_CONTROLADO,
    ):
        r['usa_polegada_principal'] = False
        r['usa_polegada_secundaria'] = False
        r['usa_rosca_conexao'] = False
        r['usa_schedule'] = False

    if td == Td.CANTONEIRA_POLEGADA:
        r['usa_polegada_principal'] = True
        r['usa_polegada_secundaria'] = True
        r['usa_rosca_conexao'] = False
        r['usa_schedule'] = False

    return r


def comprimento_mm_efetivo(
    *,
    comprimento_mm: Decimal | None,
    familia: FamiliaProduto | None,
) -> Decimal | None:
    if comprimento_mm is not None:
        return comprimento_mm
    if familia and familia.comprimento_padrao_barra_m:
        return (familia.comprimento_padrao_barra_m * Decimal('1000')).quantize(Decimal('1'))
    return None


def validar_campos_obrigatorios_produto_interno(
    familia: FamiliaProduto,
    *,
    rosca,
    schedule,
    polegada_principal,
    polegada_secundaria,
    od_mm: Decimal | None,
    espessura_mm: Decimal | None,
    comprimento_mm_resolvido: Decimal | None,
) -> dict[str, str]:
    """Retorna mapa campo -> mensagem (uma por campo). Vazio se OK."""
    from apps.produtos.models import FamiliaProduto

    req = requisitos_efetivos_produto(familia)
    td = familia.tipo_dimensional or FamiliaProduto.TipoDimensional.SIMPLES
    Td = FamiliaProduto.TipoDimensional
    Tr = FamiliaProduto.TipoRegraCodigo
    espigao_x_flange_efetivo = familia_espigao_x_flange_nps(familia)
    errs: dict[str, str] = {}

    if req['usa_schedule'] and schedule is None:
        errs['schedule_ref_id'] = 'Informe o Schedule/Espessura.'
    if req['usa_rosca_conexao'] and rosca is None:
        errs['rosca_conexao_id'] = 'Informe o Tipo de rosca/conexão.'
    if req['usa_polegada_principal'] and polegada_principal is None:
        if espigao_x_flange_efetivo:
            errs['polegada_principal_ref_id'] = 'Informe a medida do espigão.'
        elif td == Td.OD_POLEGADA:
            errs['polegada_principal_ref_id'] = 'Informe a Medida OD.'
        elif td == Td.NPS_SCHEDULE:
            errs['polegada_principal_ref_id'] = 'Informe a polegada nominal (NPS).'
        else:
            errs['polegada_principal_ref_id'] = 'Informe a polegada principal.'
    if req['usa_polegada_secundaria'] and polegada_secundaria is None:
        if espigao_x_flange_efetivo:
            errs['polegada_secundaria_ref_id'] = 'Informe a medida da flange.'
        elif td == Td.REDUCAO_NPS:
            errs['polegada_secundaria_ref_id'] = 'Informe a Polegada menor da redução.'
        elif td == Td.OD_POLEGADA_X_ROSCA:
            errs['polegada_secundaria_ref_id'] = 'Informe a Medida da rosca.'
        else:
            errs['polegada_secundaria_ref_id'] = 'Informe a polegada secundária.'

    if req['exige_od_mm'] and od_mm is None:
        errs['od_mm'] = 'Informe o OD externo em mm.'
    if req['exige_espessura_mm'] and espessura_mm is None:
        errs['espessura_mm'] = 'Informe a Espessura em mm.'
    if req['exige_comprimento_mm'] and comprimento_mm_resolvido is None:
        errs['comprimento_mm'] = 'Informe o Comprimento em mm.'
    return errs


def tipo_medida_esperado_por_campo(familia: FamiliaProduto) -> dict[str, str | None]:
    """Mapeia o tipo de medida esperado para cada campo de polegada do produto."""
    from apps.produtos.models import FamiliaProduto, Polegada

    td = familia.tipo_dimensional or FamiliaProduto.TipoDimensional.SIMPLES
    Td = FamiliaProduto.TipoDimensional
    Tr = FamiliaProduto.TipoRegraCodigo
    tipo_nps = Polegada.TipoMedida.NPS
    tipo_od = Polegada.TipoMedida.OD

    if familia_espigao_x_flange_nps(familia):
        return {'polegada_principal_ref_id': tipo_nps, 'polegada_secundaria_ref_id': tipo_nps}

    principal: str | None = None
    secundaria: str | None = None

    if td in (Td.OD_POLEGADA, Td.OD_POLEGADA_X_ROSCA):
        principal = tipo_od
    elif td in (
        Td.NPS,
        Td.NPS_SCHEDULE,
        Td.REDUCAO_NPS,
        Td.NPS_X_ROSCA,
        Td.FLANGE,
        Td.VALVULA,
        Td.ROSCA,
        Td.ROSCA_X_ROSCA,
    ):
        principal = tipo_nps

    if td == Td.REDUCAO_NPS:
        secundaria = tipo_nps
    elif td == Td.OD_POLEGADA_X_ROSCA:
        secundaria = tipo_nps
    elif td in (Td.NPS, Td.NPS_SCHEDULE, Td.NPS_X_ROSCA, Td.ROSCA_X_ROSCA):
        secundaria = tipo_nps

    return {'polegada_principal_ref_id': principal, 'polegada_secundaria_ref_id': secundaria}
