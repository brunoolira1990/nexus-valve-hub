"""Higienização e validação do XML de transmissão NF-e — ERP 4.0.13.6.13."""

from __future__ import annotations

import re
from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.xml_serializacao import ie_apenas_digitos
from apps.fiscal.nfe_operacao_fiscal_indicadores import (
    montar_indicadores_fiscais_payload,
    normalizar_ind_final,
    normalizar_ind_pres,
)

TIPO_PENDENCIA = 'PENDENCIA'
TIPO_ALERTA = 'ALERTA'
TIPO_INFO = 'INFO'

_MARCAS_PREVIEW = (
    'NFePREVIEW',
    'NÃO TRANSMITIR',
    'NAO TRANSMITIR',
    'RASCUNHO NÃO AUTORIZADO',
    'RASCUNHO NAO AUTORIZADO',
    'SEM PROTOCOLO SEFAZ',
    'XML DE PRÉVIA',
    'XML DE PREVIA',
    'XML OFICIAL NF-e 4.00 (NFELIB)',
)

_DH_EMI_COM_OFFSET = re.compile(
    r'<dhEmi>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}</dhEmi>',
    re.IGNORECASE,
)
_DH_EMI_MICROS = re.compile(
    r'<dhEmi>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+',
    re.IGNORECASE,
)
_CHAVE_44 = re.compile(r'\d{44}')
_ID_NFE = re.compile(r'Id="NFe(\d{44})"', re.IGNORECASE)
_ID_PREVIEW = re.compile(r'Id="NFePREVIEW', re.IGNORECASE)
_IE_COM_MASCARA = re.compile(r'<IE>[^<]*[.\-/][^<]*</IE>', re.IGNORECASE)


def normalizar_ie_xml(ie: str | None, *, permitir_isento: bool = True) -> str:
    """Remove máscara da IE para XML; preserva ISENTO quando aplicável."""
    raw = (ie or '').strip()
    if not raw:
        return ''
    upper = raw.upper()
    if permitir_isento and upper == 'ISENTO':
        return 'ISENTO'
    return ie_apenas_digitos(raw)


def validar_ie_emitente_transmissao(ie: str | None) -> tuple[bool, str]:
    digits = normalizar_ie_xml(ie, permitir_isento=False)
    if not digits:
        return False, 'Inscrição Estadual do emitente inválida ou incompleta para transmissão.'
    if len(digits) < 2:
        return False, 'Inscrição Estadual do emitente inválida ou incompleta para transmissão.'
    return True, digits


def _extrair_tag(xml: str, tag: str) -> str:
    m = re.search(rf'<{tag}>([^<]*)</{tag}>', xml, re.IGNORECASE)
    return (m.group(1) if m else '').strip()


def _extrair_inf_cpl(xml: str) -> str:
    m = re.search(r'<infCpl>([^<]*)</infCpl>', xml, re.IGNORECASE)
    return (m.group(1) if m else '').strip()


def validar_higienizacao_xml_transmissao(
    xml: str,
    *,
    nfe_saida: NFeSaida | None = None,
    chave_esperada: str | None = None,
) -> list[dict[str, Any]]:
    """Checklist de higienização do XML de transmissão (não altera XML)."""
    itens: list[dict[str, Any]] = []
    xml_u = xml or ''

    def add(tipo: str, codigo: str, mensagem: str) -> None:
        itens.append({'tipo': tipo, 'codigo': codigo, 'grupo': 'higienizacao_xml', 'mensagem': mensagem})

    if _ID_PREVIEW.search(xml_u):
        add(TIPO_PENDENCIA, 'XML_ID_PREVIEW', 'XML de transmissão não pode conter Id NFePREVIEW.')
    else:
        add(TIPO_INFO, 'XML_ID_REAL', 'Id da NF-e usa chave real (sem NFePREVIEW).')

    id_match = _ID_NFE.search(xml_u)
    chave_xml = id_match.group(1) if id_match else ''
    chave_ref = (chave_esperada or (nfe_saida.chave_acesso if nfe_saida else '') or '').strip()
    if not chave_xml or len(chave_xml) != 44:
        add(TIPO_PENDENCIA, 'XML_CHAVE_INVALIDA', 'XML de transmissão não possui chave de acesso válida.')
    elif chave_ref and chave_xml != chave_ref[:44]:
        add(TIPO_PENDENCIA, 'XML_CHAVE_DIVERGENTE', 'Chave de acesso do XML diverge da numeração reservada.')
    else:
        add(TIPO_INFO, 'XML_CHAVE_OK', f'Chave de acesso válida ({chave_xml[:8]}…).')

    if any(m in xml_u.upper() for m in _MARCAS_PREVIEW):
        add(TIPO_PENDENCIA, 'XML_MARCA_PREVIEW', 'XML de transmissão contém marca de prévia/conferência.')
    else:
        add(TIPO_INFO, 'XML_SEM_MARCA_PREVIEW', 'XML sem comentário ou aviso de prévia.')

    inf_cpl = _extrair_inf_cpl(xml_u).upper()
    if any(m in inf_cpl for m in ('NÃO TRANSMITIR', 'NAO TRANSMITIR', 'NFEPREVIEW', 'RASCUNHO NÃO')):
        add(TIPO_PENDENCIA, 'XML_INFCPL_PREVIEW', 'infCpl contém aviso interno de prévia.')
    else:
        add(TIPO_INFO, 'XML_INFCPL_LIMPO', 'infCpl sem aviso interno de prévia.')

    if _DH_EMI_MICROS.search(xml_u):
        add(TIPO_PENDENCIA, 'XML_DHEMI_MICROS', 'dhEmi contém microssegundos — use formato com timezone.')
    elif _DH_EMI_COM_OFFSET.search(xml_u):
        add(TIPO_INFO, 'XML_DHEMI_OK', f'dhEmi com timezone ({_extrair_tag(xml_u, "dhEmi")}).')
    else:
        add(TIPO_PENDENCIA, 'XML_DHEMI_SEM_TZ', 'dhEmi deve incluir offset de timezone (ex.: -03:00).')

    if _IE_COM_MASCARA.search(xml_u):
        add(TIPO_PENDENCIA, 'XML_IE_COM_MASCARA', 'Inscrição Estadual no XML contém pontuação/máscara.')
    else:
        add(TIPO_INFO, 'XML_IE_SEM_MASCARA', 'Inscrições Estaduais serializadas sem máscara.')

    if nfe_saida:
        ok_ie, msg_ie = validar_ie_emitente_transmissao(
            nfe_saida.pedido_venda.empresa_emitente.ie
            if nfe_saida.pedido_venda_id and nfe_saida.pedido_venda.empresa_emitente_id
            else None,
        )
        if not ok_ie:
            add(TIPO_PENDENCIA, 'XML_IE_EMITENTE_INVALIDA', msg_ie)

        ind = montar_indicadores_fiscais_payload(nfe_saida)
        if not ind['indicadores_fiscais_confirmados']:
            add(
                TIPO_PENDENCIA,
                'INDICADORES_NAO_CONFIRMADOS',
                'Confirme consumidor final (indFinal) e indicador de presença (indPres) antes da emissão.',
            )
        else:
            add(
                TIPO_INFO,
                'INDICADORES_CONFIRMADOS',
                f'indFinal={ind["ind_final"]} ({ind["ind_final_label"]}); '
                f'indPres={ind["ind_pres"]} ({ind["ind_pres_label"]}).',
            )

        xml_ind_final = _extrair_tag(xml_u, 'indFinal')
        xml_ind_pres = _extrair_tag(xml_u, 'indPres')
        if xml_ind_final and xml_ind_final != normalizar_ind_final(nfe_saida.ind_final):
            add(TIPO_PENDENCIA, 'XML_INDFINAL_DIVERGENTE', 'indFinal do XML diverge do valor confirmado na conferência.')
        if xml_ind_pres and xml_ind_pres != normalizar_ind_pres(nfe_saida.ind_pres):
            add(TIPO_PENDENCIA, 'XML_INDPRES_DIVERGENTE', 'indPres do XML diverge do valor confirmado na conferência.')

        c_mun = _extrair_tag(xml_u, 'cMun')
        if c_mun and nfe_saida.cliente_id:
            add(TIPO_INFO, 'XML_CMUN_DEST', f'cMun destinatário: {c_mun}.')

    for tag in ('IBSCBS', 'IBSCBSTot'):
        if tag.lower() in xml_u.lower():
            add(TIPO_INFO, f'XML_{tag}_PRESENTE', f'Grupo {tag} presente no XML de transmissão.')

    return itens


def montar_resumo_higienizacao_xml(nfe_saida: NFeSaida, xml: str | None = None) -> dict[str, Any]:
    """Payload para UI — última validação conhecida ou sob demanda."""
    chave = (nfe_saida.chave_acesso or '').strip()
    itens = validar_higienizacao_xml_transmissao(xml or '', nfe_saida=nfe_saida, chave_esperada=chave) if xml else []
    if not xml:
        itens = [
            {
                'tipo': TIPO_INFO,
                'codigo': 'XML_TRANSMISSAO_NAO_GERADO',
                'grupo': 'higienizacao_xml',
                'mensagem': 'Gere o XML de transmissão para validar a higienização.',
            },
        ]
    pendencias = sum(1 for i in itens if i['tipo'] == TIPO_PENDENCIA)
    return {
        'indicadores_fiscais': montar_indicadores_fiscais_payload(nfe_saida),
        'itens': itens,
        'total_pendencias': pendencias,
        'aprovado': pendencias == 0 and bool(xml),
        'chave_acesso': chave,
        'tem_xml_transmissao': bool(xml),
    }
