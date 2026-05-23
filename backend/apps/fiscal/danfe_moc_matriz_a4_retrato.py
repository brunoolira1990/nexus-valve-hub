"""
MOC 7.0 — Anexo II — Seção 3.8.1 — Formulário A-4 em modo retrato (folhas soltas).

Coordenadas Esq/Sup/Larg/Alt em centímetros, medidas a partir da área útil do formulário
(apos margem lateral/superior minima 0,2 cm conforme secoes 3.6.1 e 3.6.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class CampoCm(TypedDict):
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class BoxCm:
    x: float
    y: float
    w: float
    h: float


# Margens MOC 3.6.2 (minimo 0,2 cm; HTML/WeasyPrint usa 0,25 cm — Anexo II p.15)
MOC_MARGEM_LATERAL_CM = 0.25
MOC_MARGEM_SUPERIOR_CM = 0.25
MOC_HTML_FORM_LARGURA_CM = 20.57  # largura útil Anexo III.02 / tabela §3.8.1 (p.16–17)
MOC_FORM_ORIGEM_X_CM = 0.07  # primeira coluna «Esq» da tabela oficial
MOC_PAGINA_LARGURA_CM = 21.0
MOC_PAGINA_ALTURA_CM = 29.7
MOC_AREA_UTIL_LARGURA_CM = 20.0  # largura util do formulario (Esq max ~0.07 + 19.44)


def cm_to_pt(cm: float) -> float:
    return cm * (72.0 / 2.54)


def campo_absoluto(campo: CampoCm) -> BoxCm:
    """Converte coordenadas MOC (origem area util) para posicao na pagina A4."""
    return BoxCm(
        x=MOC_MARGEM_LATERAL_CM + campo['x'],
        y=MOC_MARGEM_SUPERIOR_CM + campo['y'],
        w=campo['w'],
        h=campo['h'],
    )


# --- Tabela 3.8.1 — blocos principais (Esq, Sup, Larg, Alt em cm) ---
DANFE_A4_RETRATO_CAMPOS: dict[str, CampoCm] = {
    # CANHOTO
    'canhoto_recebemos': {'x': 0.07, 'y': 0.42, 'w': 15.54, 'h': 0.85},
    'canhoto_nfe': {'x': 15.61, 'y': 0.42, 'w': 4.50, 'h': 1.70},
    'canhoto_data_recebimento': {'x': 0.07, 'y': 1.27, 'w': 10.00, 'h': 0.53},
    'canhoto_ident_assinatura': {'x': 10.07, 'y': 1.27, 'w': 10.04, 'h': 0.53},
    # DADOS NF-e (cabecalho)
    'emitente': {'x': 0.07, 'y': 1.80, 'w': 10.00, 'h': 3.92},
    'quadro_danfe': {'x': 10.07, 'y': 1.80, 'w': 9.44, 'h': 3.92},
    'codigo_barras': {'x': 11.20, 'y': 2.75, 'w': 8.31, 'h': 1.30},
    'chave_acesso': {'x': 0.07, 'y': 5.72, 'w': 11.13, 'h': 0.33},
    'natureza_operacao': {'x': 0.07, 'y': 6.05, 'w': 11.13, 'h': 0.33},
    'protocolo_autorizacao': {'x': 11.20, 'y': 6.05, 'w': 8.31, 'h': 0.33},
    'ie_emitente': {'x': 0.07, 'y': 6.38, 'w': 6.46, 'h': 0.33},
    'ie_st_emitente': {'x': 6.53, 'y': 6.38, 'w': 4.96, 'h': 0.33},
    'cnpj_emitente': {'x': 11.49, 'y': 6.38, 'w': 8.02, 'h': 0.33},
    # DESTINATARIO / REMETENTE (bloco)
    'destinatario_bloco': {'x': 0.07, 'y': 7.71, 'w': 19.44, 'h': 3.12},
    # FATURA / DUPLICATAS
    'fatura_duplicatas': {'x': 0.07, 'y': 10.83, 'w': 19.44, 'h': 0.83},
    # CALCULO DO IMPOSTO
    'calculo_imposto': {'x': 0.07, 'y': 11.66, 'w': 19.44, 'h': 1.67},
    # TRANSPORTADOR
    'transportador': {'x': 0.07, 'y': 13.33, 'w': 19.44, 'h': 2.42},
    # PRODUTOS / SERVICOS (coordenadas página Anexo II p.16–17: x=0,25 y=17,87 w=20,57 h=6,77)
    'produtos_bloco': {'x': 0.0, 'y': 17.62, 'w': 20.57, 'h': 6.77},
    'produtos_cabecalho': {'x': 0.0, 'y': 17.62, 'w': 20.57, 'h': 0.55},
    'produtos_corpo': {'x': 0.0, 'y': 18.17, 'w': 20.57, 'h': 6.22},
    # DADOS ADICIONAIS (página: inf. compl. y=26,33; fisco x=13,17 — margem 0,25 cm)
    'informacoes_complementares': {'x': 0.0, 'y': 26.08, 'w': 12.95, 'h': 3.07},
    'reservado_fisco': {'x': 12.92, 'y': 26.08, 'w': 7.62, 'h': 3.07},
    # Cabecalho repeticao (folhas 2+): area ate IE/CNPJ
    'cabecalho_continuacao': {'x': 0.07, 'y': 0.42, 'w': 19.44, 'h': 6.96},
    'produtos_bloco_continuacao': {'x': 0.07, 'y': 7.38, 'w': 19.44, 'h': 19.47},
    'rodape_impressao': {'x': 0.07, 'y': 29.35, 'w': 19.44, 'h': 0.25},
}

# Alias solicitado na fase 3.5.4.3 (mesma matriz §3.8.1)
DANFE_A4_RETRATO = DANFE_A4_RETRATO_CAMPOS


def campo_para_css(campo: CampoCm, *, escala_largura: bool = True) -> dict[str, str]:
    """
    Converte CampoCm (área útil §3.8.1) para top/left/width/height CSS dentro da margem @page.
    """
    x = campo['x'] - MOC_FORM_ORIGEM_X_CM
    if escala_largura and campo['w'] > 0:
        w = campo['w'] * (MOC_HTML_FORM_LARGURA_CM / 19.44)
    else:
        w = campo['w']
    return {
        'left': f'{max(x, 0):.2f}cm',
        'top': f'{campo["y"]:.2f}cm',
        'width': f'{w:.2f}cm',
        'height': f'{campo["h"]:.2f}cm',
    }


def campo_relativo(campo: CampoCm, origem: CampoCm) -> dict[str, str]:
    """Posição de subcampo relativa a um bloco pai."""
    rel = {
        'x': campo['x'] - origem['x'],
        'y': campo['y'] - origem['y'],
        'w': campo['w'],
        'h': campo['h'],
    }
    return campo_para_css(rel, escala_largura=False)

# Subcampos destinatario (coordenadas absolutas MOC dentro do formulario)
DANFE_DESTINATARIO_CAMPOS: dict[str, CampoCm] = {
    'dest_nome': {'x': 0.07, 'y': 8.37, 'w': 11.14, 'h': 0.66},
    'dest_cnpj': {'x': 11.21, 'y': 8.37, 'w': 4.28, 'h': 0.66},
    'dest_data_emissao': {'x': 15.49, 'y': 8.37, 'w': 4.02, 'h': 0.66},
    'dest_endereco': {'x': 0.07, 'y': 9.03, 'w': 11.14, 'h': 0.66},
    'dest_bairro': {'x': 11.21, 'y': 9.03, 'w': 4.28, 'h': 0.66},
    'dest_cep': {'x': 15.49, 'y': 9.03, 'w': 4.02, 'h': 0.66},
    'dest_data_saida': {'x': 0.07, 'y': 9.69, 'w': 2.78, 'h': 0.66},
    'dest_municipio': {'x': 2.85, 'y': 9.69, 'w': 7.35, 'h': 0.66},
    'dest_fone': {'x': 10.20, 'y': 9.69, 'w': 5.29, 'h': 0.66},
    'dest_uf': {'x': 15.49, 'y': 9.69, 'w': 1.02, 'h': 0.66},
    'dest_ie': {'x': 16.51, 'y': 9.69, 'w': 3.00, 'h': 0.66},
    'dest_hora_saida': {'x': 0.07, 'y': 10.35, 'w': 2.78, 'h': 0.66},
}

# Calculo imposto — duas linhas (MOC)
DANFE_IMPOSTO_CAMPOS: dict[str, CampoCm] = {
    'imp_base_icms': {'x': 0.07, 'y': 11.99, 'w': 3.88, 'h': 0.67},
    'imp_valor_icms': {'x': 3.95, 'y': 11.99, 'w': 3.88, 'h': 0.67},
    'imp_base_icms_st': {'x': 7.83, 'y': 11.99, 'w': 3.88, 'h': 0.67},
    'imp_valor_icms_st': {'x': 11.71, 'y': 11.99, 'w': 3.88, 'h': 0.67},
    'imp_valor_produtos': {'x': 15.59, 'y': 11.99, 'w': 3.92, 'h': 0.67},
    'imp_valor_frete': {'x': 0.07, 'y': 12.66, 'w': 3.88, 'h': 0.67},
    'imp_valor_seguro': {'x': 3.95, 'y': 12.66, 'w': 3.88, 'h': 0.67},
    'imp_desconto': {'x': 7.83, 'y': 12.66, 'w': 3.88, 'h': 0.67},
    'imp_outras_desp': {'x': 11.71, 'y': 12.66, 'w': 3.88, 'h': 0.67},
    'imp_valor_ipi': {'x': 15.59, 'y': 12.66, 'w': 1.96, 'h': 0.67},
    'imp_valor_total_nota': {'x': 17.55, 'y': 12.66, 'w': 1.96, 'h': 0.67},
}

# Transportador — tres linhas (MOC)
DANFE_TRANSPORTE_CAMPOS: dict[str, CampoCm] = {
    'transp_nome': {'x': 0.07, 'y': 13.66, 'w': 9.72, 'h': 0.69},
    'transp_frete': {'x': 9.79, 'y': 13.66, 'w': 2.54, 'h': 0.69},
    'transp_cod_antt': {'x': 12.33, 'y': 13.66, 'w': 2.54, 'h': 0.69},
    'transp_placa': {'x': 14.87, 'y': 13.66, 'w': 2.54, 'h': 0.69},
    'transp_uf_placa': {'x': 17.41, 'y': 13.66, 'w': 2.10, 'h': 0.69},
    'transp_cnpj': {'x': 0.07, 'y': 14.35, 'w': 6.46, 'h': 0.69},
    'transp_endereco': {'x': 6.53, 'y': 14.35, 'w': 6.46, 'h': 0.69},
    'transp_municipio': {'x': 12.99, 'y': 14.35, 'w': 4.28, 'h': 0.69},
    'transp_uf': {'x': 17.27, 'y': 14.35, 'w': 2.24, 'h': 0.69},
    'transp_ie': {'x': 0.07, 'y': 15.04, 'w': 6.46, 'h': 0.69},
    'transp_quantidade': {'x': 6.53, 'y': 15.04, 'w': 2.54, 'h': 0.69},
    'transp_especie': {'x': 9.07, 'y': 15.04, 'w': 2.54, 'h': 0.69},
    'transp_marca': {'x': 11.61, 'y': 15.04, 'w': 2.54, 'h': 0.69},
    'transp_numeracao': {'x': 14.15, 'y': 15.04, 'w': 2.54, 'h': 0.69},
    'transp_peso_bruto': {'x': 16.69, 'y': 15.04, 'w': 1.41, 'h': 0.69},
    'transp_peso_liquido': {'x': 18.10, 'y': 15.04, 'w': 1.41, 'h': 0.69},
}

# Colunas tabela produtos (Esq/Larg MOC 3.8.1 — ordem oficial; origem x=0 na área de 20,57 cm)
DANFE_PRODUTO_COLUNAS: list[tuple[str, CampoCm]] = [
    ('codigo', {'x': 0.0, 'y': 0.0, 'w': 2.14, 'h': 0.0}),
    ('descricao', {'x': 2.14, 'y': 0.0, 'w': 6.19, 'h': 0.0}),
    ('ncm', {'x': 8.33, 'y': 0.0, 'w': 1.50, 'h': 0.0}),
    ('cst', {'x': 9.83, 'y': 0.0, 'w': 0.90, 'h': 0.0}),
    ('cfop', {'x': 10.73, 'y': 0.0, 'w': 1.25, 'h': 0.0}),
    ('un', {'x': 11.98, 'y': 0.0, 'w': 0.87, 'h': 0.0}),
    ('qtd', {'x': 12.85, 'y': 0.0, 'w': 1.63, 'h': 0.0}),
    ('v_unit', {'x': 14.48, 'y': 0.0, 'w': 1.72, 'h': 0.0}),
    ('v_total', {'x': 16.20, 'y': 0.0, 'w': 1.50, 'h': 0.0}),
    ('bc_icms', {'x': 17.70, 'y': 0.0, 'w': 1.55, 'h': 0.0}),
    ('v_icms', {'x': 19.25, 'y': 0.0, 'w': 1.42, 'h': 0.0}),
    ('aliq_icms', {'x': 20.67, 'y': 0.0, 'w': 0.98, 'h': 0.0}),
]

# Cabeçalhos da tabela de produtos (MOC 3.8.1)
DANFE_PRODUTO_HEADER_LABELS: dict[str, str] = {
    'codigo': 'CÓDIGO',
    'descricao': 'DESCRIÇÃO DOS PRODUTOS/SERVIÇOS',
    'ncm': 'NCM/SH',
    'cst': 'CST',
    'cfop': 'CFOP',
    'un': 'UN',
    'qtd': 'QUANT.',
    'v_unit': 'V.UNIT',
    'v_total': 'V.TOTAL',
    'bc_icms': 'BC ICMS',
    'v_icms': 'V.ICMS',
    'aliq_icms': 'ALÍQ.ICMS',
}

# Colunas combinadas (legado — preferir DANFE_PRODUTO_COLUNAS na 3.5.4.3)
DANFE_PRODUTO_COLUNAS_COMBINADAS: list[tuple[str, float, list[str]]] = [
    ('CÓDIGO / NCM', 3.44, ['codigo', 'ncm']),
    ('CST / CFOP', 2.03, ['cst', 'cfop']),
    ('DESCRIÇÃO', 5.84, ['descricao']),
    ('QTD / UN', 2.36, ['qtd', 'un']),
    ('V.UNIT / DESC', 1.62, ['v_unit', 'desconto']),
    ('V.TOTAL / BC', 2.88, ['v_total', 'bc_icms']),
    ('V.ICMS / V.IPI', 2.80, ['v_icms', 'v_ipi']),
    ('ALÍQ.ICMS/IPI', 1.86, ['aliq_icms', 'aliq_ipi']),
]
