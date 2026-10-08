"""Baixa e estorno financeiro."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.financeiro.constants import FormaPagamentoCodigo, TipoMovimentoFinanceiro, forma_requer_conta_real
from apps.financeiro.models import BaixaFinanceira, FinanceiroEvento, ParcelaFinanceira, TituloFinanceiro
from apps.financeiro.services.eventos import registrar_evento_financeiro
from apps.financeiro.services.movimento import _resolver_parcela_saldo
from apps.financeiro.services.titulo import somar_baixas_titulo

CENTAVO = Decimal('0.01')


class BaixaFinanceiraError(ValueError):
    pass


def _tipo_movimento_baixa(titulo: TituloFinanceiro, parcial: bool) -> str:
    if titulo.tipo == TituloFinanceiro.Tipo.RECEBER:
        return (
            TipoMovimentoFinanceiro.RECEBIMENTO_PARCIAL
            if parcial
            else TipoMovimentoFinanceiro.RECEBIMENTO
        )
    return (
        TipoMovimentoFinanceiro.PAGAMENTO_PARCIAL
        if parcial
        else TipoMovimentoFinanceiro.PAGAMENTO
    )


@transaction.atomic
def registrar_baixa_financeira(
    titulo: TituloFinanceiro,
    *,
    data_baixa: date,
    valor: Decimal,
    forma_pagamento_codigo: str,
    conta_financeira_id: int | None = None,
    parcela_id: int | None = None,
    juros: Decimal = Decimal('0'),
    multa: Decimal = Decimal('0'),
    desconto: Decimal = Decimal('0'),
    tarifa: Decimal = Decimal('0'),
    observacoes: str = '',
    usuario=None,
) -> BaixaFinanceira:
    if titulo.cancelado:
        raise BaixaFinanceiraError('Título cancelado não aceita baixa.')
    if not titulo.pode_baixar:
        raise BaixaFinanceiraError('Não há saldo em aberto para baixa.')

    if forma_requer_conta_real(forma_pagamento_codigo) and not conta_financeira_id:
        raise BaixaFinanceiraError('Informe a conta financeira para esta forma de pagamento.')

    valor = valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if valor <= 0:
        raise BaixaFinanceiraError('Informe um valor maior que zero.')

    parcela, saldo = _resolver_parcela_saldo(titulo, parcela_id)
    max_permitido = saldo + juros + multa - desconto
    if valor > max_permitido + CENTAVO:
        raise BaixaFinanceiraError(
            'O valor da baixa excede o saldo em aberto. Informe juros ou multa se aplicável.'
        )

    parcial_antes = titulo.valor_aberto > valor + CENTAVO
    tipo_mov = _tipo_movimento_baixa(titulo, parcial_antes)

    baixa = BaixaFinanceira.objects.create(
        titulo=titulo,
        parcela=parcela,
        tipo_movimento=tipo_mov,
        forma_pagamento_codigo=forma_pagamento_codigo,
        data_baixa=data_baixa,
        valor=valor,
        conta_financeira_id=conta_financeira_id,
        juros=juros.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        multa=multa.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        desconto=desconto.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        tarifa=tarifa.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        observacoes=observacoes or '',
        registrada_por=usuario,
    )

    if parcela:
        parcela.recalcular_saldos_e_status()
    titulo.recalcular_saldos_e_status()
    parcial = titulo.valor_aberto > CENTAVO
    if titulo.tipo == TituloFinanceiro.Tipo.RECEBER:
        msg = (
            'Recebimento parcial registrado. Ainda há saldo em aberto.'
            if parcial
            else 'Recebimento registrado com sucesso.'
        )
    else:
        msg = (
            'Pagamento parcial registrado. Ainda há saldo em aberto.'
            if parcial
            else 'Pagamento registrado com sucesso.'
        )

    parcela_ref = ''
    if parcela:
        parcela_ref = f' (parcela {parcela.numero_parcela:03d})'

    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.BAIXA_PARCIAL if parcial else FinanceiroEvento.Acao.BAIXA,
        descricao=f'Baixa de R$ {valor} em {data_baixa}{parcela_ref}. {msg}',
        usuario=usuario,
        dados_novos={
            'baixa_id': baixa.pk,
            'valor': str(valor),
            'parcela_id': parcela.pk if parcela else None,
            'tipo_movimento': tipo_mov,
            'forma_pagamento_codigo': forma_pagamento_codigo,
        },
    )
    return baixa


@transaction.atomic
def estornar_baixa_financeira(
    baixa: BaixaFinanceira,
    *,
    motivo: str,
    usuario=None,
) -> BaixaFinanceira:
    from apps.financeiro.services.credito import estornar_uso_credito

    if baixa.tipo_movimento == TipoMovimentoFinanceiro.USO_CREDITO:
        return estornar_uso_credito(baixa, motivo=motivo, usuario=usuario)

    if baixa.estornada:
        raise BaixaFinanceiraError('Esta baixa já foi estornada.')
    motivo = (motivo or '').strip()
    if not motivo:
        raise BaixaFinanceiraError('Informe o motivo do estorno.')

    baixa.estornada = True
    baixa.motivo_estorno = motivo
    baixa.estornada_em = timezone.now()
    baixa.estornada_por = usuario
    baixa.save(
        update_fields=[
            'estornada',
            'motivo_estorno',
            'estornada_em',
            'estornada_por',
        ],
    )

    titulo = baixa.titulo
    parcela = baixa.parcela
    if parcela:
        parcela.recalcular_saldos_e_status()
    titulo.recalcular_saldos_e_status()
    _ = somar_baixas_titulo(titulo)

    parcela_ref = ''
    if parcela:
        parcela_ref = f' Parcela {parcela.numero_parcela:03d} reaberta.'

    if baixa.tipo_movimento == TipoMovimentoFinanceiro.ABATIMENTO_DEVOLUCAO:
        desc = f'Abatimento por devolução estornado. Saldo reaberto.{parcela_ref} Motivo: {motivo}'
    else:
        desc = f'Baixa estornada. O saldo do título foi reaberto.{parcela_ref} Motivo: {motivo}'

    registrar_evento_financeiro(
        titulo,
        acao=FinanceiroEvento.Acao.ESTORNO,
        descricao=desc,
        usuario=usuario,
        dados_anteriores={
            'baixa_id': baixa.pk,
            'valor': str(baixa.valor),
            'parcela_id': parcela.pk if parcela else None,
            'tipo_movimento': baixa.tipo_movimento,
        },
    )
    return baixa
