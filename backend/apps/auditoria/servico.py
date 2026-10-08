"""Serviço explícito de auditoria — chamado pelos fluxos de escrita cobertos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.politicas import (
    CAMPOS_BLOQUEADOS_SEMPRE,
    CLIENTE_ALLOWLIST,
    CLIENTE_CAMPOS_MASCARADOS,
    PRODUTO_ALLOWLIST,
    PRODUTO_CAMPOS_MASCARADOS,
    STRING_MAX_LEN,
)


def _eh_bloqueado(campo: str) -> bool:
    nome = (campo or '').strip().lower()
    if nome in CAMPOS_BLOQUEADOS_SEMPRE:
        return True
    for token in CAMPOS_BLOQUEADOS_SEMPRE:
        if token in nome:
            return True
    return False


def serializar_valor_seguro(valor: Any) -> Any:
    """Serializa tipos comuns de forma previsível; limita strings."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, Decimal):
        return format(valor, 'f')
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (int, float)):
        return valor
    if isinstance(valor, (list, tuple)):
        return [serializar_valor_seguro(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): serializar_valor_seguro(v) for k, v in valor.items()}
    texto = str(valor)
    if len(texto) > STRING_MAX_LEN:
        return texto[:STRING_MAX_LEN] + '…'
    return texto


def _normalizar_comparacao(valor: Any) -> Any:
    if valor is None:
        return None
    if isinstance(valor, str) and valor.strip() == '':
        return None
    if isinstance(valor, Decimal):
        return format(valor, 'f')
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor
    return serializar_valor_seguro(valor)


def valores_diferentes(antes: Any, depois: Any) -> bool:
    return _normalizar_comparacao(antes) != _normalizar_comparacao(depois)


def capturar_snapshot(instance: Any, allowlist: frozenset[str]) -> dict[str, Any]:
    """Extrai somente campos da allowlist a partir do model (sem model_to_dict irrestrito)."""
    out: dict[str, Any] = {}
    for campo in allowlist:
        if campo.endswith('_id') and hasattr(instance, campo):
            out[campo] = getattr(instance, campo, None)
            continue
        if campo.endswith('_id'):
            base = campo[:-3]
            out[campo] = getattr(instance, f'{base}_id', None)
            continue
        if hasattr(instance, campo):
            out[campo] = getattr(instance, campo)
    return out


def montar_alteracoes(
    antes: dict[str, Any],
    depois: dict[str, Any],
    *,
    allowlist: frozenset[str],
    mascarados: frozenset[str],
) -> dict[str, Any]:
    alteracoes: dict[str, Any] = {}
    campos = set(allowlist) | set(antes) | set(depois)
    for campo in sorted(campos):
        if campo not in allowlist:
            continue
        if _eh_bloqueado(campo):
            a = antes.get(campo)
            d = depois.get(campo)
            if valores_diferentes(a, d):
                alteracoes[campo] = {'sensivel': True, 'alterado': True}
            continue
        a = antes.get(campo)
        d = depois.get(campo)
        if not valores_diferentes(a, d):
            continue
        if campo in mascarados:
            alteracoes[campo] = {'sensivel': True, 'alterado': True}
        else:
            alteracoes[campo] = {
                'antes': serializar_valor_seguro(a),
                'depois': serializar_valor_seguro(d),
            }
    return alteracoes


def registrar_auditoria(
    *,
    usuario: AbstractBaseUser | None,
    app_label: str,
    model_name: str,
    object_id: int,
    operacao: str,
    estado_anterior: dict[str, Any],
    estado_posterior: dict[str, Any],
    allowlist: frozenset[str],
    mascarados: frozenset[str],
) -> RegistroAuditoria | None:
    """
    Persiste um registro se houver diff real.

    Deve ser chamado dentro da mesma transação da alteração principal:
    falha de auditoria reverte a escrita; rollback da escrita reverte a auditoria.
    """
    alteracoes = montar_alteracoes(
        estado_anterior,
        estado_posterior,
        allowlist=allowlist,
        mascarados=mascarados,
    )
    if not alteracoes:
        return None

    ator = usuario if usuario is not None and getattr(usuario, 'is_authenticated', False) else None
    ator_id = getattr(ator, 'pk', None) if ator is not None else None

    return RegistroAuditoria.objects.create(
        app_label=app_label,
        model_name=model_name,
        object_id=object_id,
        operacao=operacao,
        alteracoes=alteracoes,
        ator_id=ator_id,
    )


def registrar_cliente(
    *,
    usuario: AbstractBaseUser | None,
    cliente,
    operacao: str,
    estado_anterior: dict[str, Any],
    estado_posterior: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    depois = estado_posterior if estado_posterior is not None else capturar_snapshot(cliente, CLIENTE_ALLOWLIST)
    return registrar_auditoria(
        usuario=usuario,
        app_label='cadastros',
        model_name='cliente',
        object_id=cliente.pk,
        operacao=operacao,
        estado_anterior=estado_anterior,
        estado_posterior=depois,
        allowlist=CLIENTE_ALLOWLIST,
        mascarados=CLIENTE_CAMPOS_MASCARADOS,
    )


def registrar_produto(
    *,
    usuario: AbstractBaseUser | None,
    produto,
    operacao: str,
    estado_anterior: dict[str, Any],
    estado_posterior: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    depois = estado_posterior if estado_posterior is not None else capturar_snapshot(produto, PRODUTO_ALLOWLIST)
    return registrar_auditoria(
        usuario=usuario,
        app_label='produtos',
        model_name='produto',
        object_id=produto.pk,
        operacao=operacao,
        estado_anterior=estado_anterior,
        estado_posterior=depois,
        allowlist=PRODUTO_ALLOWLIST,
        mascarados=PRODUTO_CAMPOS_MASCARADOS,
    )


def snapshot_cliente(cliente) -> dict[str, Any]:
    return capturar_snapshot(cliente, CLIENTE_ALLOWLIST)


def snapshot_produto(produto) -> dict[str, Any]:
    return capturar_snapshot(produto, PRODUTO_ALLOWLIST)


def usuario_do_contexto(serializer) -> AbstractBaseUser | None:
    request = serializer.context.get('request') if serializer and serializer.context else None
    if request is None:
        return None
    return getattr(request, 'user', None)
