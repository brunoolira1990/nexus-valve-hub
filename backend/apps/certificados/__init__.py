"""Fachada neutra de certificado digital A1 (C0).

Não realiza HTTP, não integra CENPROT e não altera o fluxo fiscal.
Dívida conhecida: Empresa.senha_certificado permanece em texto simples
(correção exige tarefa separada com migration e criptografia em repouso).
"""

from apps.certificados.contratos import FinalidadeCertificado, MetadadosCertificadoSeguros
from apps.certificados.exceptions import CertificadoDigitalError
from apps.certificados.servico_a1 import CertificadoDigitalA1Facade

__all__ = [
    'CertificadoDigitalA1Facade',
    'CertificadoDigitalError',
    'FinalidadeCertificado',
    'MetadadosCertificadoSeguros',
]
