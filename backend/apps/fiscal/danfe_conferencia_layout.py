"""Layout do bloco FATURA / DUPLICATAS no DANFE de conferência (somente esta seção)."""

from __future__ import annotations

from typing import Any

MAX_DUPLICATAS_NO_BLOCO = 10
FATURA_COLUNAS_DUP = 5
FATURA_BLOCO_BASE_H_CM = 0.83
FATURA_EXTRA_LINHA_DUP_CM = 0.36

IMPOSTO_LABELS_DISPLAY: dict[str, str] = {
    'imp_valor_produtos': 'VALOR TOTAL\nDOS PRODUTOS',
}


def calcular_layout_fatura_duplicatas(qtd_duplicatas: int) -> dict[str, float | int]:
    """
    Altura extra só quando há mais de 5 parcelas (2ª linha na grade de 5 colunas).
    Demais blocos MOC descem apenas ``extra_offset_cm``.
    """
    n = min(max(int(qtd_duplicatas or 0), 0), MAX_DUPLICATAS_NO_BLOCO)
    extra = FATURA_EXTRA_LINHA_DUP_CM if n > FATURA_COLUNAS_DUP else 0.0
    linhas = 2 if n > FATURA_COLUNAS_DUP else (1 if n else 0)
    return {
        'colunas': FATURA_COLUNAS_DUP,
        'linhas_dup': linhas,
        'bloco_altura_cm': FATURA_BLOCO_BASE_H_CM + extra,
        'extra_offset_cm': extra,
    }


def preparar_duplicatas_danfe(duplicatas: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], str]:
    """Limita duplicatas no bloco; excedente vai para dados adicionais."""
    dups = list(duplicatas or [])
    if len(dups) <= MAX_DUPLICATAS_NO_BLOCO:
        return dups, ''
    visiveis = dups[:MAX_DUPLICATAS_NO_BLOCO]
    overflow = dups[MAX_DUPLICATAS_NO_BLOCO :]
    partes = [
        f"Dup. {d.get('numero', '—')} Venc. {d.get('vencimento', '—')} {d.get('valor', '—')}"
        for d in overflow
    ]
    return visiveis, 'Demais duplicatas: ' + ' | '.join(partes)


def aplicar_layout_em_dados_danfe(dados: dict[str, Any], nf) -> None:
    visiveis, overflow_txt = preparar_duplicatas_danfe(dados.get('duplicatas'))
    dados['duplicatas'] = visiveis
    dados['layout_fatura'] = calcular_layout_fatura_duplicatas(len(visiveis))
    if overflow_txt:
        base = (dados.get('informacoes_complementares') or '').strip()
        dados['informacoes_complementares'] = f'{base}\n{overflow_txt}'.strip() if base else overflow_txt
