"""Flags operacionais derivadas — ERP 4.0.14.2.1 / 4.0.14.2.2."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.financeiro.constants import TipoMovimentoFinanceiro
from apps.financeiro.models import (
    CreditoFinanceiro,
    CreditoFinanceiroEvento,
    FinanceiroEvento,
    TituloFinanceiro,
)
from apps.financeiro.status import CENTAVO

CREDITO_ORIGENS_EXCLUIVEIS = frozenset(
    {
        CreditoFinanceiro.OrigemTipo.MANUAL,
        CreditoFinanceiro.OrigemTipo.AJUSTE,
    },
)

TIPOS_REEMBOLSO = frozenset(
    {
        TipoMovimentoFinanceiro.REEMBOLSO_CLIENTE,
        TipoMovimentoFinanceiro.REEMBOLSO_FORNECEDOR,
    },
)

MSG_TITULO_EXCLUIR_ORIGEM = (
    'Este título veio de outro documento e não pode ser excluído pelo Financeiro.'
)
MSG_TITULO_EXCLUIR_MOVIMENTO_ATIVO = (
    'Este título possui movimentações financeiras ativas. Estorne os movimentos antes de excluir.'
)
MSG_TITULO_EXCLUIR_GENERICO = (
    'Este título possui movimentações ativas ou vínculo de origem e não pode ser excluído. '
    'Cancele ou estorne os movimentos para manter o histórico.'
)

MSG_CREDITO_EXCLUIR_ORIGEM = (
    'Este crédito possui movimentações ativas ou vínculo de origem e não pode ser excluído. '
    'Cancele ou estorne os movimentos para manter o histórico.'
)
MSG_CREDITO_EXCLUIR_MOVIMENTO_ATIVO = (
    'Este crédito possui movimentações financeiras ativas. Estorne os movimentos antes de excluir.'
)
MSG_CREDITO_EXCLUIR_GENERICO = MSG_CREDITO_EXCLUIR_ORIGEM


def _saldo_integral(valor_original: Decimal, valor_atual: Decimal, valor_movido: Decimal) -> bool:
    return (
        abs(valor_atual - valor_original) <= CENTAVO
        and valor_movido <= CENTAVO
    )


def titulo_origem_manual(titulo: TituloFinanceiro) -> bool:
    return titulo.origem_tipo == TituloFinanceiro.OrigemTipo.MANUAL


def titulo_possui_vinculo_origem(titulo: TituloFinanceiro) -> bool:
    if titulo.origem_tipo != TituloFinanceiro.OrigemTipo.MANUAL:
        return True
    return bool(titulo.origem_id)


def titulo_baixas_ativas(titulo: TituloFinanceiro):
    return titulo.baixas.filter(estornada=False)


def titulo_possui_movimento_financeiro_ativo(titulo: TituloFinanceiro) -> bool:
    if titulo.cancelado:
        return True
    return titulo_baixas_ativas(titulo).exists()


def titulo_possui_movimento_financeiro(titulo: TituloFinanceiro) -> bool:
    if titulo.cancelado:
        return True
    if titulo.baixas.exists():
        return True
    return titulo.eventos.exclude(acao=FinanceiroEvento.Acao.CRIACAO).exists()


def titulo_possui_apenas_movimentos_estornados(titulo: TituloFinanceiro) -> bool:
    return titulo.baixas.exists() and not titulo_baixas_ativas(titulo).exists()


def titulo_motivo_bloqueio_exclusao(titulo: TituloFinanceiro) -> str:
    if titulo.cancelado:
        return MSG_TITULO_EXCLUIR_GENERICO
    if not titulo_origem_manual(titulo) or titulo_possui_vinculo_origem(titulo):
        return MSG_TITULO_EXCLUIR_ORIGEM
    if titulo_possui_movimento_financeiro_ativo(titulo):
        return MSG_TITULO_EXCLUIR_MOVIMENTO_ATIVO
    valor_original = titulo.valor_original or Decimal('0')
    valor_baixado = titulo.valor_baixado or Decimal('0')
    valor_aberto = titulo.valor_aberto or Decimal('0')
    if not _saldo_integral(valor_original, valor_aberto, valor_baixado):
        return MSG_TITULO_EXCLUIR_MOVIMENTO_ATIVO
    status = titulo.status or ''
    if status not in (
        TituloFinanceiro.Status.EM_ABERTO,
        TituloFinanceiro.Status.VENCIDO,
    ):
        return MSG_TITULO_EXCLUIR_GENERICO
    return ''


def titulo_pode_excluir(titulo: TituloFinanceiro) -> bool:
    return not titulo_motivo_bloqueio_exclusao(titulo)


def titulo_exclusao_flags(titulo: TituloFinanceiro) -> dict[str, Any]:
    valor_original = titulo.valor_original or Decimal('0')
    valor_baixado = titulo.valor_baixado or Decimal('0')
    valor_aberto = titulo.valor_aberto or Decimal('0')
    movimento_ativo = titulo_possui_movimento_financeiro_ativo(titulo)
    return {
        'pode_excluir': titulo_pode_excluir(titulo),
        'origem_manual': titulo_origem_manual(titulo),
        'possui_movimento_financeiro': titulo_possui_movimento_financeiro(titulo),
        'possui_movimento_financeiro_ativo': movimento_ativo,
        'possui_apenas_movimentos_estornados': titulo_possui_apenas_movimentos_estornados(titulo),
        'possui_vinculo_origem': titulo_possui_vinculo_origem(titulo),
        'motivo_bloqueio_exclusao': titulo_motivo_bloqueio_exclusao(titulo),
        'saldo_integral_reaberto': _saldo_integral(valor_original, valor_aberto, valor_baixado),
        'valor_movimentado_ativo_zero': valor_baixado <= CENTAVO,
    }


def credito_possui_vinculo_origem(credito: CreditoFinanceiro) -> bool:
    return credito.origem_tipo not in CREDITO_ORIGENS_EXCLUIVEIS


def credito_movimentos_ativos(credito: CreditoFinanceiro):
    return credito.movimentos.filter(estornada=False)


def credito_possui_movimento_ativo(credito: CreditoFinanceiro) -> bool:
    if credito.cancelado:
        return True
    if (credito.valor_utilizado or Decimal('0')) > CENTAVO:
        return True
    return credito_movimentos_ativos(credito).exists()


def credito_possui_movimento(credito: CreditoFinanceiro) -> bool:
    """Histórico com efeito ou auditoria além da criação."""
    if credito.cancelado:
        return True
    if credito.movimentos.exists():
        return True
    return credito.eventos.exclude(acao=CreditoFinanceiroEvento.Acao.CRIACAO).exists()


def credito_possui_aplicacao_ativa(credito: CreditoFinanceiro) -> bool:
    return credito_movimentos_ativos(credito).filter(
        tipo_movimento=TipoMovimentoFinanceiro.USO_CREDITO,
    ).exists()


def credito_possui_reembolso_ativo(credito: CreditoFinanceiro) -> bool:
    return credito_movimentos_ativos(credito).filter(
        tipo_movimento__in=TIPOS_REEMBOLSO,
    ).exists()


def credito_possui_apenas_movimentos_estornados(credito: CreditoFinanceiro) -> bool:
    return credito.movimentos.exists() and not credito_movimentos_ativos(credito).exists()


def credito_motivo_bloqueio_exclusao(credito: CreditoFinanceiro) -> str:
    if credito.cancelado:
        return MSG_CREDITO_EXCLUIR_GENERICO
    if credito_possui_vinculo_origem(credito):
        return MSG_CREDITO_EXCLUIR_ORIGEM
    if credito.status != CreditoFinanceiro.Status.DISPONIVEL:
        return MSG_CREDITO_EXCLUIR_GENERICO
    valor_original = credito.valor_original or Decimal('0')
    saldo = credito.saldo or Decimal('0')
    valor_utilizado = credito.valor_utilizado or Decimal('0')
    if not _saldo_integral(valor_original, saldo, valor_utilizado):
        return MSG_CREDITO_EXCLUIR_MOVIMENTO_ATIVO
    if credito_possui_movimento_ativo(credito):
        return MSG_CREDITO_EXCLUIR_MOVIMENTO_ATIVO
    if credito_possui_aplicacao_ativa(credito) or credito_possui_reembolso_ativo(credito):
        return MSG_CREDITO_EXCLUIR_MOVIMENTO_ATIVO
    return ''


def credito_operational_flags(credito: CreditoFinanceiro) -> dict[str, Any]:
    cancelado = bool(credito.cancelado)
    valor_utilizado = credito.valor_utilizado or Decimal('0')
    valor_original = credito.valor_original or Decimal('0')
    saldo = credito.saldo or Decimal('0')
    exclusao = {
        'pode_excluir': not credito_motivo_bloqueio_exclusao(credito),
        'possui_vinculo_origem': credito_possui_vinculo_origem(credito),
        'motivo_bloqueio_exclusao': credito_motivo_bloqueio_exclusao(credito),
        'saldo_integral_reaberto': _saldo_integral(valor_original, saldo, valor_utilizado),
    }

    possui_mov = credito_possui_movimento(credito)
    possui_mov_ativo = credito_possui_movimento_ativo(credito)
    possui_aplicacao = credito.movimentos.filter(
        tipo_movimento=TipoMovimentoFinanceiro.USO_CREDITO,
    ).exists()
    possui_aplicacao_ativa = credito_possui_aplicacao_ativa(credito)
    possui_estorno = credito.eventos.filter(
        acao=CreditoFinanceiroEvento.Acao.ESTORNO_APLICACAO,
    ).exists()

    pode_editar_completo = not cancelado and not possui_mov_ativo
    pode_editar = not cancelado
    pode_cancelar = not cancelado and valor_utilizado <= CENTAVO

    return {
        'pode_aplicar': credito.pode_aplicar,
        'pode_cancelar': pode_cancelar,
        'pode_editar': pode_editar,
        'pode_editar_completo': pode_editar_completo,
        'possui_movimento': possui_mov,
        'possui_movimento_ativo': possui_mov_ativo,
        'possui_apenas_movimentos_estornados': credito_possui_apenas_movimentos_estornados(credito),
        'possui_aplicacao': possui_aplicacao,
        'possui_aplicacao_ativa': possui_aplicacao_ativa,
        'possui_estorno': possui_estorno,
        **exclusao,
    }
