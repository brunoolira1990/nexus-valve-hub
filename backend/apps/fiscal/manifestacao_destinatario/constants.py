"""Constantes e mapeamentos — Manifestação do Destinatário."""

from __future__ import annotations

from apps.fiscal.models import NFeDestinadaManifestacao

EVENTO_CIENCIA = 'CIENCIA_EMISSAO'
EVENTO_CONFIRMACAO = 'CONFIRMACAO_OPERACAO'
EVENTO_DESCONHECIMENTO = 'DESCONHECIMENTO'
EVENTO_NAO_REALIZADA = 'OPERACAO_NAO_REALIZADA'

EVENTOS_MANIFESTACAO = frozenset(
    {EVENTO_CIENCIA, EVENTO_CONFIRMACAO, EVENTO_DESCONHECIMENTO, EVENTO_NAO_REALIZADA},
)

# PyNFe EventoManifestacaoDest.operacao → tpEvento SEFAZ
PYNFE_OPERACAO_POR_EVENTO = {
    EVENTO_CONFIRMACAO: 1,  # 210200
    EVENTO_CIENCIA: 2,  # 210210
    EVENTO_DESCONHECIMENTO: 3,  # 210220
    EVENTO_NAO_REALIZADA: 4,  # 210240
}

CODIGO_SEFAZ_POR_EVENTO = {
    EVENTO_CONFIRMACAO: '210200',
    EVENTO_CIENCIA: '210210',
    EVENTO_DESCONHECIMENTO: '210220',
    EVENTO_NAO_REALIZADA: '210240',
}

STATUS_MANIFESTACAO_POR_EVENTO = {
    EVENTO_CIENCIA: NFeDestinadaManifestacao.StatusManifestacao.CIENTE,
    EVENTO_CONFIRMACAO: NFeDestinadaManifestacao.StatusManifestacao.CONFIRMADA,
    EVENTO_DESCONHECIMENTO: NFeDestinadaManifestacao.StatusManifestacao.DESCONHECIDA,
    EVENTO_NAO_REALIZADA: NFeDestinadaManifestacao.StatusManifestacao.NAO_REALIZADA,
}

DESCRICAO_EVENTO_USUARIO = {
    EVENTO_CIENCIA: (
        'Ciência da Emissão: registra que a empresa tomou conhecimento da NF-e. '
        'Não confirma recebimento da mercadoria.'
    ),
    EVENTO_CONFIRMACAO: (
        'Confirmação da Operação: confirma participação na operação e recebimento conforme NF-e.'
    ),
    EVENTO_DESCONHECIMENTO: (
        'Desconhecimento da Operação: informa desconhecimento da operação descrita na NF-e.'
    ),
    EVENTO_NAO_REALIZADA: (
        'Operação não Realizada: informa que a operação não foi realizada. Exige justificativa.'
    ),
}

EVENTOS_EXIGEM_JUSTIFICATIVA = frozenset({EVENTO_NAO_REALIZADA})

# Eventos que habilitam download do XML completo na distribuição DF-e (sem baixar automaticamente).
EVENTOS_LIBERAM_DOWNLOAD_XML = frozenset(
    {EVENTO_CIENCIA, EVENTO_CONFIRMACAO, EVENTO_NAO_REALIZADA},
)

MIN_JUSTIFICATIVA = 15
MAX_JUSTIFICATIVA = 255

MSG_SEM_PERMISSAO = (
    'Seu perfil não possui permissão para manifestação do destinatário. '
    'Contate um administrador do módulo fiscal.'
)
