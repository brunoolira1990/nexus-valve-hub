"""Registro auditável de ações do monitor de manifestação."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeDestinadaManifestacao, NFeDestinadaManifestacaoEvento


def registrar_evento_manifestacao(
    documento: NFeDestinadaManifestacao | None,
    *,
    tipo_acao: str,
    descricao: str,
    usuario=None,
    empresa=None,
    codigo_evento: str = '',
    ambiente: str = '',
    resultado_resumido: str = '',
    cstat: str = '',
    xmotivo: str = '',
    dados_json: dict[str, Any] | None = None,
) -> NFeDestinadaManifestacaoEvento:
    user_id = None
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        user_id = usuario.pk
    empresa_id = None
    if documento is not None:
        empresa_id = documento.empresa_id
    elif empresa is not None:
        empresa_id = empresa.pk
    amb = (ambiente or (documento.ambiente if documento else '') or '').strip()
    return NFeDestinadaManifestacaoEvento.objects.create(
        documento=documento,
        empresa_id=empresa_id,
        tipo_acao=tipo_acao,
        codigo_evento=(codigo_evento or '').strip(),
        descricao=(descricao or '').strip(),
        usuario_id=user_id,
        ambiente=amb,
        resultado_resumido=(resultado_resumido or '').strip()[:255],
        cstat=(cstat or '').strip(),
        xmotivo=(xmotivo or '').strip()[:255],
        dados_json=dados_json,
    )
