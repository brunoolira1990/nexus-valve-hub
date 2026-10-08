"""Parser robusto do retorno status_servico (retConsStatServ / SOAP / PyNFe)."""

from __future__ import annotations

import logging
import re
from typing import Any

from lxml import etree

logger = logging.getLogger(__name__)

CSTAT_SERVICO_OK = frozenset({'107', '108'})

TIPO_ERRO_PARSE = 'PARSE_ERROR'
TIPO_ERRO_PYNFE = 'PYNFE_ERROR'
TIPO_ERRO_RESPOSTA_VAZIA = 'RESPOSTA_VAZIA'
TIPO_ERRO_CONEXAO = 'CONEXAO_ERROR'

_RE_HTML = re.compile(r'(?i)<!DOCTYPE\s+html|<html[\s>]')


def parece_resposta_html(texto: str) -> bool:
    return bool(texto and _RE_HTML.search(texto))


def extrair_diagnostico_http_resposta(raw: Any) -> dict[str, str]:
    """Metadados seguros da resposta HTTP (sem corpo sensível)."""
    diag: dict[str, str] = {
        'http_status': '',
        'content_type': '',
        'html_titulo': '',
    }
    status = getattr(raw, 'status_code', None)
    if status is not None:
        diag['http_status'] = str(status)

    headers = getattr(raw, 'headers', None)
    if headers is not None:
        ct = headers.get('Content-Type') or headers.get('content-type')
        if ct:
            diag['content_type'] = str(ct).split(';')[0].strip()

    corpo = normalizar_xml_bruto(raw)
    if parece_resposta_html(corpo):
        titulo = re.search(r'(?is)<title[^>]*>(.*?)</title>', corpo)
        if titulo:
            diag['html_titulo'] = re.sub(r'\s+', ' ', titulo.group(1)).strip()[:120]
    return diag


def motivo_resposta_html_sefaz(
    *,
    uf: str,
    ambiente: str,
    empresa: str = '',
    endpoint: str = '',
    diagnostico_http: dict[str, str] | None = None,
) -> str:
    empresa_part = f', empresa: {empresa}' if empresa else ''
    endpoint_part = f' Endpoint: {endpoint}.' if endpoint else ''
    diag_part = ''
    if diagnostico_http:
        partes = []
        if diagnostico_http.get('http_status'):
            partes.append(f'HTTP {diagnostico_http["http_status"]}')
        if diagnostico_http.get('content_type'):
            partes.append(f'Content-Type: {diagnostico_http["content_type"]}')
        if diagnostico_http.get('html_titulo'):
            partes.append(f'título HTML: {diagnostico_http["html_titulo"]}')
        if partes:
            diag_part = f' ({"; ".join(partes)}).'
    return (
        f'Resposta HTML recebida — não é XML SEFAZ '
        f'(ambiente: {ambiente}, UF: {uf}{empresa_part}).{endpoint_part}{diag_part} '
        'Verifique endpoint SEFAZ, certificado A1, rede, proxy ou firewall.'
    )


def _tipo_resposta_bruto(raw: Any) -> str:
    if raw is None:
        return 'None'
    if isinstance(raw, bytes):
        return 'bytes'
    if isinstance(raw, str):
        return 'str'
    if isinstance(raw, tuple):
        return f'tuple(len={len(raw)})'
    if isinstance(raw, dict):
        return 'dict'
    if etree.iselement(raw):
        return f'lxml.{type(raw).__name__}'
    cls = type(raw).__name__
    module = type(raw).__module__ or ''
    if 'ElementTree' in module or cls == 'Element':
        return 'ElementTree.Element'
    if hasattr(raw, 'text') and hasattr(raw, 'content'):
        return f'requests-like.{cls}'
    return f'{module}.{cls}' if module else cls


def _preview_seguro(texto: str, limite: int = 500) -> str:
    if not texto:
        return ''
    t = texto.replace('\x00', '')
    t = re.sub(r'(?i)(senha|password|privateKey|pfx|certificate)[^\n<]{0,80}', '[redacted]', t)
    return t[:limite]


def log_diagnostico_resposta(raw: Any, *, contexto: str = 'status_servico') -> None:
    """Logs seguros apenas em DEBUG — sem senha/PFX/chave."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    tipo = _tipo_resposta_bruto(raw)
    try:
        xml = normalizar_xml_bruto(raw)
    except Exception as exc:
        logger.debug(
            '%s: tipo=%s falha_normalizar=%s: %s',
            contexto,
            tipo,
            type(exc).__name__,
            exc,
        )
        return
    logger.debug(
        '%s: tipo=%s tamanho=%s preview=%s',
        contexto,
        tipo,
        len(xml),
        _preview_seguro(xml),
    )


def normalizar_xml_bruto(raw: Any) -> str:
    """Converte qualquer retorno PyNFe/HTTP/XML em string XML/texto."""
    if raw is None:
        return ''

    if isinstance(raw, bytes):
        return raw.decode('utf-8', errors='replace').strip()

    if isinstance(raw, str):
        return raw.strip()

    if isinstance(raw, tuple):
        for item in raw:
            txt = normalizar_xml_bruto(item)
            if txt:
                return txt
        return ''

    if isinstance(raw, dict):
        for key in ('xml', 'text', 'content', 'body', 'data', 'response'):
            if key in raw and raw[key] is not None:
                return normalizar_xml_bruto(raw[key])
        return str(raw)

    if etree.iselement(raw):
        return etree.tostring(raw, encoding='unicode')

    try:
        from xml.etree import ElementTree as ET

        if isinstance(raw, ET.Element):
            return ET.tostring(raw, encoding='unicode')
    except Exception:
        pass

    texto_http = getattr(raw, 'text', None)
    content_http = getattr(raw, 'content', None)
    if texto_http is not None or content_http is not None:
        texto = str(texto_http or '').strip()
        if isinstance(content_http, bytes):
            conteudo = content_http.decode('utf-8', errors='replace').strip()
        elif content_http is not None:
            conteudo = str(content_http).strip()
        else:
            conteudo = ''
        if texto and parece_resposta_html(texto) and conteudo and not parece_resposta_html(conteudo):
            return conteudo
        if texto:
            return texto
        if conteudo:
            return conteudo

    for attr in ('xml', 'body', 'data'):
        val = getattr(raw, attr, None)
        if val is not None and not callable(val):
            if isinstance(val, bytes):
                return val.decode('utf-8', errors='replace').strip()
            if isinstance(val, str) and val.strip():
                return val.strip()

    s = str(raw).strip()
    if s.startswith('<') or 'cStat' in s or 'retConsStatServ' in s:
        return s
    return s


def _extrair_local_name_xpath(root: etree._Element, local_name: str) -> str | None:
    found = root.xpath(f'//*[local-name()="{local_name}"]/text()')
    if not found:
        return None
    val = str(found[0]).strip()
    return val or None


def _parse_xml_element(root: etree._Element) -> dict[str, str | None]:
    versao = root.get('versao')
    if not versao:
        vers_el = root.xpath('//*[local-name()="retConsStatServ"]')
        if vers_el:
            versao = vers_el[0].get('versao')

    return {
        'c_stat': _extrair_local_name_xpath(root, 'cStat'),
        'x_motivo': _extrair_local_name_xpath(root, 'xMotivo'),
        'tp_amb': _extrair_local_name_xpath(root, 'tpAmb'),
        'ver_aplic': _extrair_local_name_xpath(root, 'verAplic'),
        'c_uf': _extrair_local_name_xpath(root, 'cUF'),
        'dh_recbto': _extrair_local_name_xpath(root, 'dhRecbto'),
        't_med': _extrair_local_name_xpath(root, 'tMed'),
        'versao': versao,
    }


def parse_status_servico_response(raw_response: Any) -> dict[str, Any]:
    """
    Extrai campos do retConsStatServ a partir de qualquer formato de retorno PyNFe/SEFAZ.

    Retorno dict com chaves: ok, c_stat, x_motivo, tp_amb, ver_aplic, c_uf, dh_recbto, t_med,
    versao, xml_raw, erro_parse, motivo_erro, tipo_resposta, servico_operacional.
    """
    tipo_resposta = _tipo_resposta_bruto(raw_response)
    log_diagnostico_resposta(raw_response)

    xml_raw = normalizar_xml_bruto(raw_response)

    base: dict[str, Any] = {
        'ok': False,
        'c_stat': '',
        'x_motivo': '',
        'tp_amb': '',
        'ver_aplic': '',
        'c_uf': '',
        'dh_recbto': '',
        't_med': '',
        'versao': '',
        'xml_raw': xml_raw,
        'erro_parse': False,
        'motivo_erro': '',
        'tipo_resposta': tipo_resposta,
        'servico_operacional': False,
    }

    if not xml_raw:
        base['erro_parse'] = True
        base['motivo_erro'] = 'PyNFe retornou resposta vazia.'
        return base

    if parece_resposta_html(xml_raw):
        base['erro_parse'] = True
        base['motivo_erro'] = 'Resposta HTML recebida (não é XML SEFAZ).'
        base['x_motivo'] = base['motivo_erro']
        base['resposta_html'] = True
        return base

    try:
        root = etree.fromstring(xml_raw.encode('utf-8'))
    except Exception as exc:
        base['erro_parse'] = True
        base['motivo_erro'] = f'Erro de parsing XML: {exc}'
        base['x_motivo'] = base['motivo_erro']
        return base

    campos = _parse_xml_element(root)
    c_stat = (campos.get('c_stat') or '').strip()
    x_motivo = (campos.get('x_motivo') or '').strip()

    base.update(
        {
            'c_stat': c_stat,
            'x_motivo': x_motivo,
            'tp_amb': (campos.get('tp_amb') or '').strip(),
            'ver_aplic': (campos.get('ver_aplic') or '').strip(),
            'c_uf': (campos.get('c_uf') or '').strip(),
            'dh_recbto': (campos.get('dh_recbto') or '').strip(),
            't_med': (campos.get('t_med') or '').strip(),
            'versao': (campos.get('versao') or '').strip(),
        },
    )

    if not c_stat and not x_motivo:
        base['erro_parse'] = True
        base['motivo_erro'] = 'Resposta recebida, mas cStat/xMotivo não foram encontrados.'
        base['x_motivo'] = base['motivo_erro']
        return base

    if not c_stat:
        base['erro_parse'] = True
        base['motivo_erro'] = 'Resposta recebida, mas cStat não foi encontrado.'
        if not base['x_motivo']:
            base['x_motivo'] = base['motivo_erro']
        return base

    base['servico_operacional'] = c_stat in CSTAT_SERVICO_OK
    base['ok'] = base['servico_operacional']
    if not x_motivo:
        base['x_motivo'] = 'Retorno SEFAZ sem descrição (xMotivo).'
    return base
