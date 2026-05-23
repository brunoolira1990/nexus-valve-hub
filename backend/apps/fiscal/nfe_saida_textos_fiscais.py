"""Textos fiscais e recomendações da regra fiscal → NF-e rascunho (NF-e Saída 3.5.2.3)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_saida_preview import LABEL_RECOMENDACAO
from apps.regras_fiscais.models import RegraFiscalSaida
from apps.regras_fiscais.recomendacoes_nfe_config import normalizar_recomendacoes_nfe

SEPARADOR_OBS_REGRA = '\n\n--- Observações fiscais da regra ---\n'

CAMPOS_TEXTO_NF_LABEL: dict[str, str] = {
    'informacoes_adicionais': 'Informações adicionais da NF-e',
    'observacoes_nfe': 'Observações da NF-e',
    'informacoes_fisco': 'Informações ao Fisco',
}

# origem no model RegraFiscalSaida → destino em NFeSaida
MAPEAMENTO_TEXTO_REGRA_NF: tuple[tuple[str, str], ...] = (
    ('informacoes_complementares', 'informacoes_adicionais'),
    ('observacoes', 'observacoes_nfe'),
)


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _nome_regra(regra: RegraFiscalSaida) -> str:
    return _text(regra.nome) or _text(regra.descricao_cenario) or f'Regra fiscal #{regra.pk}'


def mesclar_texto_campo(atual: str, novo: str) -> tuple[str, bool]:
    """Não apaga texto do usuário; faz append seguro quando necessário."""
    atual_n = (atual or '').strip()
    novo_n = (novo or '').strip()
    if not novo_n:
        return atual_n, False
    if not atual_n:
        return novo_n, True
    if novo_n in atual_n:
        return atual_n, False
    return atual_n + SEPARADOR_OBS_REGRA + novo_n, True


def _combinar_textos_de_regras(regras: list[RegraFiscalSaida], campo_regra: str) -> str:
    vistos: set[str] = set()
    partes: list[str] = []
    for regra in regras:
        raw = _text(getattr(regra, campo_regra, ''))
        if not raw or raw in vistos:
            continue
        vistos.add(raw)
        partes.append(raw)
    return '\n\n'.join(partes)


def extrair_recomendacoes_regra(regra: RegraFiscalSaida) -> list[dict[str, str]]:
    norm = normalizar_recomendacoes_nfe(regra.recomendacoes_nfe)
    if not norm:
        return []
    origem = _nome_regra(regra)
    out: list[dict[str, str]] = []
    for key, ativo in norm.items():
        if not ativo:
            continue
        tipo = 'DANFE' if key.startswith('danfe') or key.startswith('exibir_') or key.startswith('ocultar_') else 'NF-e'
        out.append(
            {
                'origem': origem,
                'tipo': tipo,
                'codigo': key,
                'mensagem': LABEL_RECOMENDACAO.get(key, key.replace('_', ' ')),
            },
        )
    return out


def mesclar_recomendacoes_snapshot(snap: dict[str, Any], regra: RegraFiscalSaida | None) -> tuple[dict[str, Any], bool]:
    if regra is None:
        return snap, False
    norm_regra = normalizar_recomendacoes_nfe(regra.recomendacoes_nfe)
    if not norm_regra:
        return snap, False
    snap_out = dict(snap)
    atual = normalizar_recomendacoes_nfe(snap_out.get('recomendacoes_nfe')) or {}
    merged = dict(atual)
    changed = False
    for key, val in norm_regra.items():
        if val and not merged.get(key):
            merged[key] = True
            changed = True
    if changed:
        snap_out['recomendacoes_nfe'] = merged
    return snap_out, changed


def calcular_textos_fiscais_preview(
    nf: NFeSaida,
    regras: list[RegraFiscalSaida],
) -> dict[str, Any]:
    """Comparativo de textos no cabeçalho da NF-e (sem alterar banco)."""
    regras_unicas: list[RegraFiscalSaida] = []
    vistos: set[int] = set()
    for r in regras:
        if r.pk not in vistos:
            vistos.add(r.pk)
            regras_unicas.append(r)

    alteracoes: list[dict[str, str]] = []
    recomendacoes: list[dict[str, str]] = []
    origens_texto: list[str] = []

    for campo_regra, campo_nf in MAPEAMENTO_TEXTO_REGRA_NF:
        sugestao = _combinar_textos_de_regras(regras_unicas, campo_regra)
        if not sugestao:
            continue
        atual = _text(getattr(nf, campo_nf, ''))
        depois, mudou = mesclar_texto_campo(atual, sugestao)
        if mudou:
            alteracoes.append(
                {
                    'campo': campo_nf,
                    'label': CAMPOS_TEXTO_NF_LABEL[campo_nf],
                    'antes': atual or '—',
                    'depois': depois,
                    'origem': ', '.join(_nome_regra(r) for r in regras_unicas if _text(getattr(r, campo_regra, ''))),
                },
            )
            for r in regras_unicas:
                if _text(getattr(r, campo_regra, '')):
                    o = _nome_regra(r)
                    if o not in origens_texto:
                        origens_texto.append(o)

    for regra in regras_unicas:
        recomendacoes.extend(extrair_recomendacoes_regra(regra))

    # dedupe recomendacoes por codigo+origem
    rec_vistos: set[tuple[str, str]] = set()
    rec_unicas: list[dict[str, str]] = []
    for rec in recomendacoes:
        chave = (rec['codigo'], rec['origem'])
        if chave in rec_vistos:
            continue
        rec_vistos.add(chave)
        rec_unicas.append(rec)

    return {
        'alteracoes': alteracoes,
        'recomendacoes': rec_unicas,
        'origens': origens_texto,
    }


def aplicar_textos_fiscais_nf(nf: NFeSaida, regras: list[RegraFiscalSaida]) -> tuple[dict[str, str], int, int]:
    """
    Aplica textos no cabeçalho da NF-e. Retorna (campos_alterados, qtd_textos, qtd_recomendacoes_itens).
    """
    preview_txt = calcular_textos_fiscais_preview(nf, regras)
    campos_alterados: dict[str, str] = {}
    for alt in preview_txt['alteracoes']:
        campo = alt['campo']
        setattr(nf, campo, alt['depois'])
        campos_alterados[campo] = alt['depois']

    return campos_alterados, len(preview_txt['alteracoes']), len(preview_txt['recomendacoes'])
