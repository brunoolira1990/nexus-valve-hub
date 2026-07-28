"""Mapeamento de metadados seguros a partir do carregador fiscal (somente leitura)."""

from __future__ import annotations

from apps.certificados.contratos import FinalidadeCertificado, MetadadosCertificadoSeguros
from apps.certificados.exceptions import MSG_EXPIRADO, MSG_INVALIDO


def metadados_de_info_fiscal(info, *, finalidade: FinalidadeCertificado) -> MetadadosCertificadoSeguros:
    """
    Converte CertificadoA1Info fiscal em metadados seguros.

    Descarta caminho, CNPJ, subject, serial, emissor e mensagens detalhadas.
    """
    expirado = bool(getattr(info, 'expirado', False))
    valido = bool(getattr(info, 'valido', False)) and not expirado
    motivo = None
    if expirado:
        motivo = MSG_EXPIRADO
    elif not valido:
        motivo = MSG_INVALIDO
    return MetadadosCertificadoSeguros(
        disponivel=valido,
        valido=valido,
        tipo='A1',
        finalidade=finalidade.value,
        vence_em=getattr(info, 'validade_fim', None),
        dias_para_expirar=getattr(info, 'expira_em_dias', None),
        motivo_indisponibilidade=motivo,
    )
