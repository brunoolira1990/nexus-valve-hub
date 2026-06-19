"""Busca de produtos por múltiplos termos (autocomplete comercial)."""

from __future__ import annotations

import re

from django.db.models import CharField, Q, QuerySet, Value
from django.db.models.functions import Coalesce, Concat, Lower, Replace

from apps.produtos.descricao_normalizacao import remover_acentos
from apps.produtos.models import Produto

_CAMPOS_BUSCA = (
    'codigo_completo',
    'descricao',
    'material',
    'norma',
    'ncm',
    'figura',
    'sufixo',
    'schedule',
    'polegada_principal',
    'polegada_secundaria',
    'tipo_peca',
    'conexao',
    'familia__codigo_figura',
    'familia__descricao_base',
    'familia__ncm_padrao__codigo',
)

_ACENTOS_ORIGEM = 'áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ'
_ACENTOS_DESTINO = 'aaaaeeiooouucAAAAEEIOOOUUC'

_RE_FRACAO = re.compile(r'^(\d+(?:\s+\d+/\d+|\d/\d+))', re.IGNORECASE)


def normalizar_termo_busca(valor: str | None) -> str:
    return remover_acentos((valor or '').strip()).lower()


def tokenizar_busca_produto(termo: str | None) -> list[str]:
    termo = (termo or '').strip()
    if not termo:
        return []
    return [t for t in re.split(r'\s+', termo) if t]


def variantes_termo_busca(token: str) -> list[str]:
    """Variações simples do termo (polegada, aspas, POL)."""
    bruto = (token or '').strip()
    if not bruto:
        return []
    variantes: set[str] = {bruto}
    sem_pol = re.sub(r'\bpol(?:egadas?)?\.?\b', '', bruto, flags=re.IGNORECASE).strip()
    if sem_pol:
        variantes.add(sem_pol)
    sem_aspas = bruto.rstrip('"').rstrip('”').strip()
    if sem_aspas:
        variantes.add(sem_aspas)
        variantes.add(f'{sem_aspas}"')
    m = _RE_FRACAO.match(bruto)
    if m:
        frac = m.group(1).replace(' ', '-').strip()
        variantes.add(frac)
        variantes.add(frac.replace('-', ' '))
        variantes.add(f'{frac}"')
        variantes.add(f'{frac} POL')
    out: list[str] = []
    for v in variantes:
        norm = v.strip()
        if norm and norm not in out:
            out.append(norm)
    return out


def _strip_accents_expr(expr):
    resultado = Lower(expr)
    for orig, dest in zip(_ACENTOS_ORIGEM, _ACENTOS_DESTINO, strict=True):
        resultado = Replace(
            resultado,
            Value(orig),
            Value(dest),
            output_field=CharField(),
        )
    return resultado


def _valor_campo_produto(obj: Produto, campo: str) -> str:
    atual: object = obj
    for parte in campo.split('__'):
        atual = getattr(atual, parte, None) if atual is not None else None
    return str(atual or '').strip()


def produto_texto_busca_normalizado(obj: Produto) -> str:
    partes = [_valor_campo_produto(obj, campo) for campo in _CAMPOS_BUSCA]
    return normalizar_termo_busca(' '.join(p for p in partes if p))


def produto_atende_tokens(obj: Produto, tokens: list[str]) -> bool:
    if not tokens:
        return True
    blob = produto_texto_busca_normalizado(obj)
    for token in tokens:
        variantes = [normalizar_termo_busca(v) for v in variantes_termo_busca(token)]
        variantes = [v for v in variantes if v]
        if not variantes:
            return False
        if not any(v in blob for v in variantes):
            return False
    return True


def _annotate_busca_norm(qs: QuerySet) -> QuerySet:
    partes_expr = []
    for idx, campo in enumerate(_CAMPOS_BUSCA):
        partes_expr.append(Coalesce(campo, Value(''), output_field=CharField()))
        if idx < len(_CAMPOS_BUSCA) - 1:
            partes_expr.append(Value(' ', output_field=CharField()))
    blob = Concat(*partes_expr, output_field=CharField())
    return qs.annotate(_busca_norm=_strip_accents_expr(blob))


def aplicar_filtro_busca_produto(qs: QuerySet, termo: str | None) -> QuerySet:
    termo = (termo or '').strip()
    if not termo:
        return qs
    tokens = tokenizar_busca_produto(termo)
    if not tokens:
        return qs
    qs = _annotate_busca_norm(qs)
    for token in tokens:
        q_token = Q()
        for variant in variantes_termo_busca(token):
            norm = normalizar_termo_busca(variant)
            if norm:
                q_token |= Q(_busca_norm__contains=norm)
        if q_token:
            qs = qs.filter(q_token)
    return qs


def produto_busca_rank(termo: str, obj: Produto) -> tuple[int, int, int, str]:
    """Menor tupla = melhor posição no autocomplete."""
    tokens = tokenizar_busca_produto(termo)
    blob = produto_texto_busca_normalizado(obj)
    cc = normalizar_termo_busca(obj.codigo_completo or '')
    termo_norm = normalizar_termo_busca(termo)

    if termo_norm and cc == termo_norm:
        return (0, 0, 0, cc)
    if len(tokens) == 1:
        token_norm = normalizar_termo_busca(tokens[0])
        if cc == token_norm:
            return (0, 1, 0, cc)
        if cc.startswith(token_norm):
            return (1, 0, 0, cc)

    dsc = normalizar_termo_busca(obj.descricao or '')
    if termo_norm and dsc.startswith(termo_norm):
        return (2, 0, 0, cc)

    matches = 0
    for token in tokens:
        vars_norm = [normalizar_termo_busca(v) for v in variantes_termo_busca(token)]
        if any(v and v in blob for v in vars_norm):
            matches += 1

    first = normalizar_termo_busca(tokens[0]) if tokens else ''
    starts_desc = 0 if first and dsc.startswith(first) else 1
    missing = len(tokens) - matches
    return (3, missing, starts_desc, cc)
