"""Compactação de XML NF-e — evita rejeição SEFAZ cStat 588 (caracteres de edição)."""

from __future__ import annotations

import re
from typing import Any

BOM_UTF8 = b'\xef\xbb\xbf'
XML_DECLARACAO = '<?xml version="1.0" encoding="UTF-8"?>'
MSG_CSTAT_588 = (
    'XML contém caracteres de edição entre tags ou no início/fim da mensagem. '
    'Compacte o XML antes de transmitir.'
)

# Whitespace entre tags (não dentro do conteúdo textual de um elemento)
_RE_ENTRE_TAGS = re.compile(rb'>\s+<')
_RE_ENTRE_TAGS_NL = re.compile(rb'>\s*[\r\n]+\s*<')
_RE_ENTRE_TAGS_TAB = re.compile(rb'>\s*\t+\s*<')


def remover_bom(data: bytes) -> bytes:
    if data.startswith(BOM_UTF8):
        return data[len(BOM_UTF8) :]
    return data


def _as_bytes(xml: bytes | str) -> bytes:
    if isinstance(xml, bytes):
        return xml
    return xml.encode('utf-8')


def _corpo_sem_declaracao(data: bytes) -> bytes:
    data = remover_bom(data).lstrip()
    if data.startswith(b'<?xml'):
        idx = data.find(b'?>')
        if idx != -1:
            return data[idx + 2 :].lstrip()
    return data


def debug_xml_bytes(xml: bytes | str) -> dict[str, Any]:
    """Diagnóstico de bytes do XML (BOM, whitespace entre tags, etc.)."""
    raw = _as_bytes(xml)
    com_bom = raw.startswith(BOM_UTF8)
    sem_bom = remover_bom(raw)
    corpo = _corpo_sem_declaracao(raw)

    leading_ws = len(sem_bom) > len(sem_bom.lstrip())
    trailing_ws = len(sem_bom.rstrip()) < len(sem_bom)

    return {
        'tamanho': len(raw),
        'primeiros_50_bytes': repr(raw[:50]),
        'ultimos_50_bytes': repr(raw[-50:]),
        'contem_bom': com_bom,
        'leading_whitespace_antes_primeira_tag': leading_ws,
        'trailing_whitespace_apos_ultima_tag': trailing_ws,
        'quebras_entre_tags': bool(_RE_ENTRE_TAGS_NL.search(corpo)),
        'tabs_entre_tags': bool(_RE_ENTRE_TAGS_TAB.search(corpo)),
        'whitespace_entre_tags': bool(_RE_ENTRE_TAGS.search(corpo)),
    }


def tem_caracteres_edicao(xml: bytes | str) -> bool:
    raw = _as_bytes(xml)
    if raw.startswith(BOM_UTF8):
        return True
    sem_bom = remover_bom(raw)
    if len(sem_bom) > len(sem_bom.lstrip()):
        return True
    if len(sem_bom.rstrip()) < len(sem_bom):
        return True
    corpo = _corpo_sem_declaracao(raw)
    if _RE_ENTRE_TAGS.search(corpo):
        return True
    return False


def validar_xml_sem_caracteres_edicao(xml: bytes | str) -> dict[str, Any]:
    """Falha se houver BOM, whitespace nas bordas ou entre tags."""
    diag = debug_xml_bytes(xml)
    erros: list[dict[str, Any]] = []
    if diag['contem_bom']:
        erros.append({'codigo': 'BOM', 'mensagem': 'XML contém BOM UTF-8 no início.'})
    if diag['leading_whitespace_antes_primeira_tag']:
        erros.append({'codigo': 'LEADING_WS', 'mensagem': 'Whitespace antes da primeira tag.'})
    if diag['trailing_whitespace_apos_ultima_tag']:
        erros.append({'codigo': 'TRAILING_WS', 'mensagem': 'Whitespace após a última tag.'})
    if diag['quebras_entre_tags']:
        erros.append({'codigo': 'NL_ENTRE_TAGS', 'mensagem': 'Quebra de linha entre tags (>\\n<).'})
    if diag['tabs_entre_tags']:
        erros.append({'codigo': 'TAB_ENTRE_TAGS', 'mensagem': 'Tab entre tags (>\\t<).'})
    elif diag['whitespace_entre_tags']:
        erros.append({'codigo': 'WS_ENTRE_TAGS', 'mensagem': 'Espaços/whitespace entre tags.'})
    return {
        'ok': not erros,
        'mensagem': '' if not erros else MSG_CSTAT_588,
        'erros': erros,
        'diagnostico': diag,
    }


def serializar_elemento_compacto(element, *, com_declaracao: bool = True) -> bytes:
    """Serializa elemento lxml sem indentação (pretty_print=False)."""
    from lxml import etree

    body = etree.tostring(
        element,
        encoding='UTF-8',
        xml_declaration=False,
        pretty_print=False,
        method='xml',
    )
    if com_declaracao:
        return XML_DECLARACAO.encode('utf-8') + body
    return body


def normalizar_xml_para_assinatura_nfe(xml: bytes | str) -> bytes:
    """
    Remove BOM, whitespace entre tags e indentação antes da assinatura.
    Usa remove_blank_text apenas na fase pré-assinatura (não altera textos em infCpl).
    """
    from lxml import etree

    data = remover_bom(_as_bytes(xml))
    corpo = _corpo_sem_declaracao(data).decode('utf-8')
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(corpo.encode('utf-8'), parser=parser)
    return serializar_elemento_compacto(root, com_declaracao=True)


def compactar_xml_serializado(xml: bytes | str, *, com_declaracao: bool = True) -> bytes:
    """
    Re-serializa XML já montado/assinado sem pretty_print e sem remover nós de texto assinados.
    Não reconstrói infNFe/Signature — apenas compacta a serialização.
    """
    from lxml import etree

    data = remover_bom(_as_bytes(xml))
    corpo = _corpo_sem_declaracao(data)
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(corpo, parser=parser)
    return serializar_elemento_compacto(root, com_declaracao=com_declaracao)


def extrair_elemento_nfe(xml: bytes | str):
    """Retorna elemento raiz NFe (sem declaração XML embutida)."""
    from lxml import etree

    from apps.fiscal.nfe_emissao.xml_serializacao import _local_tag, normalizar_xml_nfe

    data = remover_bom(_as_bytes(xml))
    corpo = _corpo_sem_declaracao(data)
    try:
        root = etree.fromstring(corpo)
    except etree.XMLSyntaxError:
        texto = normalizar_xml_nfe(corpo.decode('utf-8'))
        root = etree.fromstring(_corpo_sem_declaracao(texto.encode('utf-8')))
    if _local_tag(root.tag) == 'NFe':
        return root
    for child in root:
        if _local_tag(child.tag) == 'NFe':
            return child
    texto = normalizar_xml_nfe(corpo.decode('utf-8'))
    root = etree.fromstring(_corpo_sem_declaracao(texto.encode('utf-8')))
    if _local_tag(root.tag) == 'NFe':
        return root
    raise ValueError('Elemento NFe não encontrado no XML.')
