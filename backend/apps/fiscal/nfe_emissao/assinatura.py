"""Assinatura digital A1 do XML NF-e (infNFe)."""

from __future__ import annotations

import logging

from apps.cadastros.models import Empresa
from apps.fiscal.nfe_emissao.validacao import validar_xml_emissao_local
from apps.fiscal.nfe_emissao.xml_compactacao import (
    compactar_xml_serializado,
    normalizar_xml_para_assinatura_nfe,
)
from apps.fiscal.nfe_emissao.xml_serializacao import normalizar_xml_nfe
from apps.fiscal.nfe_integracao.adapters.certificado_a1 import carregar_certificado_empresa
from apps.fiscal.nfe_integracao.adapters.exceptions import CertificadoA1Error
from apps.fiscal.models import NFeSaida

logger = logging.getLogger(__name__)


class NFeAssinaturaError(ValueError):
    pass


def assinar_xml_nfe(xml: bytes | str, empresa: Empresa, *, nfe_saida: NFeSaida | None = None) -> bytes:
    """
    Assina o grupo infNFe com certificado A1 da empresa.
    XML é compactado antes da assinatura; após assinar, apenas re-serializa sem reformatar infNFe.
    """
    xml_str = xml.decode('utf-8') if isinstance(xml, bytes) else xml
    xml_str = normalizar_xml_nfe(xml_str)
    xml_pre = normalizar_xml_para_assinatura_nfe(xml_str)

    if nfe_saida:
        erros = validar_xml_emissao_local(xml_pre.decode('utf-8'), nfe_saida=nfe_saida)
        if erros:
            raise NFeAssinaturaError(erros[0])

    try:
        cert_info = carregar_certificado_empresa(empresa)
    except CertificadoA1Error as exc:
        raise NFeAssinaturaError(str(exc)) from exc

    if not cert_info.valido:
        raise NFeAssinaturaError('Certificado A1 inválido ou expirado.')

    senha = (empresa.senha_certificado or '').strip()
    if not senha:
        raise NFeAssinaturaError('Senha do certificado não cadastrada.')

    try:
        from lxml import etree
        from pynfe.processamento.assinatura import AssinaturaA1
    except ImportError as exc:
        raise NFeAssinaturaError(
            'PyNFe/signxml indisponível. Instale as dependências de integração SEFAZ.',
        ) from exc

    try:
        root = etree.fromstring(xml_pre)
        assinador = AssinaturaA1(cert_info.caminho, senha)
        assinado = assinador.assinar(root, retorna_string=True)
        if isinstance(assinado, str):
            out_bytes = assinado.encode('utf-8')
        else:
            out_bytes = etree.tostring(assinado, encoding='UTF-8', xml_declaration=False, pretty_print=False)
        out = compactar_xml_serializado(out_bytes, com_declaracao=True)
        out_str = out.decode('utf-8')
        if '<Signature' not in out_str and 'signature' not in out_str.lower():
            raise NFeAssinaturaError('XML assinado não contém elemento Signature.')
        return out
    except NFeAssinaturaError:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if 'password' in msg or 'senha' in msg or 'mac verify' in msg:
            logger.warning('Falha assinatura A1 empresa_id=%s (senha/certificado)', empresa.pk)
            raise NFeAssinaturaError('Senha do certificado incorreta ou PFX inválido.') from exc
        logger.warning('Falha assinatura NF-e empresa_id=%s: %s', empresa.pk, type(exc).__name__)
        raise NFeAssinaturaError(f'Falha ao assinar XML: {exc}') from exc
