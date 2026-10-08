"""Parser de resNFe retornado na distribuição DF-e."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.fiscal.nfe_historica_classificacao import norm_digits


@dataclass
class ResNFeParseado:
    chave_acesso: str
    cnpj_emitente: str
    razao_social_emitente: str
    ie_emitente: str
    dh_emissao: datetime | None
    valor_nf: Decimal
    tp_amb: str
    resumo_json: dict


def _local(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _texto(root: ET.Element, nome: str) -> str:
    for el in root.iter():
        if _local(el.tag) == nome:
            return (el.text or '').strip()
    return ''


def _parse_dh(val: str) -> datetime | None:
    raw = (val or '').strip()
    if not raw:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S'):
        try:
            dt = datetime.strptime(raw[:19], fmt[:19])
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        except ValueError:
            continue
    return None


def parse_resnfe_xml(xml_bytes: bytes) -> ResNFeParseado | None:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    if _local(root.tag) != 'resNFe':
        return None

    chave = _texto(root, 'chNFe')
    if len(chave) != 44:
        return None

    valor_raw = _texto(root, 'vNF') or '0'
    try:
        valor = Decimal(valor_raw.replace(',', '.'))
    except (InvalidOperation, ValueError):
        valor = Decimal('0')

    return ResNFeParseado(
        chave_acesso=chave,
        cnpj_emitente=norm_digits(_texto(root, 'CNPJ') or _texto(root, 'CPF')),
        razao_social_emitente=_texto(root, 'xNome'),
        ie_emitente=_texto(root, 'IE'),
        dh_emissao=_parse_dh(_texto(root, 'dhEmi')),
        valor_nf=valor,
        tp_amb=_texto(root, 'tpAmb') or '1',
        resumo_json={
            'chNFe': chave,
            'CNPJ': _texto(root, 'CNPJ'),
            'xNome': _texto(root, 'xNome'),
            'IE': _texto(root, 'IE'),
            'dhEmi': _texto(root, 'dhEmi'),
            'vNF': valor_raw,
            'tpAmb': _texto(root, 'tpAmb'),
            'nProt': _texto(root, 'nProt'),
            'cSitNFe': _texto(root, 'cSitNFe'),
        },
    )
