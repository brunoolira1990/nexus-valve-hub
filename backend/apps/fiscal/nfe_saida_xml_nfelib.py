"""NF-e Saída 4.0.1 — XML oficial modelo 55 (layout NF-e 4.00) via nfelib + xsdata.

Rascunho/conferência: não transmite SEFAZ, não assina, não gera chave/protocolo oficiais.
O atributo Id usa prefixo NFePREVIEW{id} (não é chave de acesso válida).
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from apps.fiscal.nfe_cbenef_sp import (
    codigo_beneficio_icms_preenchido,
    normalizar_codigo_beneficio_icms,
)
from apps.fiscal.nfe_integracao.adapters.exceptions import NFeIntegracaoError
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_saida_preview import (
    MSG_PREVIEW_PENDENCIAS,
    MSG_XML_PREVIEW,
    _bloqueio_preview,
    _extrair_pendencias_alertas,
    _text,
    gerar_dados_preview_nfe_saida,
)
from apps.fiscal.snapshot_fiscal_helpers import (
    get_cofins_snapshot,
    get_difal_snapshot,
    get_icms_snapshot,
    get_ipi_snapshot,
    get_pis_snapshot,
)
from apps.fiscal.validacao_nfe_saida import STATUS_COM_PENDENCIAS, validar_nfe_saida_para_emissao

MSG_XML_OFICIAL = (
    'XML oficial NF-e 4.00 (nfelib) gerado para conferência. Não transmitir. Sem protocolo SEFAZ.'
)
XML_COMMENT_OFICIAL = (
    ' XML OFICIAL NF-e 4.00 (nfelib) — NÃO TRANSMITIR. Rascunho não autorizado. '
    'Id NFePREVIEW não é chave de acesso. Sem protocolo SEFAZ. '
)

PIS_COFINS_NT_CSTS = frozenset({'04', '05', '06', '07', '08', '09'})
IPI_NT_CSTS = frozenset({'52', '53', '54', '55'})


class NFeXmlNfelibError(NFeIntegracaoError):
    """Erro na montagem/serialização do XML oficial."""


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _dec_field(val: Any, places: int = 2) -> Decimal | None:
    d = _dec(val)
    if d == 0 and (val is None or str(val).strip() == ''):
        return None
    return d.quantize(Decimal(10) ** -places)


def _digits(val: str | None, *, max_len: int | None = None) -> str:
    d = ''.join(c for c in str(val or '') if c.isdigit())
    if max_len:
        return d[:max_len]
    return d


def _nnf_oficial(dados: dict[str, Any]) -> str:
    """nNF numérico exigido pelo leiaute (rascunho usa número interno ou pk)."""
    numero = _text(dados.get('numero'))
    digits = _digits(numero)
    if digits:
        return digits[:9]
    return str(dados.get('nfe_saida_id') or 1)[:9]


def _cnf_oficial(nfe_saida_id: int) -> str:
    return f'{int(nfe_saida_id) % 100000000:08d}'


def _id_preview(nfe_saida_id: int) -> str:
    return f'NFePREVIEW{int(nfe_saida_id)}'


def fone_nfe_digits(telefone: str | None) -> str | None:
    """Telefone NF-e (enderEmit/fone): somente dígitos, 8–14 caracteres."""
    digits = _digits(telefone, max_len=14)
    if len(digits) < 8:
        return None
    return digits


def _ender_emit(dados: dict[str, Any]):
    from nfelib.nfe.bindings.v4_0 import leiaute_nfe_v4_00 as layout

    emit = dados['emitente']
    fone = _text(emit.get('fone')) or fone_nfe_digits(emit.get('telefone'))
    c_mun = (
        _digits(emit.get('c_mun'), max_len=7)
        or _digits(dados['ide'].get('c_mun_fg'), max_len=7)
        or '3550308'
    )
    if c_mun == '3500000':
        from apps.fiscal.nfe_emissao.xml_serializacao import codigo_municipio_ibge

        c_mun = codigo_municipio_ibge(emit.get('uf'), cidade=emit.get('cidade'))
    return layout.TenderEmi(
        xLgr=_text(emit.get('logradouro')) or 'Não informado',
        nro=_text(emit.get('numero')) or 'S/N',
        xCpl=_text(emit.get('complemento')) or None,
        xBairro=_text(emit.get('bairro')) or None,
        cMun=c_mun,
        xMun=_text(emit.get('cidade')) or 'Não informado',
        UF=_text(emit.get('uf')) or 'SP',
        CEP=_digits(emit.get('cep'), max_len=8) or None,
        cPais='1058',
        xPais='Brasil',
        fone=fone or None,
    )


def _ender_dest(dados: dict[str, Any]):
    from nfelib.nfe.bindings.v4_0 import leiaute_nfe_v4_00 as layout
    from apps.fiscal.nfe_endereco_xml import resolver_c_mun_destinatario

    dest = dados['destinatario']
    c_mun = resolver_c_mun_destinatario(dest)
    return layout.Tendereco(
        xLgr=_text(dest.get('logradouro')) or 'Não informado',
        nro=_text(dest.get('numero')) or 'S/N',
        xCpl=_text(dest.get('complemento')) or None,
        xBairro=_text(dest.get('bairro')) or None,
        cMun=c_mun,
        xMun=_text(dest.get('cidade')) or 'Não informado',
        UF=_text(dest.get('uf')) or 'SP',
        CEP=_digits(dest.get('cep'), max_len=8) or None,
        cPais='1058',
        xPais='Brasil',
        fone=None,
    )


def _p_icms_inter_uf_dest_enum(p_icms_inter: Any) -> Any:
    """Enum XSD pICMSInter (4.00 / 7.00 / 12.00) para ICMSUFDest."""
    from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import IcmsufdestPIcmsinter

    val = _dec(p_icms_inter).quantize(Decimal('0.01'))
    for member in IcmsufdestPIcmsinter:
        if Decimal(member.value) == val:
            return member
    if val <= Decimal('4'):
        return IcmsufdestPIcmsinter.VALUE_4_00
    if val <= Decimal('7'):
        return IcmsufdestPIcmsinter.VALUE_7_00
    return IcmsufdestPIcmsinter.VALUE_12_00


def _icms_uf_dest_binding_target(nfe_module: Any) -> tuple[type | None, str]:
    """
    Localiza a classe ICMSUFDest no binding nfelib.

    NF-e 4.00 / nfelib >= 2.5: grupo fica em ``imposto/ICMSUFDest`` (irmão de ICMS).
  Legado: algumas versões aninhavam em ``ICMS/ICMSUFDest``.
    """
    imposto_cls = nfe_module.Tnfe.InfNfe.Det.Imposto
    item_cls = getattr(imposto_cls, 'Icmsufdest', None)
    if item_cls is not None:
        return item_cls, 'imposto'
    icms_cls = imposto_cls.Icms
    legacy_cls = getattr(icms_cls, 'ICMSUFDest', None) or getattr(icms_cls, 'Icmsufdest', None)
    if legacy_cls is not None:
        return legacy_cls, 'icms'
    return None, ''


def _build_icms_uf_dest(nfe_module: Any, snap: dict, linha: dict) -> tuple[Any | None, str]:
    """Monta ICMSUFDest (DIFAL/FCP destino) quando aplicável ao item."""
    from apps.fiscal.nfe_difal_calculo import valores_difal_item_xml
    from apps.fiscal.nfe_emissao.xml_serializacao import _dec_str
    from apps.fiscal.snapshot_fiscal_helpers import resolver_difal_snapshot_linha

    difal = resolver_difal_snapshot_linha(linha)
    valores = valores_difal_item_xml(difal)
    if valores is None:
        return None, ''

    item_cls, target = _icms_uf_dest_binding_target(nfe_module)
    if item_cls is None:
        raise NFeXmlNfelibError(
            'Binding nfelib sem grupo ICMSUFDest — não é possível serializar DIFAL/FCP no XML.',
        )

    v_bc_uf = _dec_str(difal.get('v_bc_uf_dest') or linha.get('v_prod'))
    kwargs: dict[str, Any] = {
        'vBCUFDest': v_bc_uf,
        'pICMSUFDest': _dec_str(difal.get('p_icms_uf_dest'), 4),
        'pICMSInter': _p_icms_inter_uf_dest_enum(difal.get('p_icms_inter')),
        'pICMSInterPart': _dec_str(difal.get('p_icms_inter_part') or '100', 4),
        'vICMSUFDest': _dec_str(valores['v_icms_uf_dest']),
        'vICMSUFRemet': _dec_str(valores['v_icms_uf_remet']),
    }
    p_fcp = _dec(difal.get('p_fcp_uf_dest'))
    v_fcp = valores['v_fcp_uf_dest']
    if p_fcp > 0 or v_fcp > 0:
        v_bc_fcp = _dec_str(difal.get('v_bc_fcp_uf_dest') or v_bc_uf)
        kwargs['vBCFCPUFDest'] = v_bc_fcp
        kwargs['pFCPUFDest'] = _dec_str(p_fcp, 4)
        kwargs['vFCPUFDest'] = _dec_str(v_fcp)
    return item_cls(**kwargs), target


def _build_icms(snap: dict, linha: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    icms = get_icms_snapshot(snap)
    cst = _text(icms.get('cst_icms') or icms.get('csosn')) or '00'
    cst = cst.zfill(2)[:2]
    orig = _text(snap.get('origem_mercadoria') or snap.get('orig') or '0') or '0'
    mod_bc = _text(icms.get('modalidade_bc')) or '3'
    icms_wrap = nfe.Tnfe.InfNfe.Det.Imposto.Icms()

    if cst in ('40', '41', '50'):
        icms_wrap.ICMS40 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms40(orig=orig, CST=cst)
    elif cst == '60':
        icms_wrap.ICMS60 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms60(orig=orig, CST=cst)
    elif cst == '20':
        v_bc = _dec(icms.get('base') or linha.get('v_prod'))
        p_icms = _dec(icms.get('aliquota'))
        v_icms = _dec(icms.get('valor'))
        p_red_bc = _dec(icms.get('reducao_bc'))
        icms20_kwargs: dict[str, Any] = {
            'orig': orig,
            'CST': cst,
            'modBC': mod_bc,
            'vBC': v_bc,
            'pICMS': p_icms,
            'vICMS': v_icms,
        }
        if p_red_bc > 0:
            icms20_kwargs['pRedBC'] = p_red_bc
        mot_des = _text(icms.get('motivo_desoneracao'))
        v_icms_deson = _dec(icms.get('valor_icms_deson'))
        if mot_des and v_icms_deson > 0:
            icms20_kwargs['vICMSDeson'] = v_icms_deson
            icms20_kwargs['motDesICMS'] = mot_des[:2]
        icms_wrap.ICMS20 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms20(**icms20_kwargs)
    else:
        v_bc = _dec(icms.get('base') or linha.get('v_prod'))
        p_icms = _dec(icms.get('aliquota'))
        v_icms = _dec(icms.get('valor'))
        icms_wrap.ICMS00 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms00(
            orig=orig,
            CST=cst,
            modBC=mod_bc,
            vBC=v_bc,
            pICMS=p_icms,
            vICMS=v_icms,
        )

    return icms_wrap


def _build_pis(snap: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    pis = get_pis_snapshot(snap)
    cst = _text(pis.get('cst')) or '08'
    wrap = nfe.Tnfe.InfNfe.Det.Imposto.Pis()
    if cst in PIS_COFINS_NT_CSTS:
        wrap.PISNT = nfe.Tnfe.InfNfe.Det.Imposto.Pis.Pisnt(CST=cst)
    else:
        wrap.PISAliq = nfe.Tnfe.InfNfe.Det.Imposto.Pis.Pisaliq(
            CST=cst,
            vBC=_dec_field(pis.get('base')),
            pPIS=_dec_field(pis.get('aliquota'), 4),
            vPIS=_dec_field(pis.get('valor')),
        )
    return wrap


def _build_cofins(snap: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    cof = get_cofins_snapshot(snap)
    cst = _text(cof.get('cst')) or '08'
    wrap = nfe.Tnfe.InfNfe.Det.Imposto.Cofins()
    if cst in PIS_COFINS_NT_CSTS:
        wrap.COFINSNT = nfe.Tnfe.InfNfe.Det.Imposto.Cofins.Cofinsnt(CST=cst)
    else:
        wrap.COFINSAliq = nfe.Tnfe.InfNfe.Det.Imposto.Cofins.Cofinsaliq(
            CST=cst,
            vBC=_dec_field(cof.get('base')),
            pCOFINS=_dec_field(cof.get('aliquota'), 4),
            vCOFINS=_dec_field(cof.get('valor')),
        )
    return wrap


def _build_ipi(snap: dict):
    from nfelib.nfe.bindings.v4_0 import leiaute_nfe_v4_00 as layout

    ipi = get_ipi_snapshot(snap)
    cst = _text(ipi.get('cst'))
    if not cst and not _dec(ipi.get('valor')) and not _dec(ipi.get('aliquota')):
        return None
    wrap = layout.Tipi(cEnq='999')
    if cst in IPI_NT_CSTS:
        wrap.ipint = layout.Tipi.Ipint(CST=cst)
    else:
        wrap.ipitrib = layout.Tipi.Ipitrib(
            CST=cst or '50',
            vBC=_dec_field(ipi.get('base')),
            pIPI=_dec_field(ipi.get('aliquota'), 4),
            vIPI=_dec_field(ipi.get('valor')),
        )
    return wrap


def _build_det(linha: dict) -> Any:
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    snap = linha.get('snapshot_fiscal') or {}
    q = _dec(linha.get('q_com'))
    prod = nfe.Tnfe.InfNfe.Det.Prod(
        cProd=_text(linha.get('c_prod'))[:60] or str(linha.get('item_id')),
        cEAN='SEM GTIN',
        xProd=_text(linha.get('x_prod'))[:120] or 'Item',
        NCM=_digits(linha.get('ncm'), max_len=8) or '00000000',
        CFOP=_digits(linha.get('cfop'), max_len=4) or '5102',
        uCom=_text(linha.get('u_com'))[:6] or 'UN',
        qCom=q,
        vUnCom=_dec(linha.get('v_un_com')),
        vProd=_dec(linha.get('v_prod')),
        uTrib=_text(linha.get('u_com'))[:6] or 'UN',
        qTrib=q,
        vUnTrib=_dec(linha.get('v_un_com')),
        cEANTrib='SEM GTIN',
        indTot='1',
    )
    cest = _digits(linha.get('cest'), max_len=7)
    if cest:
        prod.CEST = cest

    icms_snap = get_icms_snapshot(snap)
    c_benef = normalizar_codigo_beneficio_icms(icms_snap.get('codigo_beneficio'))
    if codigo_beneficio_icms_preenchido(c_benef):
        prod.cBenef = c_benef[:16]

    x_ped = _text(linha.get('x_ped'))
    n_item_ped = _text(linha.get('n_item_ped'))
    if not x_ped and not n_item_ped:
        from apps.fiscal.nfe_integracao.danfe_xml_adicionais import resolver_xped_nitemped_item

        x_ped, n_item_ped = resolver_xped_nitemped_item(None, linha)
    if x_ped:
        prod.xPed = x_ped[:15]
    if n_item_ped:
        prod.nItemPed = n_item_ped[:6]

    ipi = _build_ipi(snap)
    from apps.fiscal.reforma_tributaria.xml import build_reforma_tributaria_item_bindings
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    icms_wrap = _build_icms(snap, linha)
    icms_uf_dest, uf_dest_target = _build_icms_uf_dest(nfe, snap, linha)
    if uf_dest_target == 'icms' and icms_uf_dest is not None:
        icms_wrap.ICMSUFDest = icms_uf_dest

    imposto_kw: dict[str, Any] = {
        'ICMS': icms_wrap,
        'PIS': _build_pis(snap),
        'COFINS': _build_cofins(snap),
        'IPI': ipi,
    }
    if uf_dest_target == 'imposto' and icms_uf_dest is not None:
        imposto_kw['ICMSUFDest'] = icms_uf_dest
    ibscbs = build_reforma_tributaria_item_bindings(linha)
    if ibscbs is not None:
        imposto_kw['IBSCBS'] = ibscbs
    imposto = nfe.Tnfe.InfNfe.Det.Imposto(**imposto_kw)

    det_kw: dict[str, Any] = {
        'nItem': str(linha.get('n_item')),
        'prod': prod,
        'imposto': imposto,
    }
    inf_ad_prod = _text(linha.get('inf_ad_prod'))
    if inf_ad_prod:
        det_kw['infAdProd'] = inf_ad_prod[:500]
    return nfe.Tnfe.InfNfe.Det(**det_kw)


def preparar_dados_serializacao_xml(dados: dict[str, Any]) -> None:
    """Enriquece municípios e bloqueia endereço fiscal inconsistente do destinatário."""
    from apps.fiscal.nfe_endereco_xml import enriquecer_municipios_dados_nfe, validar_c_mun_destinatario

    enriquecer_municipios_dados_nfe(dados)
    erros = validar_c_mun_destinatario(dados)
    if erros:
        raise NFeXmlNfelibError(erros[0])


def build_total_nfe_bindings(nfe_module: Any, dados: dict[str, Any]) -> Any:
    """Monta bloco ``Total`` (ICMSTot + IBSCBSTot quando aplicável) — camada central."""
    from apps.fiscal.nfe_emissao.xml_serializacao import build_icms_tot_bindings
    from apps.fiscal.reforma_tributaria.xml import build_reforma_tributaria_total_bindings

    tot = dados.get('totais') or {}
    total_kw: dict[str, Any] = {'ICMSTot': build_icms_tot_bindings(nfe_module, tot)}
    ibscbs_tot = build_reforma_tributaria_total_bindings(dados.get('itens') or [])
    if ibscbs_tot is not None:
        total_kw['IBSCBSTot'] = ibscbs_tot
    return nfe_module.Tnfe.InfNfe.Total(**total_kw)


def montar_tnfe_oficial(dados: dict[str, Any], *, nfe_saida: NFeSaida | None = None) -> Any:
    """Monta ``Tnfe`` nfelib a partir dos dados normalizados do preview."""
    if not nfelib_disponivel():
        raise NFeXmlNfelibError('nfelib não está instalado no ambiente.')

    preparar_dados_serializacao_xml(dados)

    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    ide_map = dados['ide']
    inf = nfe.Tnfe.InfNfe(versao='4.00')
    inf.Id = _id_preview(int(dados['nfe_saida_id']))

    dh_emi = _text(ide_map.get('dh_emi'))
    if dh_emi and len(dh_emi) > 19:
        dh_emi = dh_emi[:25]

    inf.ide = nfe.Tnfe.InfNfe.Ide(
        cUF=_text(ide_map.get('c_uf')) or '35',
        cNF=_cnf_oficial(int(dados['nfe_saida_id'])),
        natOp=_text(ide_map.get('nat_op'))[:60] or 'Venda',
        mod='55',
        serie='0',
        nNF=_nnf_oficial(dados),
        dhEmi=dh_emi or None,
        tpNF=_text(ide_map.get('tp_nf')) or '1',
        idDest=_text(ide_map.get('id_dest')) or '1',
        cMunFG=_digits(ide_map.get('c_mun_fg'), max_len=7) or '3550308',
        tpImp='1',
        tpEmis='1',
        cDV='0',
        tpAmb='2',
        finNFe='1',
        indFinal='1',
        indPres='1',
        indIntermed='0',
        procEmi='0',
        verProc='NexusERP-4.0.1',
    )

    emit = dados['emitente']
    inf.emit = nfe.Tnfe.InfNfe.Emit(
        CNPJ=_digits(emit.get('cnpj'), max_len=14) or None,
        xNome=_text(emit.get('x_nome'))[:60] or 'Emitente',
        IE=_text(emit.get('ie'))[:14] or None,
        CRT=_text(emit.get('crt')) or '3',
    )
    inf.emit.enderEmit = _ender_emit(dados)

    dest = dados['destinatario']
    doc = _digits(dest.get('cnpj'))
    dest_kw: dict[str, Any] = {
        'xNome': _text(dest.get('x_nome'))[:60] or 'Destinatário',
        'indIEDest': _text(dest.get('ind_ie_dest')) or ('1' if _text(dest.get('ie')) else '9'),
    }
    if len(doc) == 14:
        dest_kw['CNPJ'] = doc
    elif len(doc) == 11:
        dest_kw['CPF'] = doc
    elif doc:
        dest_kw['CNPJ'] = doc
    if _text(dest.get('ie')):
        dest_kw['IE'] = _text(dest.get('ie'))[:14]
    inf.dest = nfe.Tnfe.InfNfe.Dest(**dest_kw)
    inf.dest.enderDest = _ender_dest(dados)

    if nfe_saida is not None:
        from apps.fiscal.nfe_integracao.danfe_xml_adicionais import enriquecer_linhas_xml_nfe

        enriquecer_linhas_xml_nfe(nfe_saida, dados)

    inf.det = [_build_det(linha) for linha in dados.get('itens') or []]
    if not inf.det:
        raise NFeXmlNfelibError('NF-e sem itens: não é possível gerar XML oficial.')

    from apps.fiscal.nfe_difal_calculo import aplicar_totais_difal_em_dados

    aplicar_totais_difal_em_dados(dados, det_list=inf.det)
    inf.total = build_total_nfe_bindings(nfe, dados)

    from apps.fiscal.nfe_transp_bindings import aplicar_transp_nfelib

    aplicar_transp_nfelib(inf, nfe, dados.get('transporte'))

    inf_adic_kw: dict[str, Any] = {}
    if nfe_saida:
        from apps.fiscal.nfe_integracao.danfe_xml_adicionais import montar_inf_cpl_nfe

        itens_db = {it.pk: it for it in nfe_saida.itens.all()}
        inf_cpl, inf_fisco = montar_inf_cpl_nfe(nfe_saida, dados, itens_db=itens_db)
        if inf_cpl:
            inf_adic_kw['infCpl'] = inf_cpl
        if inf_fisco:
            inf_adic_kw['infAdFisco'] = inf_fisco
    elif dados.get('observacoes'):
        inf_adic_kw['infCpl'] = _text(dados['observacoes'])[:5000]
    if inf_adic_kw:
        inf.infAdic = nfe.Tnfe.InfNfe.InfAdic(**inf_adic_kw)

    return nfe.Tnfe(infNFe=inf)


def serializar_tnfe(tnfe: Any, *, pretty: bool = True) -> str:
    from xsdata.formats.dataclass.serializers import XmlSerializer
    from xsdata.formats.dataclass.serializers.config import SerializerConfig

    body = XmlSerializer(
        config=SerializerConfig(
            pretty_print=pretty,
            xml_declaration=False,
        ),
    ).render(tnfe)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!--{XML_COMMENT_OFICIAL}-->\n{body}'


def _enriquecer_totais_impostos(dados: dict[str, Any]) -> None:
    """Agrega totais de impostos a partir dos snapshots dos itens."""
    from apps.fiscal.nfe_difal_calculo import aplicar_totais_difal_em_dados

    v_bc = v_icms = v_pis = v_cofins = v_ipi = Decimal('0')
    for linha in dados.get('itens') or []:
        snap = linha.get('snapshot_fiscal') or {}
        icms = get_icms_snapshot(snap)
        pis = get_pis_snapshot(snap)
        cof = get_cofins_snapshot(snap)
        ipi = get_ipi_snapshot(snap)
        v_bc += _dec(icms.get('base'))
        v_icms += _dec(icms.get('valor'))
        v_pis += _dec(pis.get('valor'))
        v_cofins += _dec(cof.get('valor'))
        v_ipi += _dec(ipi.get('valor'))
    tot = dict(dados.get('totais') or {})
    if v_bc:
        tot.setdefault('v_bc', f'{v_bc:.2f}')
    if v_icms:
        tot.setdefault('v_icms', f'{v_icms:.2f}')
    if v_pis:
        tot.setdefault('v_pis', f'{v_pis:.2f}')
    if v_cofins:
        tot.setdefault('v_cofins', f'{v_cofins:.2f}')
    if v_ipi:
        tot.setdefault('v_ipi', f'{v_ipi:.2f}')
    dados['totais'] = tot
    aplicar_totais_difal_em_dados(dados)


def gerar_xml_oficial_nfe_saida(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Gera XML NF-e 4.00 oficial (nfelib) para conferência — sem transmitir."""
    bloqueio = _bloqueio_preview(nfe_saida)
    if bloqueio:
        return {**bloqueio, 'nfe_saida_id': nfe_saida.pk, 'numero': nfe_saida.numero, 'status': nfe_saida.status}

    dados = gerar_dados_preview_nfe_saida(nfe_saida)
    if dados.get('bloqueado'):
        return dados

    validacao = validar_nfe_saida_para_emissao(nfe_saida)
    pendencias, alertas = _extrair_pendencias_alertas(validacao)

    itens_payload = []
    for linha in dados.get('itens') or []:
        item_id = linha.get('item_id')
        if item_id:
            from apps.fiscal.models import ItemNFeSaida

            try:
                item = ItemNFeSaida.objects.get(pk=item_id, nf=nfe_saida)
                linha['snapshot_fiscal'] = item.snapshot_fiscal or {}
            except ItemNFeSaida.DoesNotExist:
                linha['snapshot_fiscal'] = linha.get('snapshot_fiscal') or {}
        itens_payload.append(linha)
    dados['itens'] = itens_payload
    from apps.fiscal.nfe_integracao.danfe_xml_adicionais import enriquecer_linhas_xml_nfe

    enriquecer_linhas_xml_nfe(nfe_saida, dados)
    _enriquecer_totais_impostos(dados)
    preparar_dados_serializacao_xml(dados)

    from apps.fiscal.nfe_difal_calculo import NFeDifalXmlInconsistenteError

    try:
        tnfe = montar_tnfe_oficial(dados, nfe_saida=nfe_saida)
        xml = serializar_tnfe(tnfe)
    except NFeXmlNfelibError:
        raise
    except NFeDifalXmlInconsistenteError as exc:
        raise NFeXmlNfelibError(str(exc)) from exc
    except Exception as exc:
        raise NFeXmlNfelibError(f'Falha ao gerar XML oficial: {exc}') from exc

    return {
        'nfe_saida_id': nfe_saida.pk,
        'numero': nfe_saida.numero,
        'status': nfe_saida.status,
        'preview': True,
        'oficial': True,
        'bloqueado': False,
        'xml': xml,
        'xml_format': 'nfelib_4.00',
        'versao_layout': '4.00',
        'id_preview': _id_preview(nfe_saida.pk),
        'status_prontidao': validacao.get('status_prontidao'),
        'pode_emitir': validacao.get('pode_emitir'),
        'pendencias': pendencias,
        'alertas': alertas,
        'avisos': list(dados.get('avisos') or []) + [MSG_XML_OFICIAL],
        'mensagens': [MSG_XML_OFICIAL]
        + ([MSG_PREVIEW_PENDENCIAS] if validacao.get('status_prontidao') == STATUS_COM_PENDENCIAS else []),
        'marcas_preview': dados.get('marcas_preview', [])
        + ['XML oficial nfelib 4.00', 'Não transmitir'],
    }
