"""Serialização legível de erros XSD NF-e — emissão homologação/produção."""

from __future__ import annotations

from typing import Any


def _tag_do_elemento(elemento: str) -> str:
    texto = (elemento or '').strip().rstrip('/')
    if not texto:
        return ''
    ultimo = texto.split('/')[-1]
    if '}' in ultimo:
        return ultimo.split('}', 1)[-1]
    return ultimo


CONTEXT_LABELS = {
    'XML_ASSINADO': 'XML assinado',
    'ENVI_NFE': 'enviNFe',
    'XML_PRE': 'XML preliminar',
    'NFE': 'XML NF-e',
    'CARACTERES_EDICAO': 'Caracteres de edição',
}


def _label_contexto(contexto: str) -> str:
    ctx = (contexto or '').strip()
    if not ctx:
        return ''
    return CONTEXT_LABELS.get(ctx, ctx.replace('_', ' '))


def formatar_erro_xsd_legivel(erro: dict[str, Any]) -> str:
    """Mensagem única para operador/log a partir de um erro XSD estruturado."""
    contexto = _label_contexto(
        str(erro.get('contexto') or erro.get('tipo_xml') or erro.get('tipo') or '').strip(),
    )
    tag = _tag_do_elemento(str(erro.get('elemento') or ''))
    mensagem = str(erro.get('mensagem') or erro.get('message') or '').strip()
    linha = int(erro.get('linha') or 0)
    coluna = int(erro.get('coluna') or 0)

    partes: list[str] = []
    if contexto:
        partes.append(contexto)
    if tag:
        partes.append(f'Tag {tag}')
    if mensagem:
        partes.append(mensagem)
    if linha or coluna:
        loc = []
        if linha:
            loc.append(f'linha {linha}')
        if coluna:
            loc.append(f'coluna {coluna}')
        partes.append(f"({' · '.join(loc)})")

    if not partes:
        return mensagem or 'Erro XSD desconhecido.'
    if len(partes) <= 2:
        return ': '.join(partes)
    return f"{partes[0]}: {partes[1]} — {' '.join(partes[2:])}"


def normalizar_erro_xsd_bruto(erro: Any, *, contexto: str = '') -> dict[str, Any]:
    if isinstance(erro, dict):
        item = {k: v for k, v in erro.items() if v is not None}
    elif isinstance(erro, str):
        item = {'mensagem': erro.strip()}
    else:
        item = {'mensagem': str(erro).strip()}
    if contexto and not item.get('contexto'):
        item['contexto'] = contexto
    item.setdefault('linha', 0)
    item.setdefault('coluna', 0)
    item.setdefault('elemento', '')
    item.setdefault('mensagem', '')
    return item


def serializar_lista_erros_xsd(
    erros: list[Any],
    *,
    contexto_padrao: str = '',
) -> tuple[list[str], list[dict[str, Any]]]:
    erros_xsd: list[dict[str, Any]] = []
    erros_txt: list[str] = []
    for bruto in erros or []:
        item = normalizar_erro_xsd_bruto(bruto, contexto=contexto_padrao)
        erros_xsd.append(item)
        legivel = formatar_erro_xsd_legivel(item)
        if legivel and legivel not in erros_txt:
            erros_txt.append(legivel)
    return erros_txt, erros_xsd


def resumo_erros_xsd_log(erros: list[Any]) -> str:
    if not erros:
        return '-'
    textos: list[str] = []
    for bruto in erros[:3]:
        if isinstance(bruto, dict):
            textos.append(formatar_erro_xsd_legivel(bruto))
        else:
            textos.append(str(bruto))
    return ' | '.join(t for t in textos if t)


def preparar_erros_resposta_emissao(
    erros_raw: list[Any],
    *,
    validacao_xsd: dict[str, Any] | None = None,
    mensagem: str = '',
) -> dict[str, Any]:
    """
    Converte erros brutos (dict/str) em payload JSON legível para API/UI.
    Mantém validacao_xsd estruturada e adiciona erros_xsd + erros (strings).
    """
    contexto = str((validacao_xsd or {}).get('tipo') or '')
    erros_txt, erros_xsd = serializar_lista_erros_xsd(erros_raw, contexto_padrao=contexto)

    if not erros_txt and mensagem:
        erros_txt = [mensagem]

    mensagem_final = mensagem
    if erros_txt and mensagem and erros_txt[0] not in mensagem:
        mensagem_final = f'{mensagem} {erros_txt[0]}'.strip()
    elif erros_txt and not mensagem:
        mensagem_final = erros_txt[0]

    payload: dict[str, Any] = {
        'erros': erros_txt,
        'mensagem': mensagem_final,
    }
    if erros_xsd:
        payload['erros_xsd'] = erros_xsd
    if validacao_xsd:
        vx = dict(validacao_xsd)
        if erros_xsd and not vx.get('erros'):
            vx['erros'] = erros_xsd
        payload['validacao_xsd'] = vx
    payload['sefaz_transmitida'] = False
    return payload


def aplicar_erros_validacao_no_payload(
    payload: dict[str, Any],
    detalhes: dict[str, Any],
    *,
    mensagem: str,
) -> dict[str, Any]:
    """Enriquece resposta 422 de emissão com erros XSD legíveis."""
    erros_raw = detalhes.get('erros') or [mensagem]
    if not isinstance(erros_raw, list):
        erros_raw = [erros_raw]
    prep = preparar_erros_resposta_emissao(
        erros_raw,
        validacao_xsd=detalhes.get('validacao_xsd') if isinstance(detalhes.get('validacao_xsd'), dict) else None,
        mensagem=mensagem,
    )
    payload['mensagem'] = prep['mensagem']
    payload['erros'] = prep['erros']
    if prep.get('erros_xsd'):
        payload['erros_xsd'] = prep['erros_xsd']
    if prep.get('validacao_xsd'):
        payload['validacao_xsd'] = prep['validacao_xsd']
    payload['sefaz_transmitida'] = False
    return payload
