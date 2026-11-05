"""Registro de auditoria para ações de domínio da entrada de terceiros (Fase 1).

Divergência do precedente, documentada: `registrar_nfe_entrada` vive em
`apps/auditoria/servico.py:475` (precedente único até aqui). As funções novas
vivem em `apps/fiscal/auditoria_entrada.py` por coesão de domínio e escala —
as Fases 1–3 do redesenho da entrada adicionam múltiplas funções `registrar_*`
de entrada, e o app `auditoria` deve continuar genérico (não conhece modelos
fiscais). Não há duplicação de infra de gravação: `registrar_nfe_entrada` é um
wrapper fino sobre `registrar_auditoria` (servico.py), e este arquivo chama o
MESMO helper, apenas com os kwargs novos (`acao`, `anexos`,
`permitir_evento_sem_diff`).

# TODO(fase-X): avaliar mover registrar_nfe_entrada para cá e unificar o padrão
# de registrar_* de domínio em apps/fiscal/. NÃO fazer essa movação na Fase 1
# (fora de escopo; risco de quebrar os callsites de CREATE/UPDATE em
# apps/fiscal/serializers.py:619/:656).

Contrato (fixado pelo PO em 2026-11-04):
- Assinatura: registrar_X(entidade, usuario, acao, *, estado_anterior=None, detalhes=None).
- Com `estado_anterior` (dict ou instância congelada antes do save): diff real
  no formato before/after do repo, mesmo que `registrar_nfe_entrada` produz.
- Sem `estado_anterior` (evento puro): diff vazio + snapshot da allowlist sob a
  chave reservada `_snapshot`; `detalhes` (se vier) sob `_detalhes`.
- 2 chamadas com os mesmos args = 2 eventos distintos (ação de negócio é fato
  histórico, não upsert). Sem unique constraint.
- Robustez: qualquer falha (inclusive entidade fora do escopo) é logada e a
  função devolve None; a ação de negócio NUNCA é derrubada pela auditoria.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.models import AbstractBaseUser

from apps.auditoria.escopo import entidade_auditada_permitida
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.politicas import (
    CTE_HISTORICO_IMPORTADO_ALLOWLIST,
    CTE_HISTORICO_IMPORTADO_CAMPOS_MASCARADOS,
    NFE_ENTRADA_CONFERENCIA_ALLOWLIST,
    NFE_ENTRADA_CONFERENCIA_CAMPOS_MASCARADOS,
    NFE_ENTRADA_HISTORICA_IMPORTADA_ALLOWLIST,
    NFE_ENTRADA_HISTORICA_IMPORTADA_CAMPOS_MASCARADOS,
)
from apps.auditoria.servico import capturar_snapshot, registrar_auditoria, serializar_valor_seguro

logger = logging.getLogger(__name__)

# model_name (lowercase da classe, a mesma chave de MODELOS_AUDITADOS) ->
# (allowlist, mascarados). Resolver do próprio `entidade._meta` mantém as
# funções agnósticas de qual dos três documentos recebe.
_CONTEXTO_ENTRADA: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    # Grafia real de meta.model_name: 'nfeentradahistoricaimportada' (com "c" de
    # Historica -> HistoricaImportada). A spec escrevia '...inportada'; o disco
    # prevaleceu (verificado em teste, escopo.py e serializers de histórico).
    'nfeentradahistoricaimportada': (
        NFE_ENTRADA_HISTORICA_IMPORTADA_ALLOWLIST,
        NFE_ENTRADA_HISTORICA_IMPORTADA_CAMPOS_MASCARADOS,
    ),
    'nfeentradaconferencia': (
        NFE_ENTRADA_CONFERENCIA_ALLOWLIST,
        NFE_ENTRADA_CONFERENCIA_CAMPOS_MASCARADOS,
    ),
    'ctehistoricoimportado': (
        CTE_HISTORICO_IMPORTADO_ALLOWLIST,
        CTE_HISTORICO_IMPORTADO_CAMPOS_MASCARADOS,
    ),
}

# Ações recomendadas por função: divergir daqui não é erro duro (a coluna `acao`
# aceita qualquer nome máquina até 40 chars), mas loga warning para o fluxo
# novo de PR 3 não inventar grafia sem revisão.
ACOES_CONFERENCIA = frozenset({'conferir', 'reabrir', 'marcar_divergente', 'desvincular_alocacoes_venda'})
ACOES_ESTOQUE = frozenset({'preparar_estoque', 'aplicar_estoque', 'reverter_estoque'})
ACOES_FINANCEIRO = frozenset({'gerar_contas_pagar', 'estornar_contas'})
ACOES_DEVOLUCAO = frozenset({'gerar_saida_devolucao_compra'})


def _registrar_evento_entrada(
    entidade: Any,
    usuario: AbstractBaseUser | None,
    acao: str,
    *,
    estado_anterior: Any | None = None,
    detalhes: dict[str, Any] | None = None,
    acoes_recomendadas: frozenset[str] | None = None,
) -> RegistroAuditoria | None:
    try:
        meta = entidade._meta
        par = entidade_auditada_permitida(meta.app_label, meta.model_name)
        if par is None:
            logger.error(
                'auditoria-entrada: %s.%s fora de MODELOS_AUDITADOS; evento "%s" não registrado',
                meta.app_label,
                meta.model_name,
                acao,
            )
            return None
        if acoes_recomendadas is not None and acao not in acoes_recomendadas:
            logger.warning(
                'auditoria-entrada: acao "%s" fora das recomendadas %s para este registrador',
                acao,
                sorted(acoes_recomendadas),
            )
        if not acao or len(acao) > 40:
            logger.error('auditoria-entrada: acao inválida %r (vazia ou > 40 chars)', acao)
            return None

        allowlist, mascarados = _CONTEXTO_ENTRADA[meta.model_name]
        depois = capturar_snapshot(entidade, allowlist)

        anexos: dict[str, Any] = {}
        if estado_anterior is None:
            # Evento puro: sem diff de campos; o estado no momento da ação vai
            # inteiro em `_snapshot` (só campos da allowlist — nunca o objeto cru).
            antes = dict(depois)
            anexos['_snapshot'] = serializar_valor_seguro(depois)
        else:
            if isinstance(estado_anterior, dict):
                antes = estado_anterior
            else:
                antes = capturar_snapshot(estado_anterior, allowlist)
        if detalhes:
            anexos['_detalhes'] = serializar_valor_seguro(detalhes)

        return registrar_auditoria(
            usuario=usuario,
            app_label=par[0],
            model_name=par[1],
            object_id=entidade.pk,
            operacao='UPDATE',
            estado_anterior=antes,
            estado_posterior=depois,
            allowlist=allowlist,
            mascarados=mascarados,
            acao=acao,
            anexos=anexos or None,
            permitir_evento_sem_diff=True,
        )
    except Exception:
        # Auditoria jamais derruba a ação de negócio (fiscal/estoque/financeiro).
        logger.exception(
            'auditoria-entrada: falha ao registrar ação %r sobre %r', acao, entidade
        )
        return None


def registrar_conferencia_nfe(
    entidade: Any,
    usuario: AbstractBaseUser | None,
    acao: str,
    *,
    estado_anterior: Any | None = None,
    detalhes: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    """Conferência de entrada: 'conferir', 'reabrir', 'marcar_divergente', 'desvincular_alocacoes_venda'.

    Aceita `NFeEntradaConferencia` (status e *_por_id vivem nela) ou
    `NFeEntradaHistoricaImportada`/`CTeHistoricoImportado` quando a ação altera
    o documento em si — o modelo auditado é sempre o da entidade recebida.
    """
    return _registrar_evento_entrada(
        entidade,
        usuario,
        acao,
        estado_anterior=estado_anterior,
        detalhes=detalhes,
        acoes_recomendadas=ACOES_CONFERENCIA,
    )


def registrar_estoque_nfe(
    entidade: Any,
    usuario: AbstractBaseUser | None,
    acao: str,
    *,
    estado_anterior: Any | None = None,
    detalhes: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    """Efeitos de estoque da conferência: 'preparar_estoque', 'aplicar_estoque', 'reverter_estoque'."""
    return _registrar_evento_entrada(
        entidade,
        usuario,
        acao,
        estado_anterior=estado_anterior,
        detalhes=detalhes,
        acoes_recomendadas=ACOES_ESTOQUE,
    )


def registrar_financeiro_nfe(
    entidade: Any,
    usuario: AbstractBaseUser | None,
    acao: str,
    *,
    estado_anterior: Any | None = None,
    detalhes: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    """Financeiro da NF-e de entrada: 'gerar_contas_pagar', 'estornar_contas'."""
    return _registrar_evento_entrada(
        entidade,
        usuario,
        acao,
        estado_anterior=estado_anterior,
        detalhes=detalhes,
        acoes_recomendadas=ACOES_FINANCEIRO,
    )


def registrar_financeiro_cte(
    entidade: Any,
    usuario: AbstractBaseUser | None,
    acao: str,
    *,
    estado_anterior: Any | None = None,
    detalhes: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    """Financeiro do CT-e de entrada (frete/rateio): 'gerar_contas_pagar', 'estornar_contas'."""
    return _registrar_evento_entrada(
        entidade,
        usuario,
        acao,
        estado_anterior=estado_anterior,
        detalhes=detalhes,
        acoes_recomendadas=ACOES_FINANCEIRO,
    )


def registrar_devolucao_nfe(
    entidade: Any,
    usuario: AbstractBaseUser | None,
    acao: str = 'gerar_saida_devolucao_compra',
    *,
    estado_anterior: Any | None = None,
    detalhes: dict[str, Any] | None = None,
) -> RegistroAuditoria | None:
    """Devolução de compra gerada da conferência: 'gerar_saida_devolucao_compra' (default)."""
    return _registrar_evento_entrada(
        entidade,
        usuario,
        acao,
        estado_anterior=estado_anterior,
        detalhes=detalhes,
        acoes_recomendadas=ACOES_DEVOLUCAO,
    )
