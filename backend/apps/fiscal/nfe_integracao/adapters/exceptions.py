"""Exceções da camada de integração NF-e / SEFAZ."""


class NFeIntegracaoError(Exception):
    """Erro base da integração NF-e."""


class CertificadoA1Error(NFeIntegracaoError):
    """Certificado A1 inválido, ausente ou senha incorreta."""


class PyNFeComunicacaoError(NFeIntegracaoError):
    """Falha na comunicação com webservice SEFAZ via PyNFe."""


class SefazStatusServicoError(NFeIntegracaoError):
    """Erro ao consultar status do serviço na SEFAZ."""
