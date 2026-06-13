"""Transmissão NF-e Saída produção SEFAZ via PyNFe — separada da homologação."""

from __future__ import annotations

import logging
import re

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeNumeracaoConfiguracao, NFeSaida
from apps.fiscal.nfe_emissao.config_producao import exigir_producao_habilitada
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao
from apps.fiscal.nfe_emissao.pynfe_retorno import desempacotar_retorno_autorizacao_pynfe
from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz, parse_resposta_autorizacao_pynfe
from apps.fiscal.nfe_emissao.serie_fiscal import normalizar_serie_xml
from apps.fiscal.nfe_emissao.transmissao import _local_tag
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import criar_comunicacao_sefaz

logger = logging.getLogger(__name__)


class NFeTransmissaoProducaoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'TRANSMISSAO_SEFAZ_PRODUCAO'):
        self.etapa = etapa
        super().__init__(mensagem)


def re_tpamb_prod(xml: str) -> bool:
    return bool(re.search(r'<[\w:]*tpAmb>\s*1\s*</[\w:]*tpAmb>', xml))


def re_tpamb_homolog(xml: str) -> bool:
    return bool(re.search(r'<[\w:]*tpAmb>\s*2\s*</[\w:]*tpAmb>', xml))


def _validar_numeracao_producao(nfe_saida: NFeSaida, empresa: Empresa) -> None:
    if nfe_saida.ambiente_emissao != NFeSaida.AmbienteEmissao.PRODUCAO:
        raise NFeTransmissaoProducaoError('NF-e não está configurada para ambiente de produção.')
    try:
        cfg = obter_config_numeracao(empresa.pk, ambiente=NFeNumeracaoConfiguracao.Ambiente.PRODUCAO)
    except NFeNumeracaoError as exc:
        raise NFeTransmissaoProducaoError(str(exc), etapa='NUMERACAO') from exc
    if nfe_saida.serie_nfe and normalizar_serie_xml(cfg.serie) != normalizar_serie_xml(nfe_saida.serie_nfe):
        raise NFeTransmissaoProducaoError(
            'Série da NF-e diverge da configuração de numeração produção.',
            etapa='NUMERACAO',
        )


def transmitir_nfe_producao(
    nfe_saida: NFeSaida,
    xml_assinado: bytes | str,
    empresa: Empresa,
    *,
    timeout: int = 60,
) -> ResultadoAutorizacaoSefaz:
    exigir_producao_habilitada()

    if nfe_saida.ambiente_emissao == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
        raise NFeTransmissaoProducaoError('NF-e em ambiente homologação não pode ser transmitida em produção.')

    xml_str = xml_assinado.decode('utf-8') if isinstance(xml_assinado, bytes) else xml_assinado
    if not re_tpamb_prod(xml_str):
        raise NFeTransmissaoProducaoError('XML de produção deve conter tpAmb=1.')
    if re_tpamb_homolog(xml_str):
        raise NFeTransmissaoProducaoError('XML com tpAmb=2 (homologação) não pode ser transmitido em produção.')

    _validar_numeracao_producao(nfe_saida, empresa)

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeTransmissaoProducaoError(str(exc), etapa='CERTIFICADO') from exc

    senha = (empresa.senha_certificado or '').strip()
    uf = (empresa.uf or 'SP').strip()

    try:
        from lxml import etree

        root = etree.fromstring(xml_str.encode('utf-8'))
        nfe_el = root
        if _local_tag(root.tag) != 'NFe':
            for child in root:
                if _local_tag(child.tag) == 'NFe':
                    nfe_el = child
                    break

        comunicacao = criar_comunicacao_sefaz(
            uf,
            cert.caminho,
            senha,
            homologacao=False,
        )
        logger.info(
            'TRANSMISSAO_SEFAZ_PRODUCAO_INICIO nfe_id=%s empresa_id=%s serie=%s numero=%s chave=%s',
            nfe_saida.pk,
            empresa.pk,
            nfe_saida.serie_nfe,
            nfe_saida.numero_nfe,
            nfe_saida.chave_acesso,
        )
        retorno_bruto = comunicacao.autorizacao(
            modelo='nfe',
            nota_fiscal=nfe_el,
            id_lote=int(nfe_saida.pk),
            ind_sinc=1,
            timeout=timeout,
        )
        parsed_ret = desempacotar_retorno_autorizacao_pynfe(retorno_bruto)
        logger.info(
            'TRANSMISSAO_SEFAZ_PRODUCAO_RETORNO nfe_id=%s codigo=%s',
            nfe_saida.pk,
            parsed_ret.codigo,
        )
        resultado = parse_resposta_autorizacao_pynfe(
            parsed_ret.codigo,
            parsed_ret.resultado,
            xml_enviado=xml_str,
        )
        logger.info(
            'TRANSMISSAO_SEFAZ_PRODUCAO_PARSE nfe_id=%s autorizado=%s cStat_nfe=%s',
            nfe_saida.pk,
            resultado.autorizado,
            resultado.nfe.c_stat if resultado.nfe else '',
        )
        return resultado
    except PyNFeComunicacaoError as exc:
        logger.warning(
            'ERRO_TRANSMISSAO_PRODUCAO nfe_id=%s empresa_id=%s etapa=COMUNICACAO exception=%s',
            nfe_saida.pk,
            empresa.pk,
            type(exc).__name__,
            exc_info=True,
        )
        raise NFeTransmissaoProducaoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc
    except NFeTransmissaoProducaoError:
        raise
    except Exception as exc:
        logger.exception(
            'ERRO_TRANSMISSAO_PRODUCAO nfe_id=%s empresa_id=%s exception=%s',
            nfe_saida.pk,
            empresa.pk,
            type(exc).__name__,
        )
        raise NFeTransmissaoProducaoError(f'Falha na transmissão produção: {exc}') from exc
