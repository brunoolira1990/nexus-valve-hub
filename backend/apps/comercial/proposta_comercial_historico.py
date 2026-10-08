"""Histórico comercial estruturado da proposta."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.comercial.models import PropostaComercialHistorico

if TYPE_CHECKING:
    from apps.comercial.models import Proposta


def _usuario_id(usuario) -> int | None:
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        return usuario.pk
    return None


def registrar_evento_comercial(
    proposta: Proposta,
    tipo_evento: str,
    *,
    descricao: str,
    usuario=None,
    dados_json: dict[str, Any] | None = None,
) -> PropostaComercialHistorico:
    return PropostaComercialHistorico.objects.create(
        proposta=proposta,
        tipo_evento=tipo_evento,
        descricao=(descricao or '').strip(),
        usuario_id=_usuario_id(usuario),
        dados_json=dados_json,
    )


def listar_historico_comercial(proposta: Proposta) -> dict[str, Any]:
    from apps.comercial.serializers import PropostaComercialHistoricoSerializer

    eventos = (
        PropostaComercialHistorico.objects.filter(proposta_id=proposta.pk)
        .select_related('usuario')
        .order_by('-criado_em', '-id')
    )
    ser = PropostaComercialHistoricoSerializer(eventos, many=True)
    return {'proposta_id': proposta.pk, 'eventos': ser.data}
