from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def _local(tag: str) -> str:
    if not tag:
        return ''
    return tag.split('}')[-1] if '}' in tag else tag


def _find_child(parent: ET.Element | None, name: str) -> ET.Element | None:
    if parent is None:
        return None
    for c in parent:
        if _local(c.tag) == name:
            return c
    return None


def _text(el: ET.Element | None, default: str = '') -> str:
    if el is None or el.text is None:
        return default
    return str(el.text).strip()


def _to_decimal(val: str | None) -> Decimal:
    if val is None or str(val).strip() == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _element_to_jsonable(elem: ET.Element | None) -> Any:
    if elem is None:
        return None
    children = list(elem)
    if not children:
        t = (elem.text or '').strip()
        return t if t else None
    out: dict[str, Any] = {}
    for ch in children:
        key = _local(ch.tag)
        val = _element_to_jsonable(ch)
        if key in out:
            prev = out[key]
            if isinstance(prev, list):
                prev.append(val)
            else:
                out[key] = [prev, val]
        else:
            out[key] = val
    return out


def _parse_dh_emi(raw: str) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    if 'T' in raw:
        dt = parse_datetime(raw)
        if dt is None:
            return None
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    d = parse_date(raw)
    if d is None:
        return None
    return timezone.make_aware(datetime.combine(d, time.min), timezone.get_current_timezone())


def _flatten_party(node: ET.Element | None) -> dict[str, Any]:
    if node is None:
        return {}
    data: dict[str, Any] = {}
    for ch in node:
        ln = _local(ch.tag)
        if len(list(ch)) == 0:
            if ch.text and str(ch.text).strip():
                data[ln] = str(ch.text).strip()
        else:
            data[ln] = _element_to_jsonable(ch)
    return data


def _doc_digits(party: dict[str, Any]) -> str:
    for k in ('CNPJ', 'CPF', 'cNPJ', 'cPF'):
        if k in party and party[k]:
            return ''.join(c for c in str(party[k]) if c.isdigit())
    return ''


INF_CHILD_CORE = frozenset(
    {
        'ide',
        'emit',
        'dest',
        'det',
        'total',
        'transp',
        'cobr',
        'pag',
        'infAdic',
        'exporta',
        'compra',
        'cana',
        'infRespTec',
        'infIntermed',
        'avulsa',
        'retirada',
        'entrega',
        'autXML',
        'infSinc',
    }
)


@dataclass
class ParsedNFeSaida:
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


@dataclass
class ParsedNFeEvento:
    erro: str | None = None
    tipo_evento: str = ''
    chave_acesso: str = ''
    protocolo_evento: str = ''
    id_evento: str = ''
    sequencial_evento: int = 0
    data_evento: datetime | None = None
    desc_evento: str = ''
    x_just: str = ''
    evento_json: dict[str, Any] = field(default_factory=dict)
    evento_cancelamento: bool = False


@dataclass
class ParsedNFeImport:
    tipo_documento: str = ''
    erro: str | None = None
    nfe: ParsedNFeSaida | None = None
    evento: ParsedNFeEvento | None = None


def parse_nfe_saida_xml(xml_bytes: bytes) -> ParsedNFeSaida:
    out = ParsedNFeSaida()
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        out.erro = f'XML inválido ou corrompido: {e}'
        return out

    ln = _local(root.tag)
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
    if out.tp_nf != '1':
        out.erro = (
            'Apenas NF-e de saída (tpNF=1) podem ser importadas neste fluxo.'
            if out.tp_nf
            else 'Campo tpNF ausente: não é possível confirmar que a nota é de saída.'
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

    itens: list[dict[str, Any]] = []
    for det in inf_nfe:
        if _local(det.tag) != 'det':
            continue
        n_item = int(det.get('nItem') or '0')
        prod_el = _find_child(det, 'prod')
        imp_el = _find_child(det, 'imposto')
        itens.append(
            {
                'n_item': n_item,
                'prod': _element_to_jsonable(prod_el) if prod_el is not None else {},
                'imposto': _element_to_jsonable(imp_el) if imp_el is not None else {},
            }
        )
    itens.sort(key=lambda x: x['n_item'])
    out.itens = itens
    if not out.itens:
        out.erro = 'A NF-e não contém itens (det) para importar.'
        return out

    return out


def _find_inf_nfe(root: ET.Element) -> ET.Element | None:
    lr = _local(root.tag)
    if lr == 'nfeProc':
        nfe = _find_child(root, 'NFe')
        return _find_child(nfe, 'infNFe') if nfe is not None else None
    if lr == 'NFe':
        return _find_child(root, 'infNFe')
    return None


def _find_inf_prot(root: ET.Element) -> ET.Element | None:
    lr = _local(root.tag)
    if lr != 'nfeProc':
        return None
    prot = _find_child(root, 'protNFe')
    return _find_child(prot, 'infProt') if prot is not None else None


def parse_xml_nfe_importacao(xml_bytes: bytes) -> ParsedNFeImport:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return ParsedNFeImport(tipo_documento='desconhecido', erro=f'XML inválido ou corrompido: {e}')

    ln = _local(root.tag)
    if ln in {'procEventoNFe', 'evento'}:
        parsed_evento = parse_evento_nfe_xml(xml_bytes)
        return ParsedNFeImport(
            tipo_documento='evento',
            erro=parsed_evento.erro,
            evento=parsed_evento,
        )

    parsed_nfe = parse_nfe_saida_xml(xml_bytes)
    return ParsedNFeImport(
        tipo_documento='nfe',
        erro=parsed_nfe.erro,
        nfe=parsed_nfe,
    )


def parse_evento_nfe_xml(xml_bytes: bytes) -> ParsedNFeEvento:
    out = ParsedNFeEvento()
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        out.erro = f'XML inválido ou corrompido: {e}'
        return out

    inf_evento = _find_inf_evento(root)
    if inf_evento is None:
        out.erro = 'Não foi possível localizar o bloco infEvento no XML de evento.'
        return out

    out.tipo_evento = _text(_find_child(inf_evento, 'tpEvento'))
    out.chave_acesso = _text(_find_child(inf_evento, 'chNFe'))
    out.id_evento = inf_evento.get('Id') or ''
    seq = _text(_find_child(inf_evento, 'nSeqEvento')) or '0'
    try:
        out.sequencial_evento = int(seq)
    except ValueError:
        out.sequencial_evento = 0
    dh = _text(_find_child(inf_evento, 'dhEvento'))
    out.data_evento = _parse_dh_emi(dh)

    ret = _find_ret_evento(root)
    if ret is not None:
        out.protocolo_evento = _text(_find_child(ret, 'nProt'))

    if not out.chave_acesso or len(out.chave_acesso) != 44 or not out.chave_acesso.isdigit():
        out.erro = 'Evento sem chave da NF-e válida (44 dígitos).'
        return out
    if not out.tipo_evento:
        out.erro = 'Evento sem tpEvento.'
        return out

    det_evt = _find_child(inf_evento, 'detEvento')
    if det_evt is not None:
        out.desc_evento = _text(_find_child(det_evt, 'descEvento'))
        out.x_just = _text(_find_child(det_evt, 'xJust'))
        if not out.desc_evento:
            out.desc_evento = _text(_find_child(det_evt, 'xCorrecao'))[:255]

    out.evento_cancelamento = out.tipo_evento == '110111'
    out.evento_json = {
        'procEventoNFe': _element_to_jsonable(root) if _local(root.tag) == 'procEventoNFe' else None,
        'evento': _element_to_jsonable(_find_child(root, 'evento') if _local(root.tag) == 'procEventoNFe' else root),
        'retEvento': _element_to_jsonable(_find_child(root, 'retEvento') if _local(root.tag) == 'procEventoNFe' else ret),
    }
    return out


def _find_inf_evento(root: ET.Element) -> ET.Element | None:
    lr = _local(root.tag)
    if lr == 'procEventoNFe':
        evento = _find_child(root, 'evento')
        if evento is None:
            return None
        inf_evento = _find_child(evento, 'infEvento')
        if inf_evento is not None:
            return inf_evento
        env = _find_child(evento, 'envEvento')
        return _find_child(env, 'infEvento') if env is not None else None
    if lr == 'evento':
        inf_evento = _find_child(root, 'infEvento')
        if inf_evento is not None:
            return inf_evento
        env = _find_child(root, 'envEvento')
        return _find_child(env, 'infEvento') if env is not None else None
    if lr == 'envEvento':
        return _find_child(root, 'infEvento')
    return None


def _find_ret_evento(root: ET.Element) -> ET.Element | None:
    lr = _local(root.tag)
    if lr == 'procEventoNFe':
        ret = _find_child(root, 'retEvento')
        return _find_child(ret, 'infEvento') if ret is not None else None
    if lr == 'retEvento':
        return _find_child(root, 'infEvento')
    return None


def extract_dest_documento(dest: dict[str, Any]) -> str:
    return _doc_digits(dest)
