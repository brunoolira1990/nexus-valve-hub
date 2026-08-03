"""XML oficial NF-e 4.00 entrada própria (tpNF=0) — sem assinatura/transmissão."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import NFeEntrada
from apps.fiscal.nfe_emissao.serie_fiscal import normalizar_serie_xml, validar_serie_autorizacao_normal
from apps.fiscal.nfe_emissao.xml_serializacao import (
    build_icms_tot_bindings,
    build_pag_bindings,
    codigo_municipio_ibge,
    formatar_dh_emi,
    ie_apenas_digitos,
    serializar_tnfe_nfe,
)
from apps.fiscal.nfe_entrada_emissao.dados_preview import gerar_dados_preview_nfe_entrada
from apps.fiscal.nfe_entrada_emissao.validacao import (
    validar_pre_emissao_homologacao_entrada,
    validar_pre_emissao_producao_entrada,
)
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe
from apps.fiscal.nfe_saida_preview import _digits, _text

HOMOLOG_DEST_XNOME = 'NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL'
VERSAO_PROC = 'NexusERP-4.0.15-entrada'
MSG_XML_ENTRADA = 'XML oficial NF-e entrada própria (tpNF=0).'

PIS_COFINS_NT_CSTS = frozenset({'04', '05', '06', '07', '08', '09'})
PIS_COFINS_ALIQ_CSTS = frozenset({'01', '02'})
ICMS_NT_CSTS = frozenset({'40', '41', '50', '60'})
IPI_NT_CSTS = frozenset({'01', '02', '03', '04', '05', '51', '52', '53', '54', '55', '49'})


class NFeEntradaXmlError(ValueError):
    pass


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


def _nnf_xml(nnf: str) -> str:
    digits = ''.join(c for c in str(nnf) if c.isdigit())
    if not digits:
        return '1'
    return str(int(digits))


def _build_icms_entrada(impostos: dict, linha: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    icms = impostos.get('icms') or {}
    cst = (_text(icms.get('cst') or icms.get('cst_icms') or icms.get('csosn')) or '00').zfill(2)[:2]
    orig = _text(icms.get('orig')) or '0'
    mod_bc = _text(icms.get('modalidade_bc')) or '3'
    wrap = nfe.Tnfe.InfNfe.Det.Imposto.Icms()
    if cst == '40':
        wrap.ICMS40 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms40(orig=orig, CST=cst)
    elif cst == '41':
        wrap.ICMS41 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms41(orig=orig, CST=cst)
    elif cst == '50':
        wrap.ICMS50 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms50(orig=orig, CST=cst)
    elif cst == '60':
        wrap.ICMS60 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms60(orig=orig, CST=cst)
    elif cst == '20':
        p_red = _dec(icms.get('reducao_bc') or icms.get('p_red_bc') or icms.get('pRedBC'))
        kwargs: dict[str, Any] = {
            'orig': orig,
            'CST': cst,
            'modBC': mod_bc,
            'vBC': _dec_field(icms.get('base')) or _dec(linha.get('v_prod')),
            'pICMS': _dec_field(icms.get('aliquota')),
            'vICMS': _dec_field(icms.get('valor')),
        }
        if p_red > 0:
            kwargs['pRedBC'] = p_red
        wrap.ICMS20 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms20(**kwargs)
    elif cst in ICMS_NT_CSTS:
        raise NFeEntradaXmlError(f'CST ICMS {cst} ainda não mapeado no builder de entrada.')
    else:
        wrap.ICMS00 = nfe.Tnfe.InfNfe.Det.Imposto.Icms.Icms00(
            orig=orig,
            CST=cst,
            modBC=mod_bc,
            vBC=_dec_field(icms.get('base')),
            pICMS=_dec_field(icms.get('aliquota')),
            vICMS=_dec_field(icms.get('valor')),
        )
    return wrap


def _build_pis_entrada(impostos: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    pis = impostos.get('pis') or {}
    cst = _text(pis.get('cst'))
    wrap = nfe.Tnfe.InfNfe.Det.Imposto.Pis()
    if cst in PIS_COFINS_NT_CSTS:
        wrap.PISNT = nfe.Tnfe.InfNfe.Det.Imposto.Pis.Pisnt(CST=cst)
    elif cst in PIS_COFINS_ALIQ_CSTS:
        wrap.PISAliq = nfe.Tnfe.InfNfe.Det.Imposto.Pis.Pisaliq(
            CST=cst,
            vBC=_dec_field(pis.get('base')),
            pPIS=_dec_field(pis.get('aliquota'), 4),
            vPIS=_dec_field(pis.get('valor')),
        )
    else:
        # CST 49/50/98/99… → PISOutr (ex.: devolução Lucro Presumido CST 98)
        wrap.PISOutr = nfe.Tnfe.InfNfe.Det.Imposto.Pis.Pisoutr(
            CST=cst or '98',
            vBC=_dec_field(pis.get('base')),
            pPIS=_dec_field(pis.get('aliquota'), 4),
            vPIS=_dec_field(pis.get('valor')),
        )
    return wrap


def _build_cofins_entrada(impostos: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    cof = impostos.get('cofins') or {}
    cst = _text(cof.get('cst'))
    wrap = nfe.Tnfe.InfNfe.Det.Imposto.Cofins()
    if cst in PIS_COFINS_NT_CSTS:
        wrap.COFINSNT = nfe.Tnfe.InfNfe.Det.Imposto.Cofins.Cofinsnt(CST=cst)
    elif cst in PIS_COFINS_ALIQ_CSTS:
        wrap.COFINSAliq = nfe.Tnfe.InfNfe.Det.Imposto.Cofins.Cofinsaliq(
            CST=cst,
            vBC=_dec_field(cof.get('base')),
            pCOFINS=_dec_field(cof.get('aliquota'), 4),
            vCOFINS=_dec_field(cof.get('valor')),
        )
    else:
        wrap.COFINSOutr = nfe.Tnfe.InfNfe.Det.Imposto.Cofins.Cofinsoutr(
            CST=cst or '98',
            vBC=_dec_field(cof.get('base')),
            pCOFINS=_dec_field(cof.get('aliquota'), 4),
            vCOFINS=_dec_field(cof.get('valor')),
        )
    return wrap


def _build_ipi_entrada(impostos: dict):
    from nfelib.nfe.bindings.v4_0 import leiaute_nfe_v4_00 as layout

    ipi = impostos.get('ipi') if isinstance(impostos.get('ipi'), dict) else {}
    cst = _text(ipi.get('cst'))
    if not cst and not _dec(ipi.get('valor')) and not _dec(ipi.get('aliquota')):
        return None
    wrap = layout.Tipi(cEnq='999')
    if cst in IPI_NT_CSTS or not _dec(ipi.get('valor')):
        wrap.IPINT = layout.Tipi.Ipint(CST=cst or '49')
    else:
        wrap.IPITrib = layout.Tipi.Ipitrib(
            CST=cst or '00',
            vBC=_dec_field(ipi.get('base')),
            pIPI=_dec_field(ipi.get('aliquota'), 4),
            vIPI=_dec_field(ipi.get('valor')),
        )
    return wrap


def _build_imposto_devol_entrada(impostos: dict):
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    devol = impostos.get('imposto_devol') if isinstance(impostos.get('imposto_devol'), dict) else {}
    v_ipi_devol = _dec_field(devol.get('v_ipi_devol') or devol.get('vIPIDevol'))
    if v_ipi_devol is None or v_ipi_devol <= 0:
        return None
    p_devol = _dec_field(devol.get('p_devol') or devol.get('pDevol'), 2) or Decimal('100.00')
    return nfe.Tnfe.InfNfe.Det.ImpostoDevol(
        pDevol=p_devol,
        IPI=nfe.Tnfe.InfNfe.Det.ImpostoDevol.Ipi(vIPIDevol=v_ipi_devol),
    )


def _build_det_entrada(linha: dict) -> Any:
    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe
    from apps.fiscal.reforma_tributaria.xml import build_reforma_tributaria_item_bindings

    impostos = linha.get('impostos_json') or {}
    q = _dec(linha.get('q_com'))
    prod = nfe.Tnfe.InfNfe.Det.Prod(
        cProd=_text(linha.get('c_prod'))[:60],
        cEAN='SEM GTIN',
        xProd=_text(linha.get('x_prod'))[:120],
        NCM=_digits(linha.get('ncm'), max_len=8),
        CFOP=_digits(linha.get('cfop'), max_len=4),
        uCom=_text(linha.get('u_com'))[:6],
        qCom=q,
        vUnCom=_dec(linha.get('v_un_com')),
        vProd=_dec(linha.get('v_prod')),
        uTrib=_text(linha.get('u_com'))[:6],
        qTrib=q,
        vUnTrib=_dec(linha.get('v_un_com')),
        cEANTrib='SEM GTIN',
        indTot='1',
    )
    imposto_kw: dict[str, Any] = {
        'ICMS': _build_icms_entrada(impostos, linha),
        'PIS': _build_pis_entrada(impostos),
        'COFINS': _build_cofins_entrada(impostos),
    }
    ipi = _build_ipi_entrada(impostos)
    if ipi is not None:
        imposto_kw['IPI'] = ipi

    # Reforma Tributária (CBS/IBS) — replica valores da saída quando calculados.
    linha_rtc = {
        **linha,
        'snapshot_fiscal': {
            'reforma_tributaria': impostos.get('reforma_tributaria')
            if isinstance(impostos.get('reforma_tributaria'), dict)
            else {},
        },
    }
    ibscbs = build_reforma_tributaria_item_bindings(linha_rtc)
    if ibscbs is not None:
        imposto_kw['IBSCBS'] = ibscbs

    det_kw: dict[str, Any] = {
        'nItem': str(linha.get('n_item')),
        'prod': prod,
        'imposto': nfe.Tnfe.InfNfe.Det.Imposto(**imposto_kw),
    }
    imposto_devol = _build_imposto_devol_entrada(impostos)
    if imposto_devol is not None:
        det_kw['impostoDevol'] = imposto_devol
    return nfe.Tnfe.InfNfe.Det(**det_kw)


def _ender_emit_entrada(dados: dict[str, Any]):
    from nfelib.nfe.bindings.v4_0 import leiaute_nfe_v4_00 as layout

    emit = dados['emitente']
    c_mun = _digits(emit.get('c_mun'), max_len=7) or codigo_municipio_ibge(emit.get('uf'), cidade=emit.get('cidade'))
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
        fone=_digits(emit.get('fone'), max_len=14) or None,
    )


def _ender_dest_entrada(dados: dict[str, Any]):
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


def _codigo_municipio_fg(dados: dict[str, Any]) -> str:
    ide = dados.get('ide') or {}
    emit = dados.get('emitente') or {}
    c_mun = _digits(emit.get('c_mun'), max_len=7)
    if c_mun and len(c_mun) == 7:
        return c_mun
    return codigo_municipio_ibge(emit.get('uf'), cidade=emit.get('cidade'))


def montar_tnfe_entrada(
    dados: dict[str, Any],
    *,
    nf_entrada: NFeEntrada,
    chave: ChaveAcessoNFe,
    tp_amb: str = '2',
) -> Any:
    if not nfelib_disponivel():
        raise NFeEntradaXmlError('nfelib não está instalado no ambiente.')

    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    from apps.fiscal.nfe_endereco_xml import enriquecer_municipios_dados_nfe

    enriquecer_municipios_dados_nfe(dados)

    ide_map = dados['ide']
    inf = nfe.Tnfe.InfNfe(versao='4.00')
    inf.Id = chave.inf_nfe_id

    serie = _text(nf_entrada.serie_nfe)
    validar_serie_autorizacao_normal(serie)
    serie_xml = normalizar_serie_xml(serie)
    fin_nfe = _text(ide_map.get('fin_nfe')) or _text(nf_entrada.fin_nfe)

    ide_kw: dict[str, Any] = dict(
        cUF=chave.chave_43[:2],
        cNF=_text(nf_entrada.codigo_numerico),
        natOp=_text(ide_map.get('nat_op'))[:60],
        mod='55',
        serie=serie_xml,
        nNF=_nnf_xml(nf_entrada.numero_nfe),
        dhEmi=formatar_dh_emi(),
        tpNF='0',
        idDest=_text(ide_map.get('id_dest')) or '1',
        cMunFG=_codigo_municipio_fg(dados),
        tpImp='1',
        tpEmis='1',
        cDV=chave.digito_verificador,
        tpAmb=tp_amb,
        finNFe=fin_nfe,
        indFinal='0',
        indPres='9',
        procEmi='0',
        verProc=VERSAO_PROC,
    )
    inf.ide = nfe.Tnfe.InfNfe.Ide(**ide_kw)

    if fin_nfe == '4':
        ch_ref = _digits(nf_entrada.chave_nfe_referenciada, max_len=44)
        if len(ch_ref) == 44:
            inf.ide.NFref = [nfe.Tnfe.InfNfe.Ide.Nfref(refNFe=ch_ref)]

    emit = dados['emitente']
    crt = _text(emit.get('crt')) or '3'
    inf.emit = nfe.Tnfe.InfNfe.Emit(
        CNPJ=_digits(emit.get('cnpj'), max_len=14),
        xNome=_text(emit.get('x_nome'))[:60],
        IE=ie_apenas_digitos(emit.get('ie')),
        CRT=crt,
    )
    inf.emit.enderEmit = _ender_emit_entrada(dados)

    dest = dados['destinatario']
    doc = _digits(dest.get('cnpj')) or _digits(dest.get('cpf'))
    dest_nome = HOMOLOG_DEST_XNOME if tp_amb == '2' else (_text(dest.get('x_nome'))[:60] or 'Destinatário')
    dest_ie = ie_apenas_digitos(dest.get('ie'))
    dest_kw: dict[str, Any] = {'xNome': dest_nome, 'indIEDest': '1' if dest_ie else '9'}
    if len(doc) == 14:
        dest_kw['CNPJ'] = doc
    elif len(doc) == 11:
        dest_kw['CPF'] = doc
    inf.dest = nfe.Tnfe.InfNfe.Dest(**dest_kw)
    inf.dest.enderDest = _ender_dest_entrada(dados)

    inf.det = [_build_det_entrada(linha) for linha in dados.get('itens') or []]
    if not inf.det:
        raise NFeEntradaXmlError('NF-e sem itens.')

    tot = dados.get('totais') or {}
    from apps.fiscal.reforma_tributaria.xml import build_reforma_tributaria_total_bindings

    total_kw: dict[str, Any] = {'ICMSTot': build_icms_tot_bindings(nfe, tot)}
    # Passa itens com snapshot_fiscal sintético para agregar IBSCBSTot
    itens_rtc = []
    for linha in dados.get('itens') or []:
        impostos = linha.get('impostos_json') or {}
        itens_rtc.append(
            {
                **linha,
                'snapshot_fiscal': {
                    'reforma_tributaria': impostos.get('reforma_tributaria')
                    if isinstance(impostos.get('reforma_tributaria'), dict)
                    else {},
                },
            },
        )
    ibscbs_tot = build_reforma_tributaria_total_bindings(itens_rtc)
    if ibscbs_tot is not None:
        total_kw['IBSCBSTot'] = ibscbs_tot
    inf.total = nfe.Tnfe.InfNfe.Total(**total_kw)
    # Obrigatório no schema e no DANFE BFR (KeyError se modFrete ausente).
    inf.transp = nfe.Tnfe.InfNfe.Transp(modFrete='9')
    inf.pag = build_pag_bindings(nfe, tot)

    return nfe.Tnfe(infNFe=inf)


def _chave_from_nf(nf: NFeEntrada) -> ChaveAcessoNFe:
    chave_44 = _text(nf.chave_acesso)
    if len(chave_44) != 44:
        raise NFeEntradaXmlError(
            'Reserve a numeração de entrada própria antes de gerar o XML oficial.',
        )
    return ChaveAcessoNFe(
        chave_43=chave_44[:43],
        digito_verificador=nf.digito_verificador or chave_44[-1],
        chave_44=chave_44,
        inf_nfe_id=f'NFe{chave_44}',
    )


def _tp_amb_de_nf(nf: NFeEntrada) -> str:
    if nf.ambiente_emissao == NFeEntrada.AmbienteEmissao.PRODUCAO:
        return '1'
    return '2'


def _validacao_para_ambiente(nf: NFeEntrada, *, exigir_numeracao: bool) -> dict[str, Any]:
    if nf.ambiente_emissao == NFeEntrada.AmbienteEmissao.PRODUCAO:
        return validar_pre_emissao_producao_entrada(nf, exigir_numeracao=exigir_numeracao)
    return validar_pre_emissao_homologacao_entrada(nf, exigir_numeracao=exigir_numeracao)


def gerar_bytes_xml_oficial_nfe_entrada(nf: NFeEntrada) -> bytes:
    """Gera XML oficial tpNF=0 conforme ambiente da NF — levanta NFeEntradaXmlError se bloqueado."""
    validacao = _validacao_para_ambiente(nf, exigir_numeracao=True)
    if not validacao['pronta']:
        msgs = [p['mensagem'] for p in validacao['pendencias']]
        raise NFeEntradaXmlError(msgs[0] if msgs else 'NF-e com pendências.')

    dados = gerar_dados_preview_nfe_entrada(nf)
    if dados.get('bloqueado'):
        raise NFeEntradaXmlError(dados.get('mensagem') or 'Dados da NF-e bloqueados para XML.')

    chave = _chave_from_nf(nf)
    tp_amb = _tp_amb_de_nf(nf)
    tnfe = montar_tnfe_entrada(dados, nf_entrada=nf, chave=chave, tp_amb=tp_amb)
    return serializar_tnfe_nfe(tnfe).encode('utf-8')


def gerar_xml_oficial_nfe_entrada(nf: NFeEntrada, *, persistir: bool = False) -> dict[str, Any]:
    """Gera XML oficial tpNF=0 — preview ou persistência em xml_nfe_gerado."""
    validacao = _validacao_para_ambiente(nf, exigir_numeracao=True)
    if not validacao['pronta']:
        msgs = [p['mensagem'] for p in validacao['pendencias']]
        return {
            'ok': False,
            'bloqueado': True,
            'nf_entrada_id': nf.pk,
            'mensagem': msgs[0] if msgs else 'NF-e com pendências.',
            'validacao': validacao,
        }

    dados = gerar_dados_preview_nfe_entrada(nf)
    if dados.get('bloqueado'):
        return {'ok': False, 'bloqueado': True, 'mensagem': dados.get('mensagem'), 'nf_entrada_id': nf.pk}

    chave = _chave_from_nf(nf)
    tp_amb = _tp_amb_de_nf(nf)
    tnfe = montar_tnfe_entrada(dados, nf_entrada=nf, chave=chave, tp_amb=tp_amb)
    xml = serializar_tnfe_nfe(tnfe)

    if persistir:
        nf.xml_nfe_gerado = xml
        nf.status_emissao_sefaz = NFeEntrada.StatusEmissaoSefaz.XML_GERADO
        nf.save(update_fields=['xml_nfe_gerado', 'status_emissao_sefaz'])

    return {
        'ok': True,
        'bloqueado': False,
        'nf_entrada_id': nf.pk,
        'numero': nf.numero,
        'tipo_origem': nf.tipo_origem,
        'preview': not persistir,
        'oficial': True,
        'xml': xml,
        'xml_format': 'nfelib_4.00',
        'versao_layout': '4.00',
        'tp_nf': '0',
        'tp_amb': tp_amb,
        'fin_nfe': _text(nf.fin_nfe),
        'chave_acesso': nf.chave_acesso,
        'serie_nfe': nf.serie_nfe,
        'numero_nfe': nf.numero_nfe,
        'ambiente_emissao': nf.ambiente_emissao,
        'validacao': validacao,
        'pendencias': validacao.get('pendencias') or [],
        'alertas': validacao.get('alertas') or [],
        'mensagens': [MSG_XML_ENTRADA],
        'sem_assinatura': not persistir,
        'sem_transmissao': not persistir,
        'sem_protocolo': True,
    }


def gerar_preview_xml_oficial_nfe_entrada(nf: NFeEntrada) -> dict[str, Any]:
    return gerar_xml_oficial_nfe_entrada(nf, persistir=False)
