"""Cálculo DIFAL/FCP destino (ICMSUFDest) para NF-e Saída — consumidor final não contribuinte."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class AliquotasDifalResolvidas:
    aliquota_interestadual: Decimal
    aliquota_interna_destino: Decimal
    aliquota_fcp: Decimal
    fontes: list[str] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)
    usa_base_dupla: bool = False


def _registro_uf_destino(uf_destino: str) -> Any:
    """Linha da UF destino na tabela de referência (alíquotas + regime de base); None se não cadastrada."""
    from apps.regras_fiscais.models import AliquotaIcmsUF

    ufd = _norm_uf(uf_destino)
    if len(ufd) != 2:
        return None
    return AliquotaIcmsUF.objects.filter(uf=ufd, ativo=True).first()


def resolver_aliquotas_difal(
    regra: RegraFiscalSaida,
    *,
    uf_destino: str,
    nome_item: str = '',
) -> AliquotasDifalResolvidas:
    """Resolve alíquotas por UF destino: override na regra > tabela de alíquotas > sem origem (pendência).

    Sem a tabela, uma regra genérica (uf_destino vazio) aplicava a mesma alíquota
    interna a todos os estados; a resolução por UF elimina essa base única.
    """
    prefixo = f'Regra fiscal #{regra.pk}'
    if nome_item:
        prefixo = f'{nome_item} — {prefixo}'
    pendencias: list[str] = []
    fontes: list[str] = []
    tab = _registro_uf_destino(uf_destino)
    ali_tab_interna = _dec(tab.aliquota_interna) if tab is not None else Decimal('0')
    ali_tab_inter = _dec(tab.aliquota_interestadual) if tab is not None else Decimal('0')

    ali_inter = _dec(regra.aliquota_icms_interestadual)
    if ali_inter > 0:
        fontes.append('interestadual:regra')
    else:
        ali_inter = ali_tab_inter
        if ali_inter > 0:
            fontes.append('interestadual:tabela_uf')
    if ali_inter <= 0:
        pendencias.append(f'{prefixo}: informe alíquota ICMS interestadual para DIFAL.')

    ali_dest = _dec(regra.aliquota_icms_interna_destino)
    if ali_dest > 0:
        fontes.append('interna_destino:regra')
    else:
        if ali_tab_interna > 0:
            ali_dest = ali_tab_interna
            fontes.append('interna_destino:tabela_uf')
        else:
            ufd = _norm_uf(uf_destino) or 'destino'
            pendencias.append(f'{prefixo}: informe alíquota ICMS interna da UF {ufd} para DIFAL.')

    usa_base_dupla = tab is not None and bool(tab.usa_base_dupla)
    if usa_base_dupla:
        fontes.append('base_dupla:tabela_uf')

    p_fcp = Decimal('0')
    if regra.fcp_aplicavel:
        p_fcp = _dec(regra.aliquota_fcp)
        if p_fcp <= 0 and tab is not None and _dec(tab.aliquota_fcp) > 0:
            p_fcp = _dec(tab.aliquota_fcp)
            fontes.append('fcp:tabela_uf')
        if p_fcp < 0:
            pendencias.append(f'{prefixo}: alíquota FCP destino inválida.')

    return AliquotasDifalResolvidas(
        aliquota_interestadual=ali_inter,
        aliquota_interna_destino=ali_dest,
        aliquota_fcp=p_fcp,
        fontes=fontes,
        pendencias=pendencias,
        usa_base_dupla=usa_base_dupla,
    )


def validar_parametros_difal_regra(
    regra: RegraFiscalSaida,
    *,
    uf_destino: str = '',
    nome_item: str = '',
) -> list[str]:
    if not regra.difal_aplicavel:
        return []
    return resolver_aliquotas_difal(regra, uf_destino=uf_destino, nome_item=nome_item).pendencias


@dataclass(frozen=True)
class CalculoDifalBase:
    """BC do estado de destino, DIFAL e regime de base aplicados ao item."""

    base_uf_dest: Decimal
    icms_uf_dest: Decimal
    tipo_base: str


def calcular_difal_na_base(
    valor_base: Decimal,
    *,
    aliquota_interestadual: Decimal,
    aliquota_interna: Decimal,
    usa_base_dupla: bool,
) -> CalculoDifalBase:
    """DIFAL do item no regime da UF destino.

    Base única: DIFAL = BC × (interna − interestadual).
    Base dupla ("por dentro"): ICMS interestadual destacado primeiro, a BC do destino é
    recomposta dentro do próprio ICMS interno e só então se desconta o interestadual.
    """
    base = max(valor_base, Decimal('0')).quantize(Decimal('0.01'))
    divisor = Decimal('1') - aliquota_interna / Decimal('100')
    # Alíquota interna ≥ 100% só vem de erro de cadastro na tabela; cair na base única
    # mantém a emissão de pé em vez de estourar ZeroDivisionError no item.
    if usa_base_dupla and divisor > 0:
        v_icms_inter = base * aliquota_interestadual / Decimal('100')
        base_dupla = (base - v_icms_inter) / divisor
        difal = base_dupla * aliquota_interna / Decimal('100') - v_icms_inter
        return CalculoDifalBase(
            base_uf_dest=base_dupla.quantize(Decimal('0.01')),
            icms_uf_dest=max(difal, Decimal('0')).quantize(Decimal('0.01')),
            tipo_base='DUPLA',
        )

    difal_pct = max(aliquota_interna - aliquota_interestadual, Decimal('0'))
    return CalculoDifalBase(
        base_uf_dest=base,
        icms_uf_dest=(base * difal_pct / Decimal('100')).quantize(Decimal('0.01')),
        tipo_base='UNICA',
    )


def calcular_difal_item(
    valor_base: Decimal,
    regra: RegraFiscalSaida,
    *,
    aliquotas: AliquotasDifalResolvidas | None = None,
) -> dict[str, Any]:
    """Retorna snapshot DIFAL por item (valores monetários em string com 2 casas)."""
    ali_inter = (
        aliquotas.aliquota_interestadual
        if aliquotas is not None
        else _dec(regra.aliquota_icms_interestadual)
    )
    ali_dest = (
        aliquotas.aliquota_interna_destino
        if aliquotas is not None
        else _dec(regra.aliquota_icms_interna_destino)
    )
    usa_base_dupla = aliquotas.usa_base_dupla if aliquotas is not None else False
    calculo = calcular_difal_na_base(
        valor_base,
        aliquota_interestadual=ali_inter,
        aliquota_interna=ali_dest,
        usa_base_dupla=usa_base_dupla,
    )
    base = calculo.base_uf_dest
    v_icms_uf_dest = calculo.icms_uf_dest
    v_icms_uf_remet = Decimal('0')

    p_fcp = Decimal('0')
    v_fcp = Decimal('0')
    if regra.fcp_aplicavel:
        p_fcp = (
            aliquotas.aliquota_fcp
            if aliquotas is not None
            else _dec(regra.aliquota_fcp)
        )
        if p_fcp > 0:
            v_fcp = (base * p_fcp / Decimal('100')).quantize(Decimal('0.01'))

    snapshot = {
        'aplicavel': True,
        'tipo_base': calculo.tipo_base,
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
    if aliquotas is not None and aliquotas.fontes:
        snapshot['fontes_aliquota'] = ','.join(aliquotas.fontes)
    return snapshot


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
    imposto = det.imposto
    ufdest = (
        getattr(imposto, 'ICMSUFDest', None)
        or getattr(imposto, 'Icmsufdest', None)
        or getattr(imposto, 'icmsufdest', None)
    )
    if ufdest is not None:
        return ufdest
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
