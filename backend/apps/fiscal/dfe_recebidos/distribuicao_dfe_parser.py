"""Parser do retorno SEFAZ NFeDistribuicaoDFe / CTeDistribuicaoDFe (retDistDFeInt)."""

from __future__ import annotations

import base64
import gzip
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from lxml import etree

from apps.fiscal.nfe_integracao.adapters.status_servico_parser import normalizar_xml_bruto

logger = logging.getLogger(__name__)

CSTAT_DOCUMENTOS_LOCALIZADOS = frozenset({'138'})
CSTAT_NENHUM_DOCUMENTO = frozenset({'137'})
CSTAT_CONSUMO_INDEVIDO = frozenset({'656'})

_SCHEMAS_NFE_COMPLETOS = frozenset({'procnfe', 'nfeproc'})
_SCHEMAS_CTE_COMPLETOS = frozenset({'proccte', 'cteproc'})


@dataclass
class DocumentoDistribuicao:
    nsu: str
    schema: str
    conteudo_xml: bytes
    tipo: str  # NFE | CTE | OUTRO


@dataclass
class ResultadoDistribuicaoDfe:
    sucesso_parse: bool = False
    cstat: str = ''
    xmotivo: str = ''
    ult_nsu: int = 0
    max_nsu: int = 0
    documentos: list[DocumentoDistribuicao] = field(default_factory=list)
    documentos_resumo: int = 0
    mensagem_usuario: str = ''
    bloquear_retentativa: bool = False
    aguardar_proxima_consulta: bool = False


def _local_name(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _texto_filho(pai: etree._Element, nome: str) -> str:
    for filho in pai:
        if _local_name(filho.tag) == nome:
            return (filho.text or '').strip()
    return ''


def _int_nsu(val: str) -> int:
    digits = re.sub(r'\D', '', val or '')
    return int(digits) if digits else 0


def decodificar_doc_zip(conteudo_b64: str) -> bytes:
    raw = base64.b64decode(conteudo_b64 or '')
    if raw[:2] == b'\x1f\x8b':
        return gzip.decompress(raw)
    return raw


def _classificar_schema(schema: str) -> str:
    s = (schema or '').lower().replace('.xsd', '')
    if 'procnfe' in s or s == 'nfeproc':
        return 'NFE'
    if 'proccte' in s or s == 'cteproc':
        return 'CTE'
    if 'resnfe' in s:
        return 'RES_NFE'
    if 'rescte' in s:
        return 'RES_CTE'
    return 'OUTRO'


def parse_distribuicao_dfe_response(raw: Any) -> ResultadoDistribuicaoDfe:
    resultado = ResultadoDistribuicaoDfe()
    xml = normalizar_xml_bruto(raw)
    if not xml:
        resultado.mensagem_usuario = 'Resposta vazia da SEFAZ na distribuição DF-e.'
        return resultado

    try:
        root = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
    except etree.XMLSyntaxError:
        logger.debug('XML inválido na distribuição DF-e (tamanho=%s)', len(xml))
        resultado.mensagem_usuario = 'Resposta inválida da SEFAZ na distribuição DF-e.'
        return resultado

    ret = root
    if _local_name(ret.tag) != 'retDistDFeInt':
        for el in root.iter():
            if _local_name(el.tag) == 'retDistDFeInt':
                ret = el
                break

    if _local_name(ret.tag) != 'retDistDFeInt':
        resultado.mensagem_usuario = 'Estrutura de retorno SEFAZ não reconhecida (retDistDFeInt).'
        return resultado

    resultado.sucesso_parse = True
    resultado.cstat = _texto_filho(ret, 'cStat')
    resultado.xmotivo = _texto_filho(ret, 'xMotivo')
    resultado.ult_nsu = _int_nsu(_texto_filho(ret, 'ultNSU'))
    resultado.max_nsu = _int_nsu(_texto_filho(ret, 'maxNSU'))

    if resultado.cstat in CSTAT_CONSUMO_INDEVIDO:
        resultado.bloquear_retentativa = True
        resultado.mensagem_usuario = (
            'SEFAZ bloqueou consultas por consumo indevido. '
            'Aguarde cerca de 1 hora antes de tentar novamente.'
        )
        return resultado

    if resultado.cstat in CSTAT_NENHUM_DOCUMENTO:
        resultado.aguardar_proxima_consulta = True
        resultado.mensagem_usuario = resultado.xmotivo or 'Nenhum documento novo na SEFAZ para este NSU.'
        return resultado

    if resultado.cstat not in CSTAT_DOCUMENTOS_LOCALIZADOS:
        resultado.mensagem_usuario = resultado.xmotivo or f'SEFAZ retornou status {resultado.cstat or "desconhecido"}.'
        return resultado

    for el in ret.iter():
        if _local_name(el.tag) != 'docZip':
            continue
        nsu = (el.get('NSU') or el.get('nsu') or '').strip()
        schema = (el.get('schema') or '').strip()
        tipo = _classificar_schema(schema)
        if tipo in {'RES_NFE', 'RES_CTE'}:
            try:
                conteudo = decodificar_doc_zip(el.text or '')
            except Exception as exc:
                logger.debug('Falha ao decodificar resumo NSU=%s: %s', nsu, exc)
                resultado.documentos_resumo += 1
                continue
            if conteudo:
                resultado.documentos.append(
                    DocumentoDistribuicao(nsu=nsu, schema=schema, conteudo_xml=conteudo, tipo=tipo),
                )
            resultado.documentos_resumo += 1
            continue
        if tipo == 'OUTRO':
            continue
        try:
            conteudo = decodificar_doc_zip(el.text or '')
        except Exception as exc:
            logger.debug('Falha ao decodificar docZip NSU=%s: %s', nsu, exc)
            continue
        if not conteudo:
            continue
        resultado.documentos.append(
            DocumentoDistribuicao(nsu=nsu, schema=schema, conteudo_xml=conteudo, tipo=tipo),
        )

    resultado.mensagem_usuario = resultado.xmotivo or 'Documentos localizados na SEFAZ.'
    return resultado
