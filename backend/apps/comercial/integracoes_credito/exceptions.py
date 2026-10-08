"""Erros de domínio sanitizados — consultas externas B2/B3."""

from __future__ import annotations


class IntegracaoCreditoError(Exception):
    """Erro de negócio da integração de crédito/cadastral (sem dados sensíveis)."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)

    def to_dict(self) -> dict[str, str]:
        return {'code': self.code, 'detail': self.detail}


CODE_PROVIDER_NAO_CONFIGURADO = 'PROVIDER_NAO_CONFIGURADO'
CODE_BURO_NAO_CONTRATADO = 'BURO_NAO_CONTRATADO'
CODE_PROVIDER_DESCONHECIDO = 'PROVIDER_DESCONHECIDO'
CODE_CONSULTA_DESABILITADA = 'CONSULTA_DESABILITADA'

MSG_CADASTRAL_NAO_CONFIGURADO = 'A consulta cadastral externa ainda não está configurada.'
MSG_BURO_NAO_CONTRATADO = 'Não há birô de crédito contratado para esta funcionalidade.'
MSG_PROVIDER_GENERICO = 'A integração externa ainda não está configurada.'
