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


def _parse_dh(raw: str) -> datetime | None:
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


def _find_inf_cte(root: ET.Element) -> ET.Element | None:
    lr = _local(root.tag)
    if lr == 'cteProc':
        cte = _find_child(root, 'CTe')
        inf = _find_child(cte, 'infCte') if cte is not None else None
        if inf is not None:
            return inf
        # alguns layouts trazem infCte dentro de CTe/infCteSupl (não comum); mantém fallback
        return _find_child(cte, 'infCte') if cte is not None else None
    if lr == 'CTe':
        return _find_child(root, 'infCte')
    return None


def _find_inf_prot(root: ET.Element) -> ET.Element | None:
    lr = _local(root.tag)
    if lr != 'cteProc':
        return None
    prot = _find_child(root, 'protCTe')
    return _find_child(prot, 'infProt') if prot is not None else None


def _extract_tomador_json(inf_cte: ET.Element) -> dict[str, Any]:
    """
    Resolve o tomador priorizando identificação documental (CNPJ/CPF).

    Regras:
    - toma4: possui dados do tomador (CNPJ/CPF), usar diretamente.
    - toma3: traz somente código do papel (tpToma/toma). Mapeamos para o
      participante correspondente (rem/exped/receb/dest) para preservar CNPJ.
    - compl/toma: fallback para layouts alternativos.
    """
    ide = _find_child(inf_cte, 'ide')
    if ide is not None:
        toma4 = _find_child(ide, 'toma4')
        if toma4 is not None:
            t4 = _element_to_jsonable(toma4) or {}
            if isinstance(t4, dict):
                return t4

        toma3 = _find_child(ide, 'toma3')
        if toma3 is not None:
            t3 = _element_to_jsonable(toma3) or {}
            tp_toma = _text(_find_child(toma3, 'tpToma')) or _text(_find_child(toma3, 'toma'))
            # CT-e: 0=remetente, 1=expedidor, 2=recebedor, 3=destinatário
            party_by_toma = {
                '0': _element_to_jsonable(_find_child(inf_cte, 'rem')) or {},
                '1': _element_to_jsonable(_find_child(inf_cte, 'exped')) or {},
                '2': _element_to_jsonable(_find_child(inf_cte, 'receb')) or {},
                '3': _element_to_jsonable(_find_child(inf_cte, 'dest')) or {},
            }
            party = party_by_toma.get(tp_toma, {})
            if isinstance(party, dict) and party:
                party['tpToma'] = tp_toma
                party['origem_tomador'] = 'toma3_mapeado'
                return party
            if isinstance(t3, dict):
                t3['tpToma'] = tp_toma
                t3['origem_tomador'] = 'toma3_sem_participante'
                return t3

    compl = _find_child(inf_cte, 'compl')
    toma = _find_child(compl, 'toma') if compl is not None else None
    comp = _element_to_jsonable(toma) or {}
    return comp if isinstance(comp, dict) else {}


def _extract_chaves_nfe(inf_cte: ET.Element) -> list[str]:
    out: list[str] = []
    inf_cte_norm = _find_child(inf_cte, 'infCTeNorm')
    inf_doc = _find_child(inf_cte_norm, 'infDoc') if inf_cte_norm is not None else None
    if inf_doc is None:
        return out
    for ch in inf_doc:
        if _local(ch.tag) != 'infNFe':
            continue
        k = _text(_find_child(ch, 'chave'))
        if k and len(k) == 44 and k.isdigit():
            out.append(k)
    # dedup preservando ordem
    seen = set()
    uniq = []
    for k in out:
        if k in seen:
            continue
        seen.add(k)
        uniq.append(k)
    return uniq


def _icms_from_imposto(imposto_json: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    """
    Retorna (base, aliquota, valor) a partir do bloco imp/ICMS do CT-e.
    Estrutura varia (ICMS00, ICMS20, ICMS45, etc). Pegamos campos padrão quando existirem.
    """
    if not imposto_json or not isinstance(imposto_json, dict):
        return (Decimal('0'), Decimal('0'), Decimal('0'))
    imp = imposto_json.get('imp')
    if isinstance(imp, list):
        imp = imp[0] if imp else {}
    if not isinstance(imp, dict):
        imp = imposto_json
    icms = imp.get('ICMS') if isinstance(imp, dict) else None
    if isinstance(icms, list):
        icms = icms[0] if icms else {}
    if not isinstance(icms, dict):
        return (Decimal('0'), Decimal('0'), Decimal('0'))

    # ICMS normalmente tem um único sub-bloco (ICMS00, ICMS20...)
    sub = None
    for v in icms.values():
        if isinstance(v, dict):
            sub = v
            break
        if isinstance(v, list) and v and isinstance(v[0], dict):
            sub = v[0]
            break
    if not isinstance(sub, dict):
        sub = icms

    base = _to_decimal(str(sub.get('vBC') or sub.get('vBCSTRet') or sub.get('vBCST') or ''))
    aliq = _to_decimal(str(sub.get('pICMS') or sub.get('pICMSSTRet') or sub.get('pICMSST') or ''))
    valor = _to_decimal(str(sub.get('vICMS') or sub.get('vICMSSTRet') or sub.get('vICMSST') or ''))
    return (base, aliq, valor)


@dataclass
class ParsedCTe:
    chave_acesso: str = ''
    erro: str | None = None
    numero: str = ''
    serie: str = ''
    modelo: str = ''
    dh_emissao: datetime | None = None
    tp_amb: str = ''
    nat_op: str = ''
    cfop: str = ''
    versao_layout: str = ''
    cstat: str = ''
    xmotivo: str = ''
    protocolo: str = ''

    cancelado: bool = False
    status_documento: str = 'autorizado'
    data_cancelamento: datetime | None = None
    protocolo_cancelamento: str = ''
    motivo_cancelamento: str = ''

    valor_total_servico: Decimal = field(default_factory=lambda: Decimal('0'))
    valor_receber: Decimal = field(default_factory=lambda: Decimal('0'))
    componentes_frete: list[dict[str, Any]] = field(default_factory=list)

    icms_base: Decimal = field(default_factory=lambda: Decimal('0'))
    icms_aliquota: Decimal = field(default_factory=lambda: Decimal('0'))
    icms_valor: Decimal = field(default_factory=lambda: Decimal('0'))

    modal: str = ''
    tipo_servico: str = ''
    municipio_inicio: str = ''
    uf_inicio: str = ''
    municipio_fim: str = ''
    uf_fim: str = ''

    emit_json: dict[str, Any] = field(default_factory=dict)
    rem_json: dict[str, Any] = field(default_factory=dict)
    dest_json: dict[str, Any] = field(default_factory=dict)
    exped_json: dict[str, Any] = field(default_factory=dict)
    receb_json: dict[str, Any] = field(default_factory=dict)
    tomador_json: dict[str, Any] = field(default_factory=dict)

    totais_json: dict[str, Any] = field(default_factory=dict)
    imposto_json: dict[str, Any] = field(default_factory=dict)
    prot_json: dict[str, Any] = field(default_factory=dict)
    reforma_e_outros_json: dict[str, Any] = field(default_factory=dict)

    chaves_nfe_vinculadas: list[str] = field(default_factory=list)


def parse_cte_xml(xml_bytes: bytes) -> ParsedCTe:
    out = ParsedCTe()
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        out.erro = f'XML inválido ou corrompido: {e}'
        return out

    inf_cte = _find_inf_cte(root)
    if inf_cte is None:
        out.erro = 'Não foi possível localizar o bloco infCte. Verifique se é um XML de CT-e (CTe ou cteProc).'
        return out

    out.versao_layout = inf_cte.get('versao') or ''

    ide = _find_child(inf_cte, 'ide')
    if ide is None:
        out.erro = 'XML sem grupo ide.'
        return out

    out.numero = _text(_find_child(ide, 'nCT'))
    out.serie = _text(_find_child(ide, 'serie'))
    out.modelo = _text(_find_child(ide, 'mod'))
    out.tp_amb = _text(_find_child(ide, 'tpAmb'))
    out.nat_op = _text(_find_child(ide, 'natOp'))[:120]
    out.cfop = _text(_find_child(ide, 'CFOP'))[:8]
    out.modal = _text(_find_child(ide, 'modal'))[:16]
    out.tipo_servico = _text(_find_child(ide, 'tpServ'))[:16]
    out.municipio_inicio = _text(_find_child(ide, 'xMunIni'))[:120]
    out.uf_inicio = _text(_find_child(ide, 'UFIni'))[:2]
    out.municipio_fim = _text(_find_child(ide, 'xMunFim'))[:120]
    out.uf_fim = _text(_find_child(ide, 'UFFim'))[:2]

    dh = _text(_find_child(ide, 'dhEmi')) or _text(_find_child(ide, 'dEmi'))
    out.dh_emissao = _parse_dh(dh)
    if out.dh_emissao is None:
        out.erro = 'Data de emissão (dhEmi/dEmi) inválida ou ausente.'
        return out

    # chave de acesso
    cte_id = inf_cte.get('Id') or ''
    if cte_id.upper().startswith('CTE'):
        out.chave_acesso = cte_id[3:47] if len(cte_id) >= 47 else cte_id.replace('CTe', '').replace('cte', '')[:44]

    inf_prot = _find_inf_prot(root)
    if inf_prot is not None:
        ch = _text(_find_child(inf_prot, 'chCTe'))
        if ch:
            out.chave_acesso = ch
        out.protocolo = _text(_find_child(inf_prot, 'nProt'))
        out.cstat = _text(_find_child(inf_prot, 'cStat'))
        out.xmotivo = _text(_find_child(inf_prot, 'xMotivo'))[:255]
        out.prot_json = _element_to_jsonable(inf_prot) or {}

    if not out.chave_acesso or len(out.chave_acesso.strip()) != 44 or not out.chave_acesso.isdigit():
        out.erro = 'Chave de acesso do CT-e não encontrada ou inválida (esperados 44 dígitos).'
        return out

    # participantes
    out.emit_json = _element_to_jsonable(_find_child(inf_cte, 'emit')) or {}
    out.rem_json = _element_to_jsonable(_find_child(inf_cte, 'rem')) or {}
    out.dest_json = _element_to_jsonable(_find_child(inf_cte, 'dest')) or {}
    out.exped_json = _element_to_jsonable(_find_child(inf_cte, 'exped')) or {}
    out.receb_json = _element_to_jsonable(_find_child(inf_cte, 'receb')) or {}
    out.tomador_json = _extract_tomador_json(inf_cte)

    # totais/valores
    v_prest = _find_child(inf_cte, 'vPrest')
    if v_prest is not None:
        out.totais_json = _element_to_jsonable(v_prest) or {}
        out.valor_total_servico = _to_decimal(_text(_find_child(v_prest, 'vTPrest')))
        out.valor_receber = _to_decimal(_text(_find_child(v_prest, 'vRec')))
        comp = _find_child(v_prest, 'Comp')
        if comp is not None:
            out.componentes_frete = _element_to_jsonable(comp) or []
        else:
            # múltiplos Comp podem existir
            comps = []
            for ch in list(v_prest):
                if _local(ch.tag) == 'Comp':
                    comps.append(_element_to_jsonable(ch))
            out.componentes_frete = [c for c in comps if c] if comps else []

    imp = _find_child(inf_cte, 'imp')
    out.imposto_json = _element_to_jsonable(imp) or {}
    base, aliq, valor = _icms_from_imposto({'imp': out.imposto_json} if 'ICMS' not in out.imposto_json else out.imposto_json)
    out.icms_base = base
    out.icms_aliquota = aliq
    out.icms_valor = valor

    out.chaves_nfe_vinculadas = _extract_chaves_nfe(inf_cte)

    # status efetivo básico por cStat (sem eventos nesta fase)
    if out.cstat in {'101', '135', '155'}:
        out.cancelado = True
        out.status_documento = 'cancelado'
        out.motivo_cancelamento = out.xmotivo
        out.protocolo_cancelamento = out.protocolo
    else:
        out.cancelado = False
        out.status_documento = 'autorizado' if out.cstat in {'100'} else (out.status_documento or 'pendente')

    # grupos extras (compatibilidade futura)
    extra: dict[str, Any] = {}
    for ch in inf_cte:
        lname = _local(ch.tag)
        if lname in {'ide', 'emit', 'rem', 'dest', 'exped', 'receb', 'vPrest', 'imp', 'compl', 'infCTeNorm'}:
            continue
        extra[lname] = _element_to_jsonable(ch)
    if extra:
        out.reforma_e_outros_json = extra

    return out

