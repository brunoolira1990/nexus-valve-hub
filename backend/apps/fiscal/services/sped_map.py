"""
Indicadores de aderência futura à EFD ICMS/IPI e EFD Contribuições (sem geração de TXT).

Somente contagem e listas de alertas de completude; não substitui PVA/validador oficial.
"""

from __future__ import annotations

from typing import Any

SPED_MODELOS_NFE = frozenset({'55', '65'})


def montar_base_efd_icms_ipi(
    *,
    notas_c100_candidatas: int,
    notas_sem_chave: int,
    notas_modelo_nao_mapeado: int,
    itens_c170_candidatos: int,
    itens_sem_produto_0150: int,
    itens_sem_ncm_0200: int,
    grupamentos_c190_possiveis: int,
    alertas: list[str],
) -> dict[str, Any]:
    return {
        'registros_planejados': {
            'bloco_0': ['0000', '0001', '0005', '0100', '0150', '0190', '0200'],
            'bloco_c': ['C100', 'C170', 'C190'],
            'bloco_e': ['E100', 'E110', 'E111', 'E116'],
            'bloco_h': ['H005', 'H010'],
        },
        'indicadores': {
            'notas_mapeaveis_c100': notas_c100_candidatas,
            'notas_com_campos_faltantes_c100': notas_sem_chave + notas_modelo_nao_mapeado,
            'itens_mapeaveis_c170': itens_c170_candidatos,
            'itens_cadastro_participante_0150_pendentes': itens_sem_produto_0150,
            'produtos_cadastro_0200_pendentes': itens_sem_ncm_0200,
            'agrupamentos_possiveis_c190': grupamentos_c190_possiveis,
        },
        'alertas': alertas,
        'txt_oficial': False,
        'observacao': 'Pré-visualização gerencial; geração de TXT EFD ICMS/IPI não implementada nesta versão.',
    }


def montar_base_efd_contribuicoes(
    *,
    notas_com_pis_cofins_doc: int,
    itens_com_cst_pis: int,
    itens_com_cst_cofins: int,
    itens_base_pis_preenchida: int,
    itens_base_cofins_preenchida: int,
    creditos_entrada_possiveis: int,
    debitos_saida_possiveis: int,
    alertas: list[str],
) -> dict[str, Any]:
    return {
        'registros_planejados': {
            'bloco_0': ['0000', '0001', '0005', '0100', '0140', '0150'],
            'bloco_a': ['A100', 'A170'],
            'bloco_c': ['C100', 'C170', 'C180', 'C181', 'C185'],
            'bloco_m': ['M100', 'M105', 'M200', 'M205', 'M500', 'M505', 'M600', 'M605'],
        },
        'indicadores': {
            'notas_com_totais_pis_cofins_documento': notas_com_pis_cofins_doc,
            'itens_com_cst_pis': itens_com_cst_pis,
            'itens_com_cst_cofins': itens_com_cst_cofins,
            'itens_com_base_pis': itens_base_pis_preenchida,
            'itens_com_base_cofins': itens_base_cofins_preenchida,
            'creditos_entrada_possiveis': creditos_entrada_possiveis,
            'debitos_saida_possiveis': debitos_saida_possiveis,
        },
        'alertas': alertas,
        'txt_oficial': False,
        'observacao': 'Encerramento de EFD Contribuições depende de regime tributário e parametrização; não automatizado.',
    }


def modelo_mapeado_sped_nfe(modelo: str) -> bool:
    return (modelo or '').strip() in SPED_MODELOS_NFE
