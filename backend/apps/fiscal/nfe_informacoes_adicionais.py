"""Composição idempotente de informações adicionais / infCpl da NF-e Saída.

Regra: textos idênticos (após normalização de espaços/quebras) aparecem uma vez,
preservando a primeira ocorrência e a ordem original. Sem fuzzy matching.
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

    Normaliza apenas:
    - espaços no início/fim;
    - quebras de linha equivalentes;
    - espaços consecutivos;
    - linhas vazias (já descartadas ao dividir).

    Casefold + remoção de acentos alinham a chave ao infCpl (maiúsculas) sem
    aproximação semântica nem substring matching.
    """
    t = unicodedata.normalize('NFKD', texto or '')
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t.casefold().strip())
    return t


def _eh_marcador_separador(texto: str) -> bool:
    chave = chave_deduplicacao_texto(texto)
    return 'observacoes fiscais da regra' in chave


def dividir_blocos_texto(texto: str) -> list[str]:
    """
    Divide o texto em blocos não vazios (linhas/parágrafos).

    Linhas vazias excedentes são descartadas. Cada linha não vazia é um bloco
    candidato à deduplicação, na ordem original.
    """
    if not texto:
        return []
    normalizado = (texto or '').replace('\r\n', '\n').replace('\r', '\n')
    blocos: list[str] = []
    for segmento in normalizado.split('\n'):
        linha = normalizar_espacos_linha(segmento)
        if not linha:
            continue
        blocos.append(linha)
    return blocos


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
    """Recompõe o texto sem blocos duplicados (join com parágrafo em branco)."""
    return '\n\n'.join(deduplicar_blocos_texto(dividir_blocos_texto(texto)))


def mesclar_textos_informacoes_adicionais(
    atual: str,
    novo: str,
    *,
    separador: str = SEPARADOR_OBS_REGRA,
) -> tuple[str, bool]:
    """
    Mescla `novo` em `atual` sem reintroduzir blocos já presentes.

    - Deduplica o conteúdo atual (limpa rascunhos já duplicados).
    - Acrescenta somente blocos de `novo` ainda ausentes.
    - Preserva a ordem original do texto atual e a ordem dos blocos novos.
    """
    atual_bruto = (atual or '').strip()
    novo_bruto = (novo or '').strip()
    atual_limpo = deduplicar_texto_informacoes_adicionais(atual_bruto)

    if not novo_bruto:
        return atual_limpo, atual_limpo != atual_bruto

    blocos_novo = deduplicar_blocos_texto(dividir_blocos_texto(novo_bruto))
    if not blocos_novo:
        return atual_limpo, atual_limpo != atual_bruto

    if not atual_limpo:
        resultado = '\n\n'.join(blocos_novo)
        return resultado, True

    chaves_atual = {
        chave_deduplicacao_texto(b)
        for b in dividir_blocos_texto(atual_limpo)
    }
    a_adicionar = [
        b for b in blocos_novo
        if chave_deduplicacao_texto(b) not in chaves_atual
    ]
    if not a_adicionar:
        return atual_limpo, atual_limpo != atual_bruto

    resultado = atual_limpo + separador + '\n\n'.join(a_adicionar)
    return resultado, True
