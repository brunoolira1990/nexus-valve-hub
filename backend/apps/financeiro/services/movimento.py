"""Abatimentos e movimentos sem caixa — ERP 4.0.14.1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro
from apps.financeiro.models import BaixaFinanceira, FinanceiroEvento, ParcelaFinanceira, TituloFinanceiro
from apps.financeiro.services.eventos import registrar_evento_financeiro

CENTAVO = Decimal('0.01')


class MovimentoFinanceiroError(ValueError):
    pass


def _resolver_parcela_saldo(
    titulo: TituloFinanceiro,
    parcela_id: int | None,
) -> tuple[ParcelaFinanceira | None, Decimal]:
    parcela: ParcelaFinanceira | None = None
    if parcela_id:
        parcela = ParcelaFinanceira.objects.filter(pk=parcela_id, titulo=titulo).first()
        if not parcela:
            raise MovimentoFinanceiroError('Parcela não encontrada para este título.')
        return parcela, parcela.valor_aberto
    qtd = titulo.parcelas.count()
    if qtd > 1:
        raise MovimentoFinanceiroError('Selecione a parcela para este movimento.')
    if qtd == 1:
        parcela = titulo.parcelas.first()
        return parcela, parcela.valor_aberto
    return None, titulo.valor_aberto


@transaction.atomic
def registrar_abatimento_devolucao(
    titulo: TituloFinanceiro,
    *,
    valor: Decimal,
    data_abatimento: date,
    motivo: str,
    parcela_id: int | None = None,
    documento_referencia: str = '',
    observacoes: str = '',
    usuario=None,
) -> BaixaFinanceira:
    if titulo.cancelado:
        raise MovimentoFinanceiroError('Título cancelado não aceita abatimento.')
    if not titulo.pode_baixar:
        raise MovimentoFinanceiroError('Não há saldo em aberto para abatimento.')
    motivo = (motivo or '').strip()
    if not motivo:
        raise MovimentoFinanceiroError('Informe o motivo do abatimento por devolução.')

    valor = valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if valor <= 0:
        raise MovimentoFinanceiroError('Informe um valor maior que zero.')

    parcela, saldo = _resolver_parcela_saldo(titulo, parcela_id)
    if valor > saldo + CENTAVO:
        raise MovimentoFinanceiroError('O valor do abatimento excede o saldo em aberto.')

    obs_parts = [motivo]
    if documento_referencia:
        obs_parts.append(f'Ref.: {documento_referencia}')
    if observacoes:
        obs_parts.append(observacoes)

    baixa = BaixaFinanceira.objects.create(
        titulo=titulo,
        parcela=parcela,
        tipo_movimento=TipoMovimentoFinanceiro.ABATIMENTO_DEVOLUCAO,
        forma_pagamento_codigo=FormaPagamentoCodigo.SEM_MOVIMENTACAO_FINANCEIRA,
        data_baixa=data_abatimento,
        valor=valor,
        conta_financeira=None,
        observacoes=' — '.join(obs_parts),
        registrada_por=usuario,
    )
    if parcela:
        parcela.recalcular_saldos_e_status()
    titulo.recalcular_saldos_e_status()

    parcela_ref = f', parcela {parcela.numero_parcela:03d}' if parcela else ''
    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.ABATIMENTO_DEVOLUCAO,
        descricao=f'Abatimento por devolução registrado no valor de R$ {valor:.2f}{parcela_ref}. {motivo}',
        usuario=usuario,
        dados_novos={'baixa_id': baixa.pk, 'valor': str(valor)},
    )
    return baixa
