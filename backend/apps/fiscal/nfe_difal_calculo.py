"""Cálculo DIFAL/FCP destino (ICMSUFDest) para NF-e Saída — consumidor final não contribuinte."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.regras_fiscais.models import RegraFiscalSaida


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _dec(val) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _q2(val: Decimal) -> str:
    return str(val.quantize(Decimal('0.01')))


def _norm_uf(uf: str) -> str:
    return _text(uf).upper()[:2]


def deve_aplicar_difal(
    *,
    uf_origem: str,
    uf_destino: str,
    destinatario_contribuinte: str,
    consumidor_final: bool | None,
    regra: RegraFiscalSaida | None,
) -> bool:
    ufo = _norm_uf(uf_origem)
    ufd = _norm_uf(uf_destino)
    if len(ufo) != 2 or len(ufd) != 2 or ufo == ufd:
        return False
    if destinatario_contribuinte == RegraFiscalSaida.DestinatarioContribuinte.CONTRIBUINTE:
        return False
    if consumidor_final is not True:
        return False
    if regra is None or not regra.difal_aplicavel:
        return False
    return True


def validar_parametros_difal_regra(
    regra: RegraFiscalSaida,
    *,
    uf_destino: str = '',
    nome_item: str = '',
) -> list[str]:
    prefixo = f'Regra fiscal #{regra.pk}'
    if nome_item:
        prefixo = f'{nome_item} — {prefixo}'
    erros: list[str] = []
    if not regra.difal_aplicavel:
        return erros
    ali_inter = _dec(regra.aliquota_icms_interestadual)
    ali_dest = _dec(regra.aliquota_icms_interna_destino)
    if ali_inter <= 0:
        erros.append(f'{prefixo}: informe alíquota ICMS interestadual para DIFAL.')
    if ali_dest <= 0:
        ufd = _norm_uf(uf_destino) or 'destino'
        erros.append(f'{prefixo}: informe alíquota ICMS interna da UF {ufd} para DIFAL.')
    if regra.fcp_aplicavel and _dec(regra.aliquota_fcp) < 0:
        erros.append(f'{prefixo}: alíquota FCP destino inválida.')
    return erros


def calcular_difal_item(
    valor_base: Decimal,
    regra: RegraFiscalSaida,
) -> dict[str, Any]:
    """Retorna snapshot DIFAL por item (valores monetários em string com 2 casas)."""
    ali_inter = _dec(regra.aliquota_icms_interestadual)
    ali_dest = _dec(regra.aliquota_icms_interna_destino)
    base = max(valor_base, Decimal('0')).quantize(Decimal('0.01'))

    difal_pct = max(ali_dest - ali_inter, Decimal('0'))
    v_icms_uf_dest = (base * difal_pct / Decimal('100')).quantize(Decimal('0.01'))
    v_icms_uf_remet = Decimal('0')

    p_fcp = Decimal('0')
    v_fcp = Decimal('0')
    if regra.fcp_aplicavel:
        p_fcp = _dec(regra.aliquota_fcp)
        if p_fcp > 0:
            v_fcp = (base * p_fcp / Decimal('100')).quantize(Decimal('0.01'))

    return {
        'aplicavel': True,
        'v_bc_uf_dest': _q2(base),
        'v_bc_fcp_uf_dest': _q2(base),
        'p_fcp_uf_dest': _q2(p_fcp),
        'p_icms_uf_dest': _q2(ali_dest),
        'p_icms_inter': _q2(ali_inter),
        'p_icms_inter_part': '100.00',
        'v_fcp_uf_dest': _q2(v_fcp),
        'v_icms_uf_dest': _q2(v_icms_uf_dest),
        'v_icms_uf_remet': _q2(v_icms_uf_remet),
    }


def difal_emitido_no_item(difal: dict[str, Any] | None) -> bool:
    """Indica se o item deve ter grupo ICMSUFDest no XML (mesma regra da serialização)."""
    if not difal:
        return False
    if difal.get('aplicavel') in (True, 'True', 'true', '1', 1):
        return True
    if _dec(difal.get('v_icms_uf_dest')) > 0:
        return True
    if _dec(difal.get('v_fcp_uf_dest')) > 0:
        return True
    return False


def valores_difal_item_xml(difal: dict[str, Any]) -> dict[str, Decimal] | None:
    """Valores do ICMSUFDest efetivamente emitidos no XML do item."""
    if not difal_emitido_no_item(difal):
        return None
    p_fcp = _dec(difal.get('p_fcp_uf_dest'))
    v_fcp_raw = _dec(difal.get('v_fcp_uf_dest'))
    v_fcp = v_fcp_raw if (p_fcp > 0 or v_fcp_raw > 0) else Decimal('0')
    return {
        'v_icms_uf_dest': _dec(difal.get('v_icms_uf_dest')),
        'v_fcp_uf_dest': v_fcp,
        'v_icms_uf_remet': _dec(difal.get('v_icms_uf_remet')),
    }


CHAVES_TOTAIS_DIFAL = ('v_fcp_uf_dest', 'v_icms_uf_dest', 'v_icms_uf_remet')


class NFeDifalXmlInconsistenteError(ValueError):
    """ICMSTot DIFAL/FCP divergente dos itens — SEFAZ rejeita (ex.: cStat 798)."""


def agregar_totais_difal(snapshots_difal: list[dict[str, Any]]) -> dict[str, str]:
    """Soma DIFAL/FCP alinhada ao que é serializado por item (evita cStat 798)."""
    v_fcp = Decimal('0')
    v_dest = Decimal('0')
    v_remet = Decimal('0')
    for raw in snapshots_difal:
        valores = valores_difal_item_xml(raw or {})
        if not valores:
            continue
        v_dest += valores['v_icms_uf_dest']
        v_fcp += valores['v_fcp_uf_dest']
        v_remet += valores['v_icms_uf_remet']
    if v_dest <= 0 and v_fcp <= 0 and v_remet <= 0:
        return {}
    out: dict[str, str] = {}
    if v_dest > 0:
        out['v_icms_uf_dest'] = _q2(v_dest)
    if v_fcp > 0:
        out['v_fcp_uf_dest'] = _q2(v_fcp)
    if v_remet > 0:
        out['v_icms_uf_remet'] = _q2(v_remet)
    return out


def coletar_snapshots_difal_de_linhas(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from apps.fiscal.snapshot_fiscal_helpers import resolver_difal_snapshot_linha

    return [resolver_difal_snapshot_linha(linha) for linha in linhas]


def _attr_dec(obj: object | None, *names: str) -> Decimal:
    if obj is None:
        return Decimal('0')
    for name in names:
        val = getattr(obj, name, None)
        if val is not None:
            return _dec(val)
    return Decimal('0')


def _icms_grupo_det(det) -> object | None:
    imposto = det.imposto
    return (
        getattr(imposto, 'ICMS', None)
        or getattr(imposto, 'Icms', None)
        or getattr(imposto, 'icms', None)
    )


def _icms_uf_dest_det(det) -> object | None:
    icms = _icms_grupo_det(det)
    if icms is None:
        return None
    return (
        getattr(icms, 'ICMSUFDest', None)
        or getattr(icms, 'Icmsufdest', None)
        or getattr(icms, 'icmsufdest', None)
    )


def _valor_vfcp_uf_dest_item(ufdest: object | None) -> Decimal:
    return _attr_dec(ufdest, 'vFCPUFDest', 'vFcpufdest', 'v_fcpufdest', 'vfcpufdest')


def _valor_vicms_uf_dest_item(ufdest: object | None) -> Decimal:
    return _attr_dec(ufdest, 'vICMSUFDest', 'vIcmsufdest', 'v_icmsufdest', 'vicmsufdest')


def _valor_vicms_uf_remet_item(ufdest: object | None) -> Decimal:
    return _attr_dec(ufdest, 'vICMSUFRemet', 'vIcmsufremet', 'v_icmsufremet', 'vicmsufremet')


def agregar_totais_difal_de_det(det_list: list) -> dict[str, str]:
    """Soma DIFAL/FCP a partir dos grupos ICMSUFDest já montados nos itens do XML."""
    v_fcp = Decimal('0')
    v_dest = Decimal('0')
    v_remet = Decimal('0')
    for det in det_list or []:
        ufdest = _icms_uf_dest_det(det)
        if ufdest is None:
            continue
        v_dest += _valor_vicms_uf_dest_item(ufdest)
        v_fcp += _valor_vfcp_uf_dest_item(ufdest)
        v_remet += _valor_vicms_uf_remet_item(ufdest)
    if v_dest <= 0 and v_fcp <= 0 and v_remet <= 0:
        return {}
    out: dict[str, str] = {}
    if v_dest > 0:
        out['v_icms_uf_dest'] = _q2(v_dest)
    if v_fcp > 0:
        out['v_fcp_uf_dest'] = _q2(v_fcp)
    if v_remet > 0:
        out['v_icms_uf_remet'] = _q2(v_remet)
    return out


def _validar_snapshots_vs_det_difal(snap_tot: dict[str, str], det_tot: dict[str, str]) -> None:
    """Bloqueia XML quando snapshots têm DIFAL/FCP mas o item não serializou ICMSUFDest."""
    checks = (
        ('v_fcp_uf_dest', 'FCP UF destino'),
        ('v_icms_uf_dest', 'ICMS UF destino'),
        ('v_icms_uf_remet', 'ICMS UF remetente'),
    )
    for key, label in checks:
        snap_v = _dec(snap_tot.get(key))
        det_v = _dec(det_tot.get(key))
        if snap_v > 0 and det_v == 0:
            raise NFeDifalXmlInconsistenteError(
                f'{label} calculado nos snapshots (R$ {_q2(snap_v)}) mas ausente nos itens do XML. '
                'Atualize impostos na conferência e valide novamente.'
            )
        if snap_v != det_v:
            raise NFeDifalXmlInconsistenteError(
                f'Inconsistência {label} no XML de transmissão: '
                f'snapshots R$ {_q2(snap_v)} ≠ itens R$ {_q2(det_v)}. '
                'Atualize impostos na conferência e valide novamente.'
            )


def aplicar_totais_difal_em_dados(dados: dict[str, Any], *, det_list: list | None = None) -> None:
    """Recalcula totais DIFAL/FCP no payload antes de montar ICMSTot (XML SEFAZ)."""
    tot = dict(dados.get('totais') or {})
    for key in CHAVES_TOTAIS_DIFAL:
        tot.pop(key, None)
    snap_tot = agregar_totais_difal(coletar_snapshots_difal_de_linhas(dados.get('itens') or []))
    if det_list is not None:
        det_tot = agregar_totais_difal_de_det(det_list)
        _validar_snapshots_vs_det_difal(snap_tot, det_tot)
        tot.update(det_tot)
    else:
        tot.update(snap_tot)
    dados['totais'] = tot


def somar_vfcp_uf_dest_tnfe(tnfe) -> Decimal:
    total = Decimal('0')
    for det in tnfe.infNFe.det:
        total += _valor_vfcp_uf_dest_item(_icms_uf_dest_det(det))
    return total


def somar_vicms_uf_dest_tnfe(tnfe) -> Decimal:
    total = Decimal('0')
    for det in tnfe.infNFe.det:
        total += _valor_vicms_uf_dest_item(_icms_uf_dest_det(det))
    return total


def validar_consistencia_difal_tnfe(tnfe) -> None:
    """Bloqueia transmissão se ICMSTot DIFAL/FCP não bater com a soma dos itens."""
    icms_tot = tnfe.infNFe.total.ICMSTot
    soma_fcp = somar_vfcp_uf_dest_tnfe(tnfe)
    total_fcp = _dec(icms_tot.vFCPUFDest)
    if soma_fcp != total_fcp:
        raise NFeDifalXmlInconsistenteError(
            'Inconsistência FCP UF destino no XML de transmissão: '
            f'soma dos itens R$ {_q2(soma_fcp)} ≠ total ICMSTot R$ {_q2(total_fcp)} '
            '(SEFAZ cStat 798). Atualize impostos na conferência e valide novamente.'
        )
    soma_dest = somar_vicms_uf_dest_tnfe(tnfe)
    total_dest = _dec(icms_tot.vICMSUFDest)
    if soma_dest != total_dest:
        raise NFeDifalXmlInconsistenteError(
            'Inconsistência ICMS UF destino no XML de transmissão: '
            f'soma dos itens R$ {_q2(soma_dest)} ≠ total ICMSTot R$ {_q2(total_dest)}. '
            'Atualize impostos na conferência e valide novamente.'
        )


def texto_difal_inf_complementar(totais_difal: dict[str, str]) -> str:
    if not totais_difal:
        return ''
    v_dest = _dec(totais_difal.get('v_icms_uf_dest'))
    v_fcp = _dec(totais_difal.get('v_fcp_uf_dest'))
    if v_dest <= 0 and v_fcp <= 0:
        return ''
    partes: list[str] = []
    if v_dest > 0:
        partes.append(f'VALOR ICMS UF DESTINO R$ {_q2(v_dest)}')
    if v_fcp > 0:
        partes.append(f'VALOR FCP UF DESTINO R$ {_q2(v_fcp)}')
    return ' — '.join(partes)
