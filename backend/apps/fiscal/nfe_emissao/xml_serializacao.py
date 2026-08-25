"""Serialização e normalização do XML NF-e 4.00 para schema SEFAZ."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

NFE_NS = 'http://www.portalfiscal.inf.br/nfe'
TZ_SP = ZoneInfo('America/Sao_Paulo')

# Capitais IBGE (fallback quando cadastro não tem código do município)
UF_MUNICIPIO_CAPITAL: dict[str, str] = {
    'AC': '1200401',
    'AL': '2704302',
    'AP': '1600303',
    'AM': '1302603',
    'BA': '2927408',
    'CE': '2304400',
    'DF': '5300108',
    'ES': '3205309',
    'GO': '5208707',
    'MA': '2111300',
    'MT': '5103403',
    'MS': '5002704',
    'MG': '3106200',
    'PA': '1501402',
    'PB': '2507507',
    'PR': '4106902',
    'PE': '2611606',
    'PI': '2211001',
    'RJ': '3304557',
    'RN': '2408102',
    'RS': '4314902',
    'RO': '1100205',
    'RR': '1400100',
    'SC': '4205407',
    'SP': '3550308',
    'SE': '2800308',
    'TO': '1721000',
}


def codigo_municipio_ibge(uf: str | None, *, cidade: str | None = None) -> str:
    """Retorna código IBGE de 7 dígitos; evita placeholder inválido (ex.: 3500000)."""
    uf_u = (uf or 'SP').strip().upper()[:2]
    if cidade:
        cid = cidade.strip().upper()
        if cid == 'ITUPEVA' and uf_u == 'SP':
            return '3524006'
        if cid in ('SAO PAULO', 'SÃO PAULO') and uf_u == 'SP':
            return '3550308'
        if cid == 'BELEM' and uf_u == 'PA':
            return '1501402'
    return UF_MUNICIPIO_CAPITAL.get(uf_u, '3550308')


def formatar_dh_emi(dt: datetime | None = None) -> str:
    """Data/hora de emissão com fuso -03:00 (exigência schema NF-e 4.00)."""
    valor = dt or timezone.now()
    if timezone.is_naive(valor):
        valor = timezone.make_aware(valor, timezone.get_current_timezone())
    valor_sp = valor.astimezone(TZ_SP)
    offset = valor_sp.strftime('%z')
    if len(offset) == 5:
        offset = f'{offset[:3]}:{offset[3:]}'
    return f'{valor_sp.strftime("%Y-%m-%dT%H:%M:%S")}{offset}'


def _dec_str(val: Any, places: int = 2) -> str:
    from decimal import Decimal

    if val is None or val == '':
        return '0.00'
    try:
        d = Decimal(str(val).replace(',', '.'))
    except Exception:
        return '0.00'
    q = Decimal(10) ** -places
    return str(d.quantize(q))


def build_icms_tot_bindings(nfe_module: Any, tot: dict[str, Any]) -> Any:
    """ICMSTot com todos os campos obrigatórios zerados quando ausentes."""
    Icmstot = nfe_module.Tnfe.InfNfe.Total.Icmstot
    z = '0.00'
    v_fcp_uf_dest = _dec_str(tot.get('v_fcp_uf_dest'))
    v_icms_uf_dest = _dec_str(tot.get('v_icms_uf_dest'))
    v_icms_uf_remet = _dec_str(tot.get('v_icms_uf_remet'))
    return Icmstot(
        vBC=_dec_str(tot.get('v_bc')),
        vICMS=_dec_str(tot.get('v_icms')),
        vICMSDeson=z,
        vFCP=z,
        vBCST=z,
        vST=z,
        vFCPST=z,
        vFCPSTRet=z,
        vProd=_dec_str(tot.get('v_prod')),
        vFrete=_dec_str(tot.get('v_frete')),
        vSeg=z,
        vDesc=_dec_str(tot.get('v_desc')),
        vII=z,
        vIPI=_dec_str(tot.get('v_ipi')),
        vIPIDevol=_dec_str(tot.get('v_ipi_devol')),
        vPIS=_dec_str(tot.get('v_pis')),
        vCOFINS=_dec_str(tot.get('v_cofins')),
        vOutro=z,
        vNF=_dec_str(tot.get('v_nf')),
        vFCPUFDest=v_fcp_uf_dest if v_fcp_uf_dest != z else z,
        vICMSUFDest=v_icms_uf_dest if v_icms_uf_dest != z else z,
        vICMSUFRemet=v_icms_uf_remet if v_icms_uf_remet != z else z,
    )


def build_pag_bindings(
    nfe_module: Any,
    tot: dict[str, Any],
    *,
    duplicatas: list[dict[str, Any]] | None = None,
    fin_nfe: str | None = None,
) -> Any:
    """Grupo pag obrigatório NF-e 4.00.

    - finNFe 3 (ajuste) ou 4 (devolução): tPag 90 (Sem Pagamento) e vPag 0.00
      (rejeições SEFAZ 871 / 904 — NT 2016.002).
    - demais: à vista tPag 01; a prazo tPag 15 (boleto).
    """
    DetPag = nfe_module.Tnfe.InfNfe.Pag.DetPag
    fin = str(fin_nfe or '').strip()
    if fin in ('3', '4'):
        return nfe_module.Tnfe.InfNfe.Pag(
            detPag=[DetPag(tPag='90', vPag='0.00')],
        )
    v_nf = _dec_str(tot.get('v_nf'))
    t_pag = '15' if duplicatas else '01'
    return nfe_module.Tnfe.InfNfe.Pag(
        detPag=[DetPag(tPag=t_pag, vPag=v_nf)],
    )


def build_cobr_bindings(
    nfe_module: Any,
    tot: dict[str, Any],
    duplicatas: list[dict[str, Any]],
    *,
    n_fat: str = '',
) -> Any | None:
    """Grupo cobr (fatura/duplicatas) quando há parcelas a prazo."""
    if not duplicatas:
        return None

    v_nf = _dec_str(tot.get('v_nf'))
    v_desc = _dec_str(tot.get('v_desc'))
    Fat = nfe_module.Tnfe.InfNfe.Cobr.Fat
    Dup = nfe_module.Tnfe.InfNfe.Cobr.Dup

    dups_xml = []
    for dup in duplicatas:
        v_dup = _dec_str(dup.get('valor'))
        if v_dup in ('0.00', '0'):
            continue
        venc = str(dup.get('vencimento') or '')[:10]
        if not venc:
            continue
        dups_xml.append(
            Dup(
                nDup=str(dup.get('numero') or len(dups_xml) + 1)[:60],
                dVenc=venc,
                vDup=v_dup,
            ),
        )
    if not dups_xml:
        return None

    return nfe_module.Tnfe.InfNfe.Cobr(
        fat=Fat(
            nFat=(n_fat or '1')[:60],
            vOrig=v_nf,
            vDesc=v_desc,
            vLiq=v_nf,
        ),
        dup=dups_xml,
    )


def ie_apenas_digitos(ie: str | None) -> str:
    return ''.join(c for c in str(ie or '') if c.isdigit())[:14]


def serializar_tnfe_nfe(tnfe: Any) -> str:
    """Serializa Tnfe e normaliza para `<NFe xmlns=...>`."""
    from xsdata.formats.dataclass.serializers import XmlSerializer
    from xsdata.formats.dataclass.serializers.config import SerializerConfig

    body = XmlSerializer(
        config=SerializerConfig(pretty_print=False, xml_declaration=False),
    ).render(tnfe)
    xml = f'<?xml version="1.0" encoding="UTF-8"?>{body}'
    return normalizar_xml_nfe(xml)


def normalizar_xml_nfe(xml: str) -> str:
    """
    Converte saída xsdata (TNFe + prefixo ns0) para NFe com namespace default SEFAZ.
    """
    from lxml import etree

    if not xml.strip():
        return xml

    raw = xml.strip()
    if raw.startswith('<?xml'):
        raw = raw.split('?>', 1)[-1].lstrip()

    root = etree.fromstring(raw.encode('utf-8'))
    local = _local_tag(root.tag)

    if local == 'NFe' and root.nsmap.get(None) == NFE_NS:
        from apps.fiscal.nfe_emissao.xml_compactacao import normalizar_xml_para_assinatura_nfe

        return normalizar_xml_para_assinatura_nfe(
            serializar_elemento_compacto(root, com_declaracao=True),
        ).decode('utf-8')

    inf = None
    if local in ('TNFe', 'NFe'):
        for child in root:
            if _local_tag(child.tag) == 'infNFe':
                inf = child
                break
    elif local == 'infNFe':
        inf = root

    if inf is None:
        return xml

    if inf.get('Id') and not str(inf.get('Id', '')).startswith('NFe'):
        inf.set('Id', f'NFe{inf.get("Id")}')

    for attr in list(inf.attrib):
        if attr in ('xmlns', 'xmlns:ns0') or attr.startswith('{') and 'xmlns' in attr:
            del inf.attrib[attr]

    nfe_root = etree.Element(f'{{{NFE_NS}}}NFe', nsmap={None: NFE_NS})
    nfe_root.append(inf)

    sig = root.find('.//{http://www.w3.org/2000/09/xmldsig#}Signature')
    if sig is None:
        sig = root.find('.//{*}Signature')
    if sig is not None:
        parent = sig.getparent()
        if parent is not None:
            parent.remove(sig)
        nfe_root.append(sig)

    from apps.fiscal.nfe_emissao.xml_compactacao import normalizar_xml_para_assinatura_nfe

    return normalizar_xml_para_assinatura_nfe(
        serializar_elemento_compacto(nfe_root, com_declaracao=True),
    ).decode('utf-8')


def serializar_elemento_compacto(element, *, com_declaracao: bool = True) -> bytes:
    from apps.fiscal.nfe_emissao.xml_compactacao import serializar_elemento_compacto as _serializar

    return _serializar(element, com_declaracao=com_declaracao)


def _local_tag(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def xml_contem_grupo_pag(xml: str) -> bool:
    return bool(re.search(r'<[\w:]*pag\b', xml, flags=re.IGNORECASE))


def xml_root_e_nfe(xml: str) -> bool:
    return bool(re.search(r'<NFe\s+xmlns=["\']http://www\.portalfiscal\.inf\.br/nfe["\']', xml))
