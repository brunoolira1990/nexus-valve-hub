"""NF-e 4.0.1 — XML NF-e 4.00 preliminar (nfelib) + chave de acesso real, sem SEFAZ."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import (
    MSG_AMBIENTE_NAO_DEFINIDO,
    ambiente_emissao_nfe_definido,
    resolver_ambiente_emissao_nfe,
    tp_amb_xml_de_ambiente_emissao,
)
from apps.fiscal.nfe_integracao.adapters.exceptions import NFeIntegracaoError
from apps.fiscal.nfe_integracao.adapters.nfelib_adapter import nfelib_disponivel
from apps.fiscal.nfe_integracao.nfe_chave_acesso import ChaveAcessoNFe, aamm_da_emissao, montar_chave_acesso_nfe
from apps.fiscal.nfe_integracao.nfe_numero_fiscal_preliminar import (
    NumeroFiscalPreliminarError,
    resolver_numero_fiscal_preliminar,
)
from apps.fiscal.nfe_saida_preview import (
    MSG_PREVIEW_PENDENCIAS,
    _bloqueio_preview,
    _extrair_pendencias_alertas,
    _text,
    gerar_dados_preview_nfe_saida,
)
from apps.fiscal.nfe_saida_xml_nfelib import (
    NFeXmlNfelibError,
    _build_det,
    _dec,
    _dec_field,
    _digits,
    _enriquecer_totais_impostos,
    _ender_dest,
    _ender_emit,
    build_total_nfe_bindings,
    preparar_dados_serializacao_xml,
)
from apps.fiscal.nfe_emissao.xml_serializacao import formatar_dh_emi
from apps.fiscal.nfe_operacao_fiscal_indicadores import (
    normalizar_ind_final,
    normalizar_ind_intermed,
    normalizar_ind_pres,
)
from apps.fiscal.nfe_xml_higienizacao import normalizar_ie_xml
from apps.fiscal.snapshot_fiscal_helpers import (
    get_cofins_snapshot,
    get_icms_snapshot,
    get_ipi_snapshot,
    get_pis_snapshot,
)
from apps.fiscal.nfe_integracao.danfe_xml_adicionais import (
    enriquecer_linhas_xml_nfe,
    montar_inf_cpl_nfe,
)
from apps.fiscal.validacao_nfe_saida import STATUS_COM_PENDENCIAS, validar_nfe_saida_para_emissao

MSG_XML_PRELIMINAR = (
    'XML NF-e 4.00 preliminar gerado para conferência. Não transmitir. Sem protocolo SEFAZ.'
)
XML_COMMENT_PRELIMINAR = (
    ' Nexus ERP — prévia NF-e 4.00 para conferência. Não transmitir. '
    'Sem autorização SEFAZ. Sem protocolo. Chave calculada; não equivale a NF-e autorizada. '
)
AVISO_DANFE_PRELIMINAR = (
    'Documento gerado a partir de XML preliminar. Ainda sem autorização SEFAZ e sem protocolo.'
)


class NFeXmlPreliminarError(NFeIntegracaoError):
    """Erro na geração/validação do XML preliminar."""


@dataclass
class ResultadoXmlPreliminar:
    xml_bytes: bytes
    xml: str
    chave_acesso: str
    serie_fiscal: str
    numero_fiscal: str
    numero_interno_ref: str
    politica_numeracao: str
    inf_nfe_id: str
    tp_amb: str


def _codigo_municipio_fg(dados: dict[str, Any]) -> str:
    cfg = (getattr(settings, 'FISCAL_CODIGO_MUNICIPIO_FG', None) or '3550308').strip()
    digits = _digits(cfg, max_len=7)
    if len(digits) == 7:
        return digits
    c_uf = _digits(dados.get('ide', {}).get('c_uf'), max_len=2)
    return f'{c_uf}50308' if c_uf == '35' else '3550308'


def validar_dados_para_xml_preliminar(nfe_saida: NFeSaida, dados: dict[str, Any]) -> list[str]:
    """Retorna lista de pendências bloqueantes para XML preliminar / BFR."""
    erros: list[str] = []
    emit = dados.get('emitente') or {}
    dest = dados.get('destinatario') or {}
    if len(_digits(emit.get('cnpj'), max_len=14)) != 14:
        erros.append('Emitente sem CNPJ válido (14 dígitos).')
    if not _text(emit.get('uf')):
        erros.append('Emitente sem UF.')
    if not _text(emit.get('ie')):
        erros.append('Emitente sem inscrição estadual.')
    doc_dest = _digits(dest.get('cnpj'))
    if len(doc_dest) not in (11, 14):
        erros.append('Destinatário sem CNPJ/CPF válido.')
    if not _text(dest.get('uf')):
        erros.append('Destinatário sem UF.')

    itens = dados.get('itens') or []
    if not itens:
        erros.append('NF-e sem itens.')
    soma_itens = Decimal('0')
    for idx, linha in enumerate(itens, start=1):
        if not _digits(linha.get('ncm'), max_len=8):
            erros.append(f'Item {idx}: NCM obrigatório.')
        if not _digits(linha.get('cfop'), max_len=4):
            erros.append(f'Item {idx}: CFOP obrigatório.')
        if not _text(linha.get('u_com')):
            erros.append(f'Item {idx}: unidade comercial obrigatória.')
        snap = linha.get('snapshot_fiscal') or {}
        icms = get_icms_snapshot(snap)
        cst = _text(icms.get('cst_icms') or icms.get('csosn'))
        if not cst:
            erros.append(f'Item {idx}: CST/CSOSN ICMS obrigatório.')
        soma_itens += _dec(linha.get('v_prod'))

    v_nf = _dec((dados.get('totais') or {}).get('v_nf'))
    if v_nf and abs(soma_itens - v_nf) > Decimal('0.05'):
        erros.append(
            f'Total da NF-e ({v_nf}) diverge da soma dos itens ({soma_itens}).',
        )
    return erros


def montar_tnfe_preliminar(
    dados: dict[str, Any],
    *,
    nfe_saida: NFeSaida,
    chave: ChaveAcessoNFe,
    numeracao,
    tp_amb: str = '2',
) -> Any:
    if not nfelib_disponivel():
        raise NFeXmlPreliminarError('nfelib não está instalado no ambiente.')

    preparar_dados_serializacao_xml(dados)

    from nfelib.nfe.bindings.v4_0 import nfe_v4_00 as nfe

    ide_map = dados['ide']
    inf = nfe.Tnfe.InfNfe(versao='4.00')
    inf.Id = chave.inf_nfe_id

    dh_emi = formatar_dh_emi()

    inf.ide = nfe.Tnfe.InfNfe.Ide(
        cUF=chave.chave_43[:2],
        cNF=numeracao.codigo_numerico,
        natOp=_text(ide_map.get('nat_op'))[:60] or 'Venda',
        mod='55',
        serie=numeracao.serie,
        nNF=numeracao.nnf,
        dhEmi=dh_emi,
        tpNF=_text(ide_map.get('tp_nf')) or '1',
        idDest=_text(ide_map.get('id_dest')) or '1',
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
        verProc='NexusERP-4.0.1-preliminar',
    )

    emit = dados['emitente']
    inf.emit = nfe.Tnfe.InfNfe.Emit(
        CNPJ=_digits(emit.get('cnpj'), max_len=14),
        xNome=_text(emit.get('x_nome'))[:60] or 'Emitente',
        IE=normalizar_ie_xml(emit.get('ie'), permitir_isento=False) or None,
        CRT=_text(emit.get('crt')) or '3',
    )
    inf.emit.enderEmit = _ender_emit(dados)

    dest = dados['destinatario']
    doc = _digits(dest.get('cnpj'))
    dest_kw: dict[str, Any] = {
        'xNome': _text(dest.get('x_nome'))[:60] or 'Destinatário',
        'indIEDest': '1' if _text(dest.get('ie')) else '9',
    }
    if len(doc) == 14:
        dest_kw['CNPJ'] = doc
    elif len(doc) == 11:
        dest_kw['CPF'] = doc
    if _text(dest.get('ie')):
        dest_kw['IE'] = normalizar_ie_xml(dest.get('ie'))
    inf.dest = nfe.Tnfe.InfNfe.Dest(**dest_kw)
    inf.dest.enderDest = _ender_dest(dados)

    itens_db = enriquecer_linhas_xml_nfe(nfe_saida, dados)
    inf.det = [_build_det(linha) for linha in dados.get('itens') or []]

    inf.total = build_total_nfe_bindings(nfe, dados)

    from apps.fiscal.nfe_emissao.xml_serializacao import build_cobr_bindings, build_pag_bindings
    from apps.fiscal.nfe_saida_duplicatas import duplicatas_para_xml, numero_fatura_nfe

    tot = dados.get('totais') or {}
    duplicatas = duplicatas_para_xml(nfe_saida)
    inf.pag = build_pag_bindings(nfe, tot, duplicatas=duplicatas)
    cobr = build_cobr_bindings(nfe, tot, duplicatas, n_fat=numero_fatura_nfe(nfe_saida))
    if cobr is not None:
        inf.cobr = cobr

    from apps.fiscal.nfe_transp_bindings import aplicar_transp_nfelib

    aplicar_transp_nfelib(inf, nfe, dados.get('transporte'))

    inf_cpl, inf_fisco = montar_inf_cpl_nfe(nfe_saida, dados, itens_db=itens_db)
    inf_adic_kw: dict[str, Any] = {}
    if inf_cpl:
        inf_adic_kw['infCpl'] = inf_cpl
    if inf_fisco:
        inf_adic_kw['infAdFisco'] = inf_fisco
    if inf_adic_kw:
        inf.infAdic = nfe.Tnfe.InfNfe.InfAdic(**inf_adic_kw)

    return nfe.Tnfe(infNFe=inf)


def serializar_tnfe_preliminar(tnfe: Any, *, pretty: bool = True) -> str:
    from xsdata.formats.dataclass.serializers import XmlSerializer
    from xsdata.formats.dataclass.serializers.config import SerializerConfig

    body = XmlSerializer(
        config=SerializerConfig(pretty_print=pretty, xml_declaration=False),
    ).render(tnfe)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!--{XML_COMMENT_PRELIMINAR}-->\n{body}'


def invalidar_xml_preliminar_armazenado(nfe_saida: NFeSaida) -> None:
    """Limpa XML preliminar persistido para forçar regeneração com dados atuais da conferência."""
    if not (
        _text(getattr(nfe_saida, 'xml_preliminar', ''))
        or _text(getattr(nfe_saida, 'chave_acesso_preliminar', ''))
    ):
        return
    nfe_saida.xml_preliminar = ''
    nfe_saida.xml_preliminar_gerado_em = None
    nfe_saida.chave_acesso_preliminar = ''
    nfe_saida.serie_fiscal_preliminar = ''
    nfe_saida.numero_fiscal_preliminar = ''
    nfe_saida.save(
        update_fields=[
            'xml_preliminar',
            'xml_preliminar_gerado_em',
            'chave_acesso_preliminar',
            'serie_fiscal_preliminar',
            'numero_fiscal_preliminar',
        ],
    )


def _persistir_preliminar_no_modelo(
    nfe_saida: NFeSaida,
    *,
    xml: str,
    chave: str,
    serie: str,
    nnf: str,
) -> None:
    if not getattr(settings, 'FISCAL_PERSISTIR_XML_PRELIMINAR', False):
        return
    nfe_saida.xml_preliminar = xml
    nfe_saida.xml_preliminar_gerado_em = timezone.now()
    nfe_saida.chave_acesso_preliminar = chave
    nfe_saida.serie_fiscal_preliminar = serie
    nfe_saida.numero_fiscal_preliminar = nnf
    nfe_saida.save(
        update_fields=[
            'xml_preliminar',
            'xml_preliminar_gerado_em',
            'chave_acesso_preliminar',
            'serie_fiscal_preliminar',
            'numero_fiscal_preliminar',
        ],
    )


def _xml_tem_tag_valor(xml_cache: str, tag: str, valor: str) -> bool:
    if not valor:
        return True
    return bool(
        re.search(
            rf'<(?:[\w]{{1,20}}:)?{tag}>{re.escape(valor)}</(?:[\w]{{1,20}}:)?{tag}>',
            xml_cache,
            flags=re.IGNORECASE,
        ),
    )


def _xml_tag_inteiro(xml_cache: str, tag: str) -> int | None:
    m = re.search(
        rf'<(?:[\w]{{1,20}}:)?{tag}>([^<]+)</(?:[\w]{{1,20}}:)?{tag}>',
        xml_cache,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    digits = ''.join(c for c in m.group(1) if c.isdigit())
    return int(digits) if digits else None


def _xml_preliminar_numeracao_bate(nfe_saida: NFeSaida, xml_cache: str) -> bool:
    try:
        numeracao = resolver_numero_fiscal_preliminar(nfe_saida)
    except NumeroFiscalPreliminarError:
        return False
    serie_xml = _xml_tag_inteiro(xml_cache, 'serie')
    nnf_xml = _xml_tag_inteiro(xml_cache, 'nNF')
    if serie_xml is None or nnf_xml is None:
        return False
    serie_esperada = int(''.join(c for c in numeracao.serie if c.isdigit()) or '0')
    nnf_esperada = int(''.join(c for c in numeracao.nnf if c.isdigit()) or '0')
    return serie_xml == serie_esperada and nnf_xml == nnf_esperada


def _xml_preliminar_cache_valido(nfe_saida: NFeSaida, xml_cache: str, *, tp_amb_esperado: str) -> bool:
    """Invalida cache antigo sem tags xPed/nItemPed ou ambiente/numeração divergentes."""
    if not xml_cache:
        return False
    m_amb = re.search(r'<(?:[\w]{1,20}:)?tpAmb>([12])</(?:[\w]{1,20}:)?tpAmb>', xml_cache, flags=re.IGNORECASE)
    if not m_amb or m_amb.group(1) != tp_amb_esperado:
        return False
    if not _xml_preliminar_numeracao_bate(nfe_saida, xml_cache):
        return False
    ped_cab = _text(nfe_saida.pedido_cliente_numero)
    tags_xped: set[str] = set()
    tags_nitem: set[str] = set()
    if ped_cab:
        tags_xped.add(ped_cab[:15])
    for item in nfe_saida.itens.all():
        pc = _text(item.pedido_cliente_numero) or ped_cab
        if pc:
            tags_xped.add(pc[:15])
        pi = _text(item.pedido_cliente_item)
        if pi:
            from apps.fiscal.nfe_integracao.danfe_xml_adicionais import resolver_xped_nitemped_item

            _, n_item = resolver_xped_nitemped_item(item, pedido_cabecalho=ped_cab)
            if n_item:
                tags_nitem.add(n_item)
    for ped_tag in tags_xped:
        if not _xml_tem_tag_valor(xml_cache, 'xPed', ped_tag):
            return False
    for n_item in tags_nitem:
        if not _xml_tem_tag_valor(xml_cache, 'nItemPed', n_item):
            return False
    return True


def gerar_xml_nfe_preliminar(nfe_saida: NFeSaida, *, persistir: bool | None = None) -> bytes:
    """Gera XML NF-e 4.00 preliminar com chave calculada (tpAmb conforme ambiente_emissao)."""
    if not ambiente_emissao_nfe_definido(nfe_saida):
        raise NFeXmlPreliminarError(MSG_AMBIENTE_NAO_DEFINIDO)

    try:
        ambiente = resolver_ambiente_emissao_nfe(nfe_saida)
    except ValueError as exc:
        raise NFeXmlPreliminarError(str(exc)) from exc
    tp_amb = tp_amb_xml_de_ambiente_emissao(ambiente)

    xml_cache = _text(getattr(nfe_saida, 'xml_preliminar', ''))
    chave_cache = _text(getattr(nfe_saida, 'chave_acesso_preliminar', ''))
    if xml_cache and chave_cache and _xml_preliminar_cache_valido(
        nfe_saida,
        xml_cache,
        tp_amb_esperado=tp_amb,
    ):
        return xml_cache.encode('utf-8')

    bloqueio = _bloqueio_preview(nfe_saida)
    if bloqueio:
        raise NFeXmlPreliminarError((bloqueio.get('mensagens') or ['Prévia bloqueada.'])[0])

    dados = gerar_dados_preview_nfe_saida(nfe_saida, incluir_validacao_emissao=False)
    if dados.get('bloqueado'):
        raise NFeXmlPreliminarError('Dados de prévia bloqueados para esta NF-e.')

    erros = validar_dados_para_xml_preliminar(nfe_saida, dados)
    if erros:
        raise NFeXmlPreliminarError(' '.join(erros[:3]) + (f' (+{len(erros) - 3})' if len(erros) > 3 else ''))

    for linha in dados.get('itens') or []:
        item_pk = linha.get('item_id')
        if item_pk and not linha.get('snapshot_fiscal'):
            try:
                item = ItemNFeSaida.objects.get(pk=item_pk, nf=nfe_saida)
                linha['snapshot_fiscal'] = item.snapshot_fiscal or {}
            except ItemNFeSaida.DoesNotExist:
                linha['snapshot_fiscal'] = {}
    _enriquecer_totais_impostos(dados)
    preparar_dados_serializacao_xml(dados)

    try:
        numeracao = resolver_numero_fiscal_preliminar(nfe_saida)
    except NumeroFiscalPreliminarError as exc:
        raise NFeXmlPreliminarError(str(exc)) from exc

    if numeracao.numero_interno_ref and not numeracao.nnf.isdigit():
        raise NFeXmlPreliminarError('nNF preliminar deve ser numérico.')

    emit_cnpj = _digits(dados['emitente'].get('cnpj'), max_len=14)
    chave = montar_chave_acesso_nfe(
        cuf=dados['ide'].get('c_uf') or '35',
        aamm=aamm_da_emissao(),
        cnpj_emitente=emit_cnpj,
        modelo='55',
        serie=numeracao.serie,
        nnf=numeracao.nnf,
        tp_emis='1',
        codigo_numerico=numeracao.codigo_numerico,
    )

    try:
        tnfe = montar_tnfe_preliminar(
            dados,
            nfe_saida=nfe_saida,
            chave=chave,
            numeracao=numeracao,
            tp_amb=tp_amb,
        )
        xml = serializar_tnfe_preliminar(tnfe)
    except NFeXmlNfelibError as exc:
        raise NFeXmlPreliminarError(str(exc)) from exc
    except Exception as exc:
        raise NFeXmlPreliminarError(f'Falha ao montar XML preliminar: {exc}') from exc

    if 'RASCUNHO-FAT' in xml and f'<nNF>{numeracao.nnf}</nNF>' not in xml:
        pass
    if f'<nNF>{nfe_saida.numero}</nNF>' in xml and not str(nfe_saida.numero).isdigit():
        raise NFeXmlPreliminarError(
            'XML preliminar não pode usar número interno alfanumérico como nNF oficial.',
        )

    do_persist = persistir if persistir is not None else getattr(
        settings,
        'FISCAL_PERSISTIR_XML_PRELIMINAR',
        False,
    )
    if do_persist:
        _persistir_preliminar_no_modelo(
            nfe_saida,
            xml=xml,
            chave=chave.chave_44,
            serie=numeracao.serie,
            nnf=numeracao.nnf,
        )

    return xml.encode('utf-8')


def gerar_resultado_xml_preliminar(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Payload API (xml string + metadados) para prévia/DANFE BFR."""
    if not ambiente_emissao_nfe_definido(nfe_saida):
        raise NFeXmlPreliminarError(MSG_AMBIENTE_NAO_DEFINIDO)
    ambiente = resolver_ambiente_emissao_nfe(nfe_saida)
    tp_amb = tp_amb_xml_de_ambiente_emissao(ambiente)
    numeracao = resolver_numero_fiscal_preliminar(nfe_saida)
    xml_bytes = gerar_xml_nfe_preliminar(nfe_saida)
    xml = xml_bytes.decode('utf-8')
    nfe_saida.refresh_from_db()
    chave_44 = nfe_saida.chave_acesso_preliminar or ''
    if not chave_44:
        import re

        m = re.search(r'Id="NFe([0-9]{44})"', xml)
        chave_44 = m.group(1) if m else ''
    chave_fmt = ' '.join(chave_44[i : i + 4] for i in range(0, 44, 4)) if len(chave_44) == 44 else ''
    validacao = validar_nfe_saida_para_emissao(nfe_saida)
    pendencias, alertas = _extrair_pendencias_alertas(validacao)

    return {
        'nfe_saida_id': nfe_saida.pk,
        'numero': nfe_saida.numero,
        'numero_interno_ref': numeracao.numero_interno_ref,
        'numero_fiscal_preliminar': numeracao.nnf,
        'serie_fiscal_preliminar': numeracao.serie,
        'politica_numeracao': numeracao.politica,
        'status': nfe_saida.status,
        'preview': True,
        'preliminar': True,
        'sem_autorizacao': True,
        'ambiente': ambiente,
        'bloqueado': False,
        'xml': xml,
        'xml_bytes': len(xml_bytes),
        'xml_format': 'nfelib_4.00_preliminar',
        'versao_layout': '4.00',
        'chave_acesso_preliminar': chave_44,
        'chave_acesso_formatada': chave_fmt,
        'inf_nfe_id': f'NFe{chave_44}' if chave_44 else '',
        'tp_amb': tp_amb,
        'mensagens': [MSG_XML_PRELIMINAR, AVISO_DANFE_PRELIMINAR],
        'avisos': [AVISO_DANFE_PRELIMINAR],
        'status_prontidao': validacao.get('status_prontidao'),
        'pendencias': pendencias,
        'alertas': alertas,
        'pode_emitir': validacao.get('pode_emitir'),
        'marcas_preview': [
            'XML preliminar nfelib 4.00',
            'Chave calculada — sem protocolo SEFAZ',
            'Não transmitir',
        ],
    }


def pode_gerar_xml_preliminar(nfe_saida: NFeSaida) -> tuple[bool, list[str]]:
    try:
        dados = gerar_dados_preview_nfe_saida(nfe_saida, incluir_validacao_emissao=False)
        if dados.get('bloqueado'):
            return False, ['Prévia bloqueada.']
        erros = validar_dados_para_xml_preliminar(nfe_saida, dados)
        return len(erros) == 0, erros
    except Exception as exc:
        return False, [str(exc)]
