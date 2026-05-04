from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from .parser import (
    INF_CHILD_CORE,
    _element_to_jsonable,
    _find_child,
    _find_inf_nfe,
    _find_inf_prot,
    _flatten_party,
    _local,
    _parse_dh_emi,
    _text,
    _to_decimal,
)
import xml.etree.ElementTree as ET


@dataclass
class ParsedNFeEntrada:
    chave_acesso: str = ''
    erro: str | None = None
    numero: str = ''
    serie: str = ''
    modelo: str = ''
    dh_emissao: datetime | None = None
    tp_amb: str = ''
    tp_nf: str = ''
    nat_op: str = ''
    versao_layout: str = ''
    cstat: str = ''
    xmotivo: str = ''
    protocolo: str = ''
    valor_produtos: Decimal = field(default_factory=lambda: Decimal('0'))
    valor_total_nf: Decimal = field(default_factory=lambda: Decimal('0'))
    v_frete: Decimal = field(default_factory=lambda: Decimal('0'))
    v_seg: Decimal = field(default_factory=lambda: Decimal('0'))
    v_desc: Decimal = field(default_factory=lambda: Decimal('0'))
    v_outro: Decimal = field(default_factory=lambda: Decimal('0'))
    emit_json: dict[str, Any] = field(default_factory=dict)
    dest_json: dict[str, Any] = field(default_factory=dict)
    totais_json: dict[str, Any] = field(default_factory=dict)
    reforma_e_outros_json: dict[str, Any] = field(default_factory=dict)
    prot_json: dict[str, Any] = field(default_factory=dict)
    itens: list[dict[str, Any]] = field(default_factory=list)


def parse_nfe_entrada_xml(xml_bytes: bytes) -> ParsedNFeEntrada:
    out = ParsedNFeEntrada()
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        out.erro = f'XML inválido ou corrompido: {e}'
        return out

    inf_nfe = _find_inf_nfe(root)
    if inf_nfe is None:
        out.erro = 'Não foi possível localizar o bloco infNFe. Verifique se é um XML de NF-e.'
        return out

    out.versao_layout = inf_nfe.get('versao') or ''
    ide = _find_child(inf_nfe, 'ide')
    if ide is None:
        out.erro = 'XML sem grupo ide.'
        return out

    out.tp_nf = _text(_find_child(ide, 'tpNF'))
    # tpNF=1 com emitente = fornecedor é o caso típico de NF-e de compra (saída do emitente).
    if out.tp_nf not in ('0', '1'):
        out.erro = (
            'tpNF deve ser 0 ou 1. Verifique o XML.'
            if out.tp_nf
            else 'Campo tpNF ausente.'
        )
        return out

    out.numero = _text(_find_child(ide, 'nNF'))
    out.serie = _text(_find_child(ide, 'serie'))
    out.modelo = _text(_find_child(ide, 'mod'))
    out.tp_amb = _text(_find_child(ide, 'tpAmb'))
    out.nat_op = _text(_find_child(ide, 'natOp'))[:120]
    dh = _text(_find_child(ide, 'dhEmi')) or _text(_find_child(ide, 'dEmi'))
    out.dh_emissao = _parse_dh_emi(dh)
    if out.dh_emissao is None:
        out.erro = 'Data de emissão (dhEmi/dEmi) inválida ou ausente.'
        return out

    inf_prot = _find_inf_prot(root)
    if inf_prot is not None:
        out.chave_acesso = _text(_find_child(inf_prot, 'chNFe'))
        out.protocolo = _text(_find_child(inf_prot, 'nProt'))
        out.cstat = _text(_find_child(inf_prot, 'cStat'))
        out.xmotivo = _text(_find_child(inf_prot, 'xMotivo'))[:255]
        out.prot_json = _element_to_jsonable(inf_prot) or {}

    if not out.chave_acesso:
        nfe_id = inf_nfe.get('Id') or ''
        if nfe_id.upper().startswith('NFE'):
            out.chave_acesso = nfe_id[3:47] if len(nfe_id) >= 47 else nfe_id.replace('NFe', '').replace('nfe', '')[:44]
    if not out.chave_acesso or len(out.chave_acesso.strip()) != 44 or not out.chave_acesso.isdigit():
        out.erro = 'Chave de acesso da NF-e não encontrada ou inválida (esperados 44 dígitos).'
        return out

    emit_el = _find_child(inf_nfe, 'emit')
    dest_el = _find_child(inf_nfe, 'dest')
    out.emit_json = _flatten_party(emit_el)
    out.dest_json = _flatten_party(dest_el)
    total_el = _find_child(inf_nfe, 'total')
    if total_el is not None:
        out.totais_json = _element_to_jsonable(total_el) or {}
        icms_tot = _find_child(total_el, 'ICMSTot')
        if icms_tot is not None:
            out.valor_produtos = _to_decimal(_text(_find_child(icms_tot, 'vProd')))
            out.valor_total_nf = _to_decimal(_text(_find_child(icms_tot, 'vNF')))
            out.v_frete = _to_decimal(_text(_find_child(icms_tot, 'vFrete')))
            out.v_seg = _to_decimal(_text(_find_child(icms_tot, 'vSeg')))
            out.v_desc = _to_decimal(_text(_find_child(icms_tot, 'vDesc')))
            out.v_outro = _to_decimal(_text(_find_child(icms_tot, 'vOutro')))

    extra: dict[str, Any] = {}
    for ch in inf_nfe:
        lname = _local(ch.tag)
        if lname in INF_CHILD_CORE or lname.startswith('ref'):
            continue
        extra[lname] = _element_to_jsonable(ch)
    if extra:
        out.reforma_e_outros_json = extra

    itens = []
    for det in inf_nfe:
        if _local(det.tag) != 'det':
            continue
        n_item = int(det.get('nItem') or '0')
        prod_el = _find_child(det, 'prod')
        imp_el = _find_child(det, 'imposto')
        itens.append({'n_item': n_item, 'prod': _element_to_jsonable(prod_el) or {}, 'imposto': _element_to_jsonable(imp_el) or {}})
    itens.sort(key=lambda x: x['n_item'])
    out.itens = itens
    if not out.itens:
        out.erro = 'A NF-e não contém itens (det) para importar.'
    return out

