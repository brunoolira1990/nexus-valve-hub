"""Validação XSD local NF-e 4.00 / enviNFe antes de transmitir à SEFAZ."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from lxml import etree

TipoXmlSchema = Literal['NFE', 'ENVI_NFE', 'XML_ASSINADO']

_SCHEMA_CACHE: dict[str, etree.XMLSchema] = {}


def _xsd_path(tipo: TipoXmlSchema) -> Path:
    import nfelib

    base = Path(nfelib.__file__).resolve().parent / 'nfe' / 'schemas' / 'v4_0'
    if tipo == 'ENVI_NFE':
        return base / 'enviNFe_v4.00.xsd'
    return base / 'nfe_v4.00.xsd'


def _schema(tipo: TipoXmlSchema) -> etree.XMLSchema:
    key = tipo if tipo != 'XML_ASSINADO' else 'NFE'
    if key not in _SCHEMA_CACHE:
        xsd_path = _xsd_path(key)  # type: ignore[arg-type]
        doc = etree.parse(str(xsd_path))
        _SCHEMA_CACHE[key] = etree.XMLSchema(doc)
    return _SCHEMA_CACHE[key]


def _erro_dict(error_log: Any) -> dict[str, Any]:
    return {
        'linha': int(getattr(error_log, 'line', 0) or 0),
        'coluna': int(getattr(error_log, 'column', 0) or 0),
        'dominio': str(getattr(error_log, 'domain_name', '') or ''),
        'tipo': str(getattr(error_log, 'type_name', '') or ''),
        'mensagem': str(getattr(error_log, 'message', '') or '').strip(),
        'elemento': str(getattr(error_log, 'path', '') or ''),
    }


def validar_xml_nfe_schema(xml: bytes | str, tipo: str) -> dict[str, Any]:
    """
    Valida XML contra XSD nfelib.

    tipo: NFE | ENVI_NFE | XML_ASSINADO (usa nfe_v4.00.xsd)
    """
    tipo_u = (tipo or 'NFE').upper().replace('-', '_')
    if tipo_u not in ('NFE', 'ENVI_NFE', 'XML_ASSINADO'):
        return {
            'ok': False,
            'tipo': tipo_u,
            'erros': [{'linha': 0, 'coluna': 0, 'dominio': '', 'tipo': '', 'mensagem': f'Tipo inválido: {tipo}', 'elemento': ''}],
        }

    xml_str = xml.decode('utf-8') if isinstance(xml, bytes) else xml
    if not xml_str.strip():
        return {
            'ok': False,
            'tipo': tipo_u,
            'erros': [{'linha': 0, 'coluna': 0, 'dominio': '', 'tipo': '', 'mensagem': 'XML vazio.', 'elemento': ''}],
        }

    schema_key: TipoXmlSchema = 'ENVI_NFE' if tipo_u == 'ENVI_NFE' else 'NFE'  # type: ignore[assignment]

    try:
        doc = etree.fromstring(xml_str.encode('utf-8'))
        schema = _schema(schema_key)
        valido = schema.validate(doc)
        if valido:
            return {'ok': True, 'tipo': tipo_u, 'erros': []}
        erros = [_erro_dict(e) for e in schema.error_log]
        return {'ok': False, 'tipo': tipo_u, 'erros': erros}
    except etree.XMLSyntaxError as exc:
        return {
            'ok': False,
            'tipo': tipo_u,
            'erros': [
                {
                    'linha': int(exc.lineno or 0),
                    'coluna': int(exc.offset or 0),
                    'dominio': '',
                    'tipo': 'XMLSyntaxError',
                    'mensagem': str(exc),
                    'elemento': '',
                },
            ],
        }
    except Exception as exc:
        return {
            'ok': False,
            'tipo': tipo_u,
            'erros': [
                {
                    'linha': 0,
                    'coluna': 0,
                    'dominio': '',
                    'tipo': type(exc).__name__,
                    'mensagem': str(exc),
                    'elemento': '',
                },
            ],
        }


def validar_emissao_completa(
    xml_nfe: str,
    xml_envi_nfe: str,
    *,
    validar_assinado: bool = True,
    xml_pre_assinatura: str | None = None,
) -> dict[str, Any]:
    """Valida XSD + caracteres de edição (cStat 588) em NF-e, assinado e enviNFe."""
    from apps.fiscal.nfe_emissao.xml_compactacao import validar_xml_sem_caracteres_edicao

    validacoes: dict[str, Any] = {}
    erros: list[dict[str, Any]] = []

    for rotulo, conteudo in (
        ('XML_PRE', xml_pre_assinatura),
        ('XML_ASSINADO', xml_nfe),
        ('ENVI_NFE', xml_envi_nfe),
    ):
        if not conteudo:
            continue
        ed = validar_xml_sem_caracteres_edicao(conteudo)
        validacoes[f'edicao_{rotulo}'] = ed
        if not ed.get('ok'):
            for e in ed.get('erros') or []:
                erros.append({**e, 'contexto': rotulo})
            return {
                'ok': False,
                'tipo': 'CARACTERES_EDICAO',
                'erros': erros,
                'validacoes': validacoes,
                'compacto': False,
                'schema_ok': None,
            }

    tipos_xsd: list[tuple[str, str]] = []
    if validar_assinado:
        tipos_xsd.append(('XML_ASSINADO', xml_nfe))
    tipos_xsd.append(('ENVI_NFE', xml_envi_nfe))

    for tipo, conteudo in tipos_xsd:
        res = validar_xml_nfe_schema(conteudo, tipo)
        validacoes[tipo] = res
        if not res.get('ok'):
            erros.extend(res.get('erros') or [])
            return {
                'ok': False,
                'tipo': res.get('tipo'),
                'erros': erros,
                'validacoes': validacoes,
                'compacto': True,
                'schema_ok': False,
            }

    return {
        'ok': True,
        'tipo': 'NFE',
        'erros': [],
        'validacoes': validacoes,
        'compacto': True,
        'schema_ok': True,
    }
