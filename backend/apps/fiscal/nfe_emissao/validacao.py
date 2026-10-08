"""Validações locais antes de assinar/transmitir NF-e."""

from __future__ import annotations

import re
from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import MSG_AMBIENTE_NAO_DEFINIDO, ambiente_emissao_nfe_definido
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao
from apps.fiscal.nfe_emissao.validacao_util import extrair_mensagens_pendencias_validacao
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao

MSG_CERTIFICADO_A1 = 'Certificado A1 inválido, ausente ou expirado.'


class NFeEmissaoValidacaoError(ValueError):
    def __init__(self, mensagens: list[str]):
        self.mensagens = mensagens
        super().__init__(mensagens[0] if mensagens else 'Validação de emissão falhou.')


def _digits(value: str | None, size: int) -> str:
    return ''.join(c for c in str(value or '') if c.isdigit())[:size]


def _validar_empresa_emitente(empresa) -> list[str]:
    erros: list[str] = []
    if len(_digits(empresa.cnpj, 14)) != 14:
        erros.append('Empresa emitente: CNPJ inválido ou ausente.')
    if not (empresa.ie or '').strip():
        erros.append('Empresa emitente: Inscrição Estadual (IE) ausente.')
    if not (empresa.uf or '').strip() or len((empresa.uf or '').strip()) != 2:
        erros.append('Empresa emitente: UF inválida ou ausente.')
    if not (empresa.cidade or '').strip():
        erros.append('Empresa emitente: município ausente.')
    if not (empresa.logradouro or '').strip():
        erros.append('Empresa emitente: logradouro ausente.')
    if not (empresa.cep or '').strip():
        erros.append('Empresa emitente: CEP ausente.')
    return erros


def validar_pre_emissao_homologacao(nfe_saida: NFeSaida) -> dict[str, Any]:
    erros: list[str] = []

    if nfe_saida.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO:
        erros.append('Emissão em produção não está habilitada nesta fase.')

    try:
        from apps.cadastros.nfe_ambiente import empresa_configurada_para_producao

        empresa = resolver_empresa_emitente_nfe(nfe_saida)
        if empresa_configurada_para_producao(empresa):
            erros.append(
                'Empresa configurada para ambiente Produção. '
                'Altere o ambiente NF-e no cadastro da empresa ou use o fluxo de emissão produção.',
            )
    except Exception:
        pass

    if nfe_saida.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
        erros.append('NF-e já autorizada em homologação.')

    conf = (nfe_saida.status_conferencia or '').strip()
    if conf != NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO:
        erros.append('NF-e deve estar com status «Pronta para emissão» na conferência.')

    val = validar_nfe_saida_para_emissao(nfe_saida, bloquear_divergencia_cenario=True)
    erros.extend(extrair_mensagens_pendencias_validacao(val))

    try:
        from apps.fiscal.nfe_emissao.serie_fiscal import (
            normalizar_serie_xml,
            serie_rejeitada_sefaz_266,
            validar_serie_autorizacao_normal,
        )

        empresa = resolver_empresa_emitente_nfe(nfe_saida)
        erros.extend(_validar_empresa_emitente(empresa))
        cfg = obter_config_numeracao(empresa.pk, ambiente='homologacao')
        if nfe_saida.numero_nfe and nfe_saida.serie_nfe:
            try:
                validar_serie_autorizacao_normal(nfe_saida.serie_nfe)
            except Exception as exc:
                erros.append(str(exc))
            if normalizar_serie_xml(cfg.serie) != normalizar_serie_xml(nfe_saida.serie_nfe):
                erros.append(
                    'Série da NF-e diverge da configuração de homologação. '
                    'Use «Corrigir série homologação» antes de emitir.',
                )
            if serie_rejeitada_sefaz_266(nfe_saida.serie_nfe):
                erros.append(
                    'Série fora da faixa SEFAZ (0–889). Corrija a série de homologação antes de emitir.',
                )
            if nfe_saida.chave_acesso:
                from apps.fiscal.nfe_emissao.serie_fiscal import (
                    NFeSerieFiscalError,
                    validar_chave_corresponde_numeracao,
                )

                try:
                    validar_chave_corresponde_numeracao(
                        nfe_saida.chave_acesso,
                        serie=nfe_saida.serie_nfe,
                        nnf=nfe_saida.numero_nfe,
                        codigo_numerico=nfe_saida.codigo_numerico,
                    )
                except NFeSerieFiscalError as exc:
                    erros.append(str(exc))
        if (nfe_saida.xml_assinado or '').strip() and nfe_saida.serie_nfe:
            if serie_rejeitada_sefaz_266(nfe_saida.serie_nfe):
                erros.append('XML assinado com série inválida — corrija a série e gere novo XML.')
        try:
            cert = carregar_certificado_empresa(empresa)
            if not cert.valido:
                erros.append(MSG_CERTIFICADO_A1)
        except CertificadoA1Error:
            erros.append(MSG_CERTIFICADO_A1)
    except NFeNumeracaoError as exc:
        erros.append(str(exc))

    if erros:
        raise NFeEmissaoValidacaoError(erros)

    return {'ok': True, 'validacao': val}


def validar_xml_emissao_local(xml: str, *, nfe_saida: NFeSaida) -> list[str]:
    erros: list[str] = []
    if not xml.strip():
        erros.append('XML vazio.')
        return erros

    if 'RASCUNHO-FAT' in xml.upper():
        erros.append('XML contém referência a número interno RASCUNHO-FAT.')

    m_mod = re.search(r'<[\w:]*mod>(\d+)</[\w:]*mod>', xml)
    if not m_mod or m_mod.group(1) != '55':
        erros.append('XML deve ser modelo 55.')

    m_nnf = re.search(r'<[\w:]*nNF>([^<]+)</[\w:]*nNF>', xml)
    if not m_nnf or not re.match(r'^[0-9]{1,9}$', m_nnf.group(1).strip()):
        erros.append('nNF deve ser numérico.')

    if nfe_saida.numero_nfe and m_nnf:
        nnf_xml = m_nnf.group(1).strip()
        nnf_res = ''.join(c for c in nfe_saida.numero_nfe if c.isdigit())
        try:
            if int(nnf_xml) != int(nnf_res or '0'):
                erros.append('nNF do XML diverge da numeração reservada.')
        except ValueError:
            erros.append('nNF do XML diverge da numeração reservada.')

    m_serie = re.search(r'<[\w:]*serie>([^<]+)</[\w:]*serie>', xml)
    if nfe_saida.serie_nfe and m_serie:
        from apps.fiscal.nfe_emissao.serie_fiscal import normalizar_serie_xml

        if normalizar_serie_xml(m_serie.group(1)) != normalizar_serie_xml(nfe_saida.serie_nfe):
            erros.append('Série do XML diverge da numeração reservada.')

    m_amb = re.search(r'<[\w:]*tpAmb>([12])</[\w:]*tpAmb>', xml)
    if not ambiente_emissao_nfe_definido(nfe_saida):
        erros.append(MSG_AMBIENTE_NAO_DEFINIDO)
    else:
        tp_amb_esperado = (
            '1' if nfe_saida.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO else '2'
        )
        if not m_amb or m_amb.group(1) != tp_amb_esperado:
            if tp_amb_esperado == '1':
                erros.append('tpAmb deve ser 1 (produção).')
            else:
                erros.append('tpAmb deve ser 2 (homologação).')

    if nfe_saida.chave_acesso and f'NFe{nfe_saida.chave_acesso}' not in xml:
        erros.append('Id infNFe não corresponde à chave reservada.')

    if re.search(r'<[\w:]*Signature\b', xml, flags=re.IGNORECASE):
        pass  # ok após assinatura
    return erros
