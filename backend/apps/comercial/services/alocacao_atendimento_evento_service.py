"""Emissão append-only de AlocacaoAtendimentoEvento (S4C-B1 / R2).

Uma ação pública de negócio → no máximo um evento.
Payload allowlist; sem signals; sem dados fiscais/pessoais proibidos.
Append-only na camada de aplicação (ver modelo + testes R2).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import AlocacaoAtendimento, AlocacaoAtendimentoEvento

# Identificadores estáveis para chamadas sem ator autenticado (não sensíveis).
ORIGEM_SISTEMA_CRIAR_ALOCACAO = 'SISTEMA:CRIAR_ALOCACAO'
ORIGEM_SISTEMA_ATUALIZAR_ALOCACAO = 'SISTEMA:ATUALIZAR_ALOCACAO'
ORIGEM_SISTEMA_EXCLUIR_ALOCACAO = 'SISTEMA:EXCLUIR_ALOCACAO'
ORIGEM_SISTEMA_CONCILIAR_ENTRADA_VENDA = 'SISTEMA:CONCILIAR_ENTRADA_VENDA'
ORIGEM_SISTEMA_AJUSTAR_QUANTIDADE = 'SISTEMA:AJUSTAR_QUANTIDADE'
ORIGEM_SISTEMA_DESVINCULAR_ENTRADA_VENDA = 'SISTEMA:DESVINCULAR_ENTRADA_VENDA'

# Campos permitidos no snapshot operacional (antes/depois).
_CAMPOS_SNAPSHOT: tuple[str, ...] = (
    'id',
    'produto_id',
    'pedido_venda_item_id',
    'faturamento_item_id',
    'item_nf_saida_id',
    'pedido_compra_item_id',
    'nf_entrada_item_id',
    'nf_entrada_historica_item_id',
    'cte_historico_importado_id',
    'fornecedor_id',
    'quantidade_necessaria',
    'quantidade_atendida',
    'quantidade_pendente',
    'tipo_atendimento',
    'status_entrada_fiscal',
    'origem_fisica',
    'destino_fisico',
)

_CAMPOS_QTD = frozenset(
    {
        'quantidade_necessaria',
        'quantidade_atendida',
        'quantidade_pendente',
    },
)

# Metadados de negócio permitidos em ``depois`` (além do snapshot).
_EXTRAS_DEPOIS_PERMITIDOS = frozenset(
    {
        'acao_upsert',
        'campos_alterados',
        'alocacao_id_anterior',
    },
)

ATOR_ROTULO_MAX = 64
MOTIVO_MAX = 255


def _qty_json(v: Any) -> str:
    if v is None or v == '':
        return '0'
    return str(Decimal(str(v)).quantize(Decimal('0.001')))


def exigir_ator_ou_origem_sistema(*, ator=None, origem_sistema: str | None = None) -> None:
    """Falha de programação se não houver ator autenticado nem origem_sistema explícita.

    Deve ser chamada antes de qualquer mutação nos writers.
    Não usa rótulo genérico silencioso ``SISTEMA``.
    """
    from apps.comercial.services.alocacao_atendimento_service import AlocacaoAtendimentoErro

    if ator is not None and getattr(ator, 'pk', None):
        return
    if origem_sistema is None or not str(origem_sistema).strip():
        raise AlocacaoAtendimentoErro(
            'Chamada sem ator autenticado exige origem_sistema explícita '
            '(ex.: SISTEMA:CRIAR_ALOCACAO).',
        )


def snapshot_alocacao(alocacao: AlocacaoAtendimento | None) -> dict[str, Any]:
    """Snapshot allowlist de AlocacaoAtendimento (sem observações/XML/dados pessoais)."""
    if alocacao is None:
        return {}
    out: dict[str, Any] = {}
    for campo in _CAMPOS_SNAPSHOT:
        if campo == 'id':
            out['id'] = alocacao.pk
            continue
        val = getattr(alocacao, campo, None)
        if campo in _CAMPOS_QTD:
            out[campo] = _qty_json(val)
        else:
            out[campo] = val
    return out


def snapshots_iguais(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a == b


def campos_alterados(antes: dict[str, Any], depois: dict[str, Any]) -> list[str]:
    keys = sorted(set(antes) | set(depois))
    return [k for k in keys if antes.get(k) != depois.get(k)]


def _resolver_ator(
    ator,
    origem_sistema: str | None,
) -> tuple[Any, int | None, str]:
    """Retorna (ator_fk_ou_None, ator_id_snapshot, ator_rotulo_snapshot).

    Sem inventar usuário técnico. Sem e-mail/nome completo.
    Pré-condição: ``exigir_ator_ou_origem_sistema`` já foi satisfeita.
    """
    if ator is not None and getattr(ator, 'pk', None):
        username = (getattr(ator, 'username', None) or '').strip()
        rotulo = (username or f'user:{ator.pk}')[:ATOR_ROTULO_MAX]
        return ator, int(ator.pk), rotulo
    rotulo = str(origem_sistema).strip()[:ATOR_ROTULO_MAX]
    return None, None, rotulo


def registrar_evento_alocacao(
    *,
    evento: str,
    alocacao: AlocacaoAtendimento | None,
    alocacao_id_snapshot: int,
    antes: dict[str, Any] | None = None,
    depois: dict[str, Any] | None = None,
    ator=None,
    origem_sistema: str | None = None,
    motivo: str | None = None,
    extras_depois: dict[str, Any] | None = None,
) -> AlocacaoAtendimentoEvento:
    """Persiste um evento imutável na transação corrente.

    Único ponto de escrita de ``AlocacaoAtendimentoEvento`` nos services públicos.
    """
    exigir_ator_ou_origem_sistema(ator=ator, origem_sistema=origem_sistema)
    ator_fk, ator_id_snap, ator_rotulo = _resolver_ator(ator, origem_sistema)
    antes_payload = dict(antes or {})
    depois_payload = dict(depois or {})
    if extras_depois:
        for k, v in extras_depois.items():
            if k in _EXTRAS_DEPOIS_PERMITIDOS:
                depois_payload[k] = v

    hist_id = None
    pvi_id = None
    if alocacao is not None:
        hist_id = alocacao.nf_entrada_historica_item_id
        pvi_id = alocacao.pedido_venda_item_id
    else:
        hist_id = antes_payload.get('nf_entrada_historica_item_id') or depois_payload.get(
            'nf_entrada_historica_item_id',
        )
        pvi_id = antes_payload.get('pedido_venda_item_id') or depois_payload.get('pedido_venda_item_id')

    motivo_limpo = (motivo or '').strip()[:MOTIVO_MAX]

    return AlocacaoAtendimentoEvento.objects.create(
        evento=evento,
        alocacao=alocacao,
        alocacao_id_snapshot=int(alocacao_id_snapshot),
        ator=ator_fk,
        ator_id_snapshot=ator_id_snap,
        ator_rotulo_snapshot=ator_rotulo,
        nf_entrada_historica_item_id_snapshot=int(hist_id) if hist_id else None,
        pedido_venda_item_id_snapshot=int(pvi_id) if pvi_id else None,
        antes=antes_payload,
        depois=depois_payload,
        motivo=motivo_limpo,
    )
