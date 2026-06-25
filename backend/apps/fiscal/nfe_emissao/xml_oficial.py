"""XML oficial NF-e 4.00 para emissão SEFAZ (numeração reservada, chave real)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.xml_serializacao import (
    build_cobr_bindings,
    build_icms_tot_bindings,
    build_pag_bindings,
    codigo_municipio_ibge,
    formatar_dh_emi,
    ie_apenas_digitos,
    serializar_tnfe_nfe,
)
from apps.fiscal.nfe_operacao_fiscal_indicadores import (
    normalizar_ind_final,
    normalizar_ind_intermed,
    normalizar_ind_pres,
)
from apps.fiscal.nfe_xml_higienizacao import normalizar_ie_xml, validar_ie_emitente_transmissao
from apps.fiscal.nfe_saida_duplicatas import duplicatas_para_xml, numero_fatura_nfe
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_integracao.danfe_xml_adicionais import enriquecer_linhas_xml_nfe, montar_inf_cpl_nfe
from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe
from apps.fiscal.nfe_saida_preview import _text, gerar_dados_preview_nfe_saida
from apps.fiscal.nfe_saida_xml_nfelib import (
    NFeXmlNfelibError,
    _build_det,
    _dec_field,
    _digits,
    _enriquecer_totais_impostos,
    _ender_dest,
    _ender_emit,
    build_total_nfe_bindings,
    preparar_dados_serializacao_xml,
)
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao

HOMOLOG_DEST_XNOME = 'NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL'
VERSAO_PROC = 'NexusERP-4.0.2'


class NFeXmlEmissaoError(NFeXmlNfelibError):
    pass


def _nnf_xml(nnf: str) -> str:
    """nNF no XML — sem zeros à esquerda (pattern XSD [1-9]{1}[0-9]{0,8})."""
    digits = ''.join(c for c in str(nnf) if c.isdigit())
    if not digits:
        return '1'
    return str(int(digits))


def _codigo_municipio_fg(dados: dict[str, Any]) -> str:
    ide = dados.get('ide') or {}
    emit = dados.get('emitente') or {}
    c_mun = _digits(ide.get('c_mun_fg'), max_len=7) or _digits(emit.get('c_mun'), max_len=7)
    if c_mun and c_mun != '3500000' and len(c_mun) == 7:
        return c_mun
    return codigo_municipio_ibge(emit.get('uf'), cidade=emit.get('cidade'))


def _enriquecer_municipios_emissao(dados: dict[str, Any]) -> None:
    """Delega ao módulo central de endereço fiscal (emitente FG + destinatário próprio)."""
    preparar_dados_serializacao_xml(dados)


def montar_tnfe_emissao(
    dados: dict[str, Any],
    *,
    nfe_saida: NFeSaida,
    chave: ChaveAcessoNFe,
    serie: str,
    nnf: str,
    codigo_numerico: str,
    tp_amb: str = '2',
) -> Any:
    if not nfelib_disponivel():
        raise NFeXmlEmissaoError('nfelib não está instalado no ambiente.')
    if not nfe_saida.numero_nfe or not nfe_saida.serie_nfe:
        raise NFeXmlEmissaoError('Numeração fiscal não reservada para esta NF-e.')

    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    _enriquecer_municipios_emissao(dados)
    ide_map = dados['ide']
    inf = nfe.Tnfe.InfNfe(versao='4.00')
    inf.Id = chave.inf_nfe_id

    dh_emi = formatar_dh_emi()

    from apps.fiscal.nfe_emissao.serie_fiscal import normalizar_serie_xml, validar_serie_autorizacao_normal

    validar_serie_autorizacao_normal(serie)
    serie_xml = normalizar_serie_xml(serie)

    inf.ide = nfe.Tnfe.InfNfe.Ide(
        cUF=chave.chave_43[:2],
        cNF=codigo_numerico,
        natOp=_text(ide_map.get('nat_op'))[:60] or 'Venda',
        mod='55',
        serie=serie_xml,
        nNF=_nnf_xml(nnf),
        dhEmi=dh_emi,
        tpNF=_text(ide_map.get('tp_nf')) or '1',
        idDest=_text(ide_map.get('id_dest')) or _text(ide_map.get('idDest')) or '1',
        cMunFG=_codigo_municipio_fg(dados),
        tpImp='1',
        tpEmis='1',
        cDV=chave.digito_verificador,
        tpAmb=tp_amb,
        finNFe='1',
        indFinal=normalizar_ind_final(nfe_saida.ind_final),
        indPres=normalizar_ind_pres(nfe_saida.ind_pres),
        indIntermed=normalizar_ind_intermed(getattr(nfe_saida, 'ind_intermed', None)),
        procEmi='0',
        verProc=VERSAO_PROC,
    )

    emit = dados['emitente']
    ie_emit = normalizar_ie_xml(emit.get('ie'), permitir_isento=False)
    ok_ie, msg_ie = validar_ie_emitente_transmissao(emit.get('ie'))
    if not ok_ie:
        raise NFeXmlEmissaoError(msg_ie)
    inf.emit = nfe.Tnfe.InfNfe.Emit(
        CNPJ=_digits(emit.get('cnpj'), max_len=14),
        xNome=_text(emit.get('x_nome'))[:60] or 'Emitente',
        IE=ie_emit,
        CRT=_text(emit.get('crt')) or '3',
    )
    inf.emit.enderEmit = _ender_emit(dados)

    dest = dados['destinatario']
    doc = _digits(dest.get('cnpj'))
    dest_nome = HOMOLOG_DEST_XNOME if tp_amb == '2' else (_text(dest.get('x_nome'))[:60] or 'Destinatário')
    dest_ie = normalizar_ie_xml(dest.get('ie'))
    ind_ie = _text(dest.get('ind_ie_dest')) or ('1' if dest_ie else '9')
    dest_kw: dict[str, Any] = {
        'xNome': dest_nome,
        'indIEDest': ind_ie,
    }
    if len(doc) == 14:
        dest_kw['CNPJ'] = doc
    elif len(doc) == 11:
        dest_kw['CPF'] = doc
    if dest_ie:
        dest_kw['IE'] = dest_ie
    inf.dest = nfe.Tnfe.InfNfe.Dest(**dest_kw)
    inf.dest.enderDest = _ender_dest(dados)

    enriquecer_linhas_xml_nfe(nfe_saida, dados)
    inf.det = [_build_det(linha) for linha in dados.get('itens') or []]
    if not inf.det:
        raise NFeXmlEmissaoError('NF-e sem itens: não é possível gerar XML oficial.')

    from apps.fiscal.nfe_difal_calculo import aplicar_totais_difal_em_dados

    aplicar_totais_difal_em_dados(dados, det_list=inf.det)
    tot = dados.get('totais') or {}
    inf.total = build_total_nfe_bindings(nfe, dados)
    duplicatas = duplicatas_para_xml(nfe_saida)
    inf.pag = build_pag_bindings(nfe, tot, duplicatas=duplicatas)
    cobr = build_cobr_bindings(nfe, tot, duplicatas, n_fat=numero_fatura_nfe(nfe_saida))
    if cobr is not None:
        inf.cobr = cobr

    from apps.fiscal.nfe_transp_bindings import aplicar_transp_nfelib

    aplicar_transp_nfelib(inf, nfe, dados.get('transporte'))

    itens_db = (
        {it.pk: it for it in nfe_saida.itens.all()}
        if hasattr(nfe_saida, 'itens')
        else None
    )
    inf_cpl, inf_fisco = montar_inf_cpl_nfe(nfe_saida, dados, itens_db=itens_db)
    inf_adic_kw: dict[str, Any] = {}
    if inf_cpl:
        inf_adic_kw['infCpl'] = inf_cpl
    if inf_fisco:
        inf_adic_kw['infAdFisco'] = inf_fisco
    if inf_adic_kw:
        inf.infAdic = nfe.Tnfe.InfNfe.InfAdic(**inf_adic_kw)

    return nfe.Tnfe(infNFe=inf)


def _preparar_dados_emissao(nfe_saida: NFeSaida, *, incluir_validacao_emissao: bool = False) -> dict[str, Any]:
    from apps.fiscal.models import ItemNFeSaida

    dados = gerar_dados_preview_nfe_saida(
        nfe_saida,
        incluir_validacao_emissao=incluir_validacao_emissao,
    )
    if dados.get('bloqueado'):
        raise NFeXmlEmissaoError(dados.get('mensagem') or 'NF-e bloqueada para emissão.')

    itens_payload = []
    for linha in dados.get('itens') or []:
        item_id = linha.get('item_id')
        if item_id:
            try:
                item = ItemNFeSaida.objects.get(pk=item_id, nf=nfe_saida)
                linha['snapshot_fiscal'] = item.snapshot_fiscal or {}
            except ItemNFeSaida.DoesNotExist:
                linha['snapshot_fiscal'] = linha.get('snapshot_fiscal') or {}
        itens_payload.append(linha)
    dados['itens'] = itens_payload
    _enriquecer_totais_impostos(dados)
    _enriquecer_municipios_emissao(dados)
    return dados


def gerar_xml_oficial_emissao(nfe_saida: NFeSaida) -> bytes:
    """Gera XML NF-e 4.00 oficial com numeração/chave já reservadas."""
    if not nfe_saida.chave_acesso:
        raise NFeXmlEmissaoError('XML de transmissão não possui chave de acesso válida.')

    if not nfe_saida.indicadores_fiscais_confirmados:
        raise NFeXmlEmissaoError(
            'Confirme consumidor final (indFinal) e indicador de presença (indPres) antes de gerar o XML de transmissão.',
        )

    validacao = validar_nfe_saida_para_emissao(nfe_saida, incluir_higienizacao_xml=False)
    if not validacao.get('pode_emitir'):
        from apps.fiscal.nfe_emissao.validacao_util import extrair_mensagens_pendencias_validacao

        pend = extrair_mensagens_pendencias_validacao(validacao)
        raise NFeXmlEmissaoError(
            pend[0] if pend else 'NF-e com pendências bloqueantes para emissão.',
        )

    dados = _preparar_dados_emissao(nfe_saida)
    empresa = resolver_empresa_emitente_nfe(nfe_saida)
    if not dados.get('emitente'):
        dados['emitente'] = {}

    chave = ChaveAcessoNFe(
        chave_43=nfe_saida.chave_acesso[:43],
        digito_verificador=nfe_saida.digito_verificador or nfe_saida.chave_acesso[-1],
        chave_44=nfe_saida.chave_acesso,
        inf_nfe_id=f'NFe{nfe_saida.chave_acesso}',
    )
    tp_amb = '2' if nfe_saida.ambiente_emissao != NFeSaida.AmbienteEmissao.PRODUCAO else '1'

    try:
        tnfe = montar_tnfe_emissao(
            dados,
            nfe_saida=nfe_saida,
            chave=chave,
            serie=nfe_saida.serie_nfe,
            nnf=nfe_saida.numero_nfe,
            codigo_numerico=nfe_saida.codigo_numerico,
            tp_amb=tp_amb,
        )
        from apps.fiscal.nfe_difal_calculo import NFeDifalXmlInconsistenteError, validar_consistencia_difal_tnfe

        validar_consistencia_difal_tnfe(tnfe)
        xml = serializar_tnfe_nfe(tnfe)
    except NFeXmlEmissaoError:
        raise
    except NFeDifalXmlInconsistenteError as exc:
        raise NFeXmlEmissaoError(str(exc)) from exc
    except Exception as exc:
        raise NFeXmlEmissaoError(f'Falha ao gerar XML oficial: {exc}') from exc

    if 'RASCUNHO-FAT' in xml.upper():
        raise NFeXmlEmissaoError('XML não pode conter número interno RASCUNHO-FAT como nNF.')
    if 'NÃO TRANSMITIR' in xml.upper() or 'NAO TRANSMITIR' in xml.upper():
        raise NFeXmlEmissaoError('XML de emissão contém marcação de prévia.')

    _ = empresa  # emitente validado no preview
    from apps.fiscal.nfe_emissao.xml_compactacao import normalizar_xml_para_assinatura_nfe

    return normalizar_xml_para_assinatura_nfe(xml.encode('utf-8'))
