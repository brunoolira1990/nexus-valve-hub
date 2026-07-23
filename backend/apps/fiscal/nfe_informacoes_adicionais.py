"""Composição idempotente de informações adicionais / infCpl da NF-e Saída.

Regra: textos idênticos (após normalização) aparecem uma vez, preservando a
primeira ocorrência e a estrutura de parágrafos do texto original.

- Linha em branco separa informações complementares distintas.
- Quebra simples (soft wrap) permanece no mesmo parágrafo (colapsada em espaço).
- Sem fuzzy matching / substring.
"""

from __future__ import annotations

import re
import unicodedata

MARCADOR_OBS_FISCAIS_REGRA = '--- Observações fiscais da regra ---'
SEPARADOR_OBS_REGRA = f'\n\n{MARCADOR_OBS_FISCAIS_REGRA}\n'


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def normalizar_espacos_linha(texto: str) -> str:
    """Colapsa espaços consecutivos e remove bordas."""
    return re.sub(r'\s+', ' ', _text(texto))


def chave_deduplicacao_texto(texto: str) -> str:
    """
    Chave de comparação para duplicidade.

    Normaliza:
    - espaços no início/fim;
    - quebras de linha equivalentes (colapsadas);
    - espaços consecutivos;
    - casefold + remoção de acentos (somente na chave).

    Sem aproximação semântica nem substring matching.
    """
    t = unicodedata.normalize('NFKD', texto or '')
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t.casefold().strip())
    return t


def _eh_marcador_separador(texto: str) -> bool:
    chave = chave_deduplicacao_texto(texto)
    return 'observacoes fiscais da regra' in chave


def dividir_paragrafos_em_linhas(texto: str) -> list[list[str]]:
    """
    Separa o texto em parágrafos pela linha em branco.

    Cada parágrafo é a lista de linhas não vazias (soft wraps) na ordem original.
    """
    if not texto:
        return []
    normalizado = (texto or '').replace('\r\n', '\n').replace('\r', '\n')
    paragrafos: list[list[str]] = []
    atual: list[str] = []
    for segmento in normalizado.split('\n'):
        linha = normalizar_espacos_linha(segmento)
        if not linha:
            if atual:
                paragrafos.append(atual)
                atual = []
            continue
        atual.append(linha)
    if atual:
        paragrafos.append(atual)
    return paragrafos


def _juntar_linhas_paragrafo(linhas: list[str]) -> str:
    """Continuações de linha do mesmo parágrafo viram um único texto contínuo."""
    return normalizar_espacos_linha(' '.join(linhas))


# Palavras finais que indicam soft wrap / continuação (não fim de cláusula).
# Evitar artigos soltos (a/o) — quebrariam títulos como "NCM A".
_CONTINUACOES_SOFT_WRAP = frozenset({
    'mediante', 'conforme', 'segundo', 'perante', 'durante',
    'de', 'do', 'da', 'dos', 'das', 'com', 'sem', 'por', 'para',
    'em', 'no', 'na', 'nos', 'nas', 'e', 'ou', 'sob', 'sobre', 'entre',
    'apos', 'após', 'ate', 'até', 'pelo', 'pela', 'pelos', 'pelas',
})


def _ultima_palavra_normalizada(texto: str) -> str:
    t = normalizar_espacos_linha(texto)
    if not t:
        return ''
    ultima = t.split()[-1]
    return re.sub(r'[^\w]+', '', ultima, flags=re.UNICODE).casefold()


def _paragrafo_parece_continuacao(prev: str) -> bool:
    """True se o parágrafo anterior parece ter sido cortado no meio da cláusula."""
    t = normalizar_espacos_linha(prev)
    if not t:
        return False
    if t[-1] in '.!?;:':
        return False
    return _ultima_palavra_normalizada(t) in _CONTINUACOES_SOFT_WRAP


def _fundir_soft_wraps_com_linha_vazia_indevida(paragrafos: list[list[str]]) -> list[list[str]]:
    """
    Reata soft wraps que foram indevidamente separados por linha em branco
    (ex.: "... MEDIANTE\\n\\nCOMUNICAÇÃO ...").
    """
    if not paragrafos:
        return []
    out: list[list[str]] = [list(paragrafos[0])]
    for para in paragrafos[1:]:
        if out and _paragrafo_parece_continuacao(_juntar_linhas_paragrafo(out[-1])):
            out[-1].extend(para)
        else:
            out.append(list(para))
    return out


def dividir_blocos_texto(texto: str) -> list[str]:
    """
    Divide em blocos por parágrafo (linha em branco).

    Soft wraps dentro do parágrafo são colapsados em um único bloco contínuo.
    Também reata continuações que chegaram com linha vazia indevida após palavras
    como MEDIANTE/DE/COM/conforme.
    """
    brutos = dividir_paragrafos_em_linhas(texto)
    fundidos = _fundir_soft_wraps_com_linha_vazia_indevida(brutos)
    out: list[str] = []
    for linhas in fundidos:
        filtradas = [ln for ln in linhas if not _eh_marcador_separador(ln)]
        if not filtradas:
            continue
        out.append(_juntar_linhas_paragrafo(filtradas))
    return out


def deduplicar_blocos_texto(blocos: list[str]) -> list[str]:
    """Remove blocos idênticos após normalização; preserva primeira ocorrência e ordem."""
    vistos: set[str] = set()
    out: list[str] = []
    for raw in blocos:
        t = normalizar_espacos_linha(raw)
        if not t or _eh_marcador_separador(t):
            continue
        chave = chave_deduplicacao_texto(t)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        out.append(t)
    return out


def deduplicar_texto_informacoes_adicionais(texto: str) -> str:
    """
    Recompõe o texto sem duplicatas, preservando parágrafos.

    Soft wraps (quebra simples) são colapsados em espaço dentro do parágrafo.
    Linha em branco separa informações distintas. Deduplicação é por parágrafo
    contínuo resultante (sem fuzzy).
    """
    return '\n\n'.join(deduplicar_blocos_texto(dividir_blocos_texto(texto)))


def mesclar_textos_informacoes_adicionais(
    atual: str,
    novo: str,
    *,
    separador: str = SEPARADOR_OBS_REGRA,
) -> tuple[str, bool]:
    """
    Mescla `novo` em `atual` sem reintroduzir linhas/parágrafos já presentes.

    - Deduplica o conteúdo atual (limpa rascunhos já duplicados).
    - Concatena e deduplica com o novo texto, preservando a ordem do atual.
    - Se houver parágrafos realmente novos, insere o separador da regra.
    """
    atual_bruto = (atual or '').strip()
    novo_bruto = (novo or '').strip()
    atual_limpo = deduplicar_texto_informacoes_adicionais(atual_bruto)

    if not novo_bruto:
        return atual_limpo, atual_limpo != atual_bruto

    if not atual_limpo:
        resultado = deduplicar_texto_informacoes_adicionais(novo_bruto)
        return resultado, bool(resultado)

    combinado = deduplicar_texto_informacoes_adicionais(f'{atual_limpo}\n\n{novo_bruto}')
    if combinado == atual_limpo:
        return atual_limpo, atual_limpo != atual_bruto

    paras_atual = dividir_blocos_texto(atual_limpo)
    paras_comb = dividir_blocos_texto(combinado)
    if (
        len(paras_comb) > len(paras_atual)
        and paras_comb[: len(paras_atual)] == paras_atual
    ):
        novos = paras_comb[len(paras_atual) :]
        return atual_limpo + separador + '\n\n'.join(novos), True

    return combinado, True
