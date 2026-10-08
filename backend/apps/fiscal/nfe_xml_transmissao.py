"""Separação XML preview vs transmissão NF-e — ERP 4.0.13.6.13."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.xml_oficial import NFeXmlEmissaoError, gerar_xml_oficial_emissao
from apps.fiscal.nfe_saida_xml_nfelib import gerar_xml_oficial_nfe_saida
from apps.fiscal.nfe_xml_higienizacao import montar_resumo_higienizacao_xml, validar_higienizacao_xml_transmissao


def gerar_xml_preview_conferencia(nfe_saida: NFeSaida) -> dict[str, Any]:
    """XML de conferência — pode conter NFePREVIEW, comentários e avisos internos."""
    return gerar_xml_oficial_nfe_saida(nfe_saida)


def gerar_xml_transmissao_homologacao(nfe_saida: NFeSaida) -> bytes:
    """XML limpo para transmissão SEFAZ homologação — sem marcas de preview."""
    return gerar_xml_oficial_emissao(nfe_saida)


def gerar_xml_transmissao_producao(nfe_saida: NFeSaida) -> bytes:
    """XML limpo para transmissão SEFAZ produção."""
    if nfe_saida.ambiente_emissao != NFeSaida.AmbienteEmissao.PRODUCAO:
        raise NFeXmlEmissaoError('NF-e não está configurada para ambiente de produção.')
    return gerar_xml_oficial_emissao(nfe_saida)


def montar_payload_xml_transmissao_homologacao(nfe_saida: NFeSaida) -> dict[str, Any]:
    """Gera XML de transmissão + resumo de higienização para API/UI."""
    xml_bytes = gerar_xml_transmissao_homologacao(nfe_saida)
    xml = xml_bytes.decode('utf-8')
    higiene = montar_resumo_higienizacao_xml(nfe_saida, xml)
    pendencias = [i for i in higiene['itens'] if i.get('tipo') == 'PENDENCIA']
    if pendencias:
        raise NFeXmlEmissaoError(
            pendencias[0].get('mensagem') or 'XML de transmissão inválido. Corrija os campos destacados.',
        )
    return {
        'xml': xml,
        'tipo': 'transmissao_homologacao',
        'chave_acesso': nfe_saida.chave_acesso,
        'higienizacao': higiene,
        'mensagem': 'XML de transmissão gerado e validado.',
    }


def validar_xml_transmissao_existente(nfe_saida: NFeSaida, xml: str) -> dict[str, Any]:
    """Valida XML de transmissão já montado (checklist/UI)."""
    itens = validar_higienizacao_xml_transmissao(
        xml,
        nfe_saida=nfe_saida,
        chave_esperada=nfe_saida.chave_acesso,
    )
    pendencias = sum(1 for i in itens if i.get('tipo') == 'PENDENCIA')
    return {
        'aprovado': pendencias == 0,
        'total_pendencias': pendencias,
        'itens': itens,
    }
