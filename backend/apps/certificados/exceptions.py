"""Erros de domínio sanitizados — certificado digital A1."""

from __future__ import annotations

import re

CODE_NAO_CONFIGURADO = 'CERTIFICADO_NAO_CONFIGURADO'
CODE_ARQUIVO_INDISPONIVEL = 'CERTIFICADO_ARQUIVO_INDISPONIVEL'
CODE_SENHA_INVALIDA = 'CERTIFICADO_SENHA_INVALIDA'
CODE_INVALIDO = 'CERTIFICADO_INVALIDO'
CODE_EXPIRADO = 'CERTIFICADO_EXPIRADO'
CODE_FINALIDADE_NAO_SUPORTADA = 'FINALIDADE_NAO_SUPORTADA'

_PATH_RE = re.compile(r'(/[^\s]+)|([A-Za-z]:\\[^\s]+)')
_FILE_RE = re.compile(r'(?i)[^\s]*\.(pfx|p12|pem|key)')


class CertificadoDigitalError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = sanitizar_mensagem(detail)
        super().__init__(self.detail)

    def to_dict(self) -> dict[str, str]:
        return {'code': self.code, 'detail': self.detail}


def sanitizar_mensagem(mensagem: str | None) -> str:
    """Remove caminhos e nomes de arquivo; não altera mensagens-constante seguras."""
    texto = str(mensagem or '').strip() or 'Certificado digital indisponível.'
    texto = _PATH_RE.sub('[caminho removido]', texto)
    texto = _FILE_RE.sub('[arquivo removido]', texto)
    if len(texto) > 240:
        texto = texto[:239] + '…'
    return texto


MSG_NAO_CONFIGURADO = 'Certificado digital A1 não configurado para a empresa.'
MSG_ARQUIVO_INDISPONIVEL = 'Arquivo do certificado digital indisponível.'
MSG_SENHA_INVALIDA = 'Senha do certificado incorreta ou arquivo inválido.'
MSG_INVALIDO = 'Certificado digital inválido.'
MSG_EXPIRADO = 'Certificado digital expirado.'
MSG_FINALIDADE = 'Finalidade de uso do certificado não suportada.'
