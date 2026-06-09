"""Transmissão NF-e para SEFAZ homologação via PyNFe."""

from __future__ import annotations

import logging

from apps.cadastros.models import Empresa
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.pynfe_retorno import desempacotar_retorno_autorizacao_pynfe
from apps.fiscal.nfe_emissao.retorno_sefaz import ResultadoAutorizacaoSefaz, parse_resposta_autorizacao_pynfe
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error, PyNFeComunicacaoError
from apps.fiscal.nfe_integracao.adapters.pynfe_adapter import criar_comunicacao_sefaz

logger = logging.getLogger(__name__)


class NFeTransmissaoError(ValueError):
    def __init__(self, mensagem: str, *, etapa: str = 'TRANSMISSAO_SEFAZ'):
        self.etapa = etapa
        super().__init__(mensagem)


def transmitir_nfe_homologacao(
    nfe_saida: NFeSaida,
    xml_assinado: bytes | str,
    empresa: Empresa,
    *,
    timeout: int = 60,
) -> ResultadoAutorizacaoSefaz:
    if nfe_saida.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO:
        raise NFeTransmissaoError('Transmissão em produção bloqueada nesta fase.')

    xml_str = xml_assinado.decode('utf-8') if isinstance(xml_assinado, bytes) else xml_assinado
    if re_tpamb_prod(xml_str):
        raise NFeTransmissaoError('XML com tpAmb=1 (produção) não pode ser transmitido nesta fase.')

    try:
        cert = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeTransmissaoError(str(exc), etapa='CERTIFICADO') from exc

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
            homologacao=True,
        )
        logger.info(
            'TRANSMISSAO_SEFAZ_INICIO nfe_id=%s empresa_id=%s ambiente=homologacao serie=%s numero=%s chave=%s',
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
            'TRANSMISSAO_SEFAZ_RETORNO nfe_id=%s codigo=%s partes=%s',
            nfe_saida.pk,
            parsed_ret.codigo,
            len(retorno_bruto) if isinstance(retorno_bruto, tuple) else 1,
        )
        logger.info('PARSE_RETORNO_INICIO nfe_id=%s codigo=%s', nfe_saida.pk, parsed_ret.codigo)
        resultado = parse_resposta_autorizacao_pynfe(
            parsed_ret.codigo,
            parsed_ret.resultado,
            xml_enviado=xml_str,
        )
        logger.info(
            'PARSE_RETORNO_OK nfe_id=%s autorizado=%s cStat_lote=%s cStat_nfe=%s protocolo=%s',
            nfe_saida.pk,
            resultado.autorizado,
            resultado.lote.c_stat,
            resultado.nfe.c_stat if resultado.nfe else '',
            resultado.protocolo or '',
        )
        return resultado
    except PyNFeComunicacaoError as exc:
        logger.warning(
            'ERRO_TRANSMISSAO nfe_id=%s empresa_id=%s etapa=COMUNICACAO exception=%s msg=%s',
            nfe_saida.pk,
            empresa.pk,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise NFeTransmissaoError(str(exc), etapa='COMUNICACAO_SEFAZ') from exc
    except NFeTransmissaoError:
        raise
    except ValueError as exc:
        logger.exception(
            'ERRO_TRANSMISSAO nfe_id=%s empresa_id=%s etapa=PARSE_RETORNO exception=%s',
            nfe_saida.pk,
            empresa.pk,
            type(exc).__name__,
        )
        raise NFeTransmissaoError(f'Falha na transmissão: {exc}', etapa='PARSE_RETORNO') from exc
    except Exception as exc:
        logger.exception(
            'ERRO_TRANSMISSAO nfe_id=%s empresa_id=%s etapa=TRANSMISSAO_SEFAZ exception=%s',
            nfe_saida.pk,
            empresa.pk,
            type(exc).__name__,
        )
        raise NFeTransmissaoError(f'Falha na transmissão: {exc}', etapa='TRANSMISSAO_SEFAZ') from exc


def re_tpamb_prod(xml: str) -> bool:
    import re

    m = re.search(r'<[\w:]*tpAmb>\s*1\s*</[\w:]*tpAmb>', xml)
    return bool(m)


def _local_tag(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag
