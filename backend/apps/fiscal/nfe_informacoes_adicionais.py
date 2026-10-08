"""Composição idempotente de informações adicionais / infCpl da NF-e Saída.

Regra: textos idênticos (após normalização) aparecem uma vez, preservando a
primeira ocorrência e a estrutura de unidades do texto original.

Uma informação de negócio = um bloco/parágrafo. Uma cláusula comercial com
várias frases permanece em um único parágrafo (pontos finais internos não
separam blocos).

Separação permitida:
- linha em branco explícita;
- início confirmado de outra unidade conhecida (BASE DE CÁLCULO, PEDIDO…);
- unidades coladas na mesma linha após `.!?` + início conhecido.

Soft wrap simples → espaço. Entre blocos distintos → ``\\n\\n``.
Sem fuzzy matching.
"""

from __future__ import annotations

import re
import unicodedata

MARCADOR_OBS_FISCAIS_REGRA = '--- Observações fiscais da regra ---'
SEPARADOR_OBS_REGRA = f'\n\n{MARCADOR_OBS_FISCAIS_REGRA}\n'

# Inícios de unidade informativa independente (não frases internas da cláusula).
_INICIOS_UNIDADE_INFO = (
    r'n[ãa]o\s+aceitaremos',
    r'base\s+de\s+c[aá]lculo',
    r'pedido\s+de\s+compra',
    r'fundamento\s+fiscal',
    r'endere[cç]o\s+de\s+entrega',
    r'hor[aá]rio\s+de\s+entrega',
)
_RE_INICIO_UNIDADE = re.compile(
    r'^(?:' + '|'.join(_INICIOS_UNIDADE_INFO) + r')\b',
    re.IGNORECASE,
)
_RE_SEPARAR_UNIDADES = re.compile(
    r'(?<=[.!?])\s+(?=(?:' + '|'.join(_INICIOS_UNIDADE_INFO) + r')\b)',
    re.IGNORECASE,
)


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def normalizar_espacos_linha(texto: str) -> str:
    """Colapsa espaços consecutivos e remove bordas."""
    return re.sub(r'\s+', ' ', _text(texto))


def chave_deduplicacao_texto(texto: str) -> str:
    """
    Chave de comparação para duplicidade.

    Normaliza (somente na chave):
    - espaços / quebras;
    - casefold + remoção de acentos;
    - pontos de abreviação no meio do token (R.ICMS ↔ RICMS).

    Sem aproximação semântica nem substring matching.
    """
    t = unicodedata.normalize('NFKD', texto or '')
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t.casefold().strip())
    # R.ICMS/SP ≡ RICMS/SP (não altera o texto exibido).
    t = re.sub(r'(?<=[a-z0-9])\.(?=[a-z0-9])', '', t)
    return t


def _eh_marcador_separador(texto: str) -> bool:
    chave = chave_deduplicacao_texto(texto)
    return 'observacoes fiscais da regra' in chave


def _linha_inicia_unidade_conhecida(linha: str) -> bool:
    """True se a linha começa com unidade informativa independente."""
    return bool(_RE_INICIO_UNIDADE.match(normalizar_espacos_linha(linha)))


def dividir_paragrafos_em_linhas(texto: str) -> list[list[str]]:
    """
    Separa o texto em parágrafos.

    Fronteiras:
    - linha em branco;
    - linha que inicia outra unidade conhecida (ex.: ``\\nBASE DE CÁLCULO...``).

    Soft wraps no meio da mesma unidade (ex.: após MEDIANTE, ou entre frases
    da cláusula comercial) permanecem no mesmo parágrafo.
    Pontos finais internos NÃO abrem bloco novo por si só.
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
        if atual and _linha_inicia_unidade_conhecida(linha):
            paragrafos.append(atual)
            atual = [linha]
            continue
        atual.append(linha)
    if atual:
        paragrafos.append(atual)
    return paragrafos


def _juntar_linhas_paragrafo(linhas: list[str]) -> str:
    """Continuações de linha do mesmo parágrafo viram um único texto contínuo."""
    return normalizar_espacos_linha(' '.join(linhas))


def _separar_unidades_coladas(texto: str) -> list[str]:
    """
    Separa unidades informativas distintas coladas na mesma linha.

    Ex.: "... ICMS 52/91. NÃO ACEITAREMOS DEVOLUÇÃO..." → dois blocos.
    Não parte a cláusula em "COMERCIAL. NOSSOS PRODUTOS..." (NOSSOS não é
    início de unidade conhecida).
    """
    t = normalizar_espacos_linha(texto)
    if not t:
        return []
    partes = [normalizar_espacos_linha(p) for p in _RE_SEPARAR_UNIDADES.split(t)]
    return [p for p in partes if p]


# Palavras finais que indicam soft wrap / continuação (não fim de cláusula).
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
    Divide em unidades informativas independentes.

    1) Parágrafos por linha em branco / início de unidade conhecida;
    2) Soft wraps colapsados em espaço;
    3) Unidades coladas na mesma linha (fundamento + cláusula) separadas;
    4) Marcador de regra descartado.
    """
    brutos = dividir_paragrafos_em_linhas(texto)
    fundidos = _fundir_soft_wraps_com_linha_vazia_indevida(brutos)
    out: list[str] = []
    for linhas in fundidos:
        filtradas = [ln for ln in linhas if not _eh_marcador_separador(ln)]
        if not filtradas:
            continue
        paragrafo = _juntar_linhas_paragrafo(filtradas)
        for unidade in _separar_unidades_coladas(paragrafo):
            if unidade and not _eh_marcador_separador(unidade):
                out.append(unidade)
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
    Recompõe o texto sem duplicatas, preservando unidades/parágrafos.

    Soft wraps viram espaço; ``\\n\\n`` separa blocos distintos.
    Deduplicação por unidade contínua (sem fuzzy).
    """
    return '\n\n'.join(deduplicar_blocos_texto(dividir_blocos_texto(texto)))


def mesclar_textos_informacoes_adicionais(
    atual: str,
    novo: str,
    *,
    separador: str = SEPARADOR_OBS_REGRA,
) -> tuple[str, bool]:
    """
    Mescla `novo` em `atual` sem reintroduzir unidades já presentes.

    - Deduplica o conteúdo atual (limpa rascunhos já duplicados).
    - Concatena e deduplica com o novo texto, preservando a ordem do atual.
    - Se houver unidades realmente novas, insere o separador da regra.
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
