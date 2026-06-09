"""Listas fixas e labels operacionais — ERP 4.0.14.1."""

from __future__ import annotations


class FormaPagamentoCodigo:
    PIX = 'PIX'
    BOLETO = 'BOLETO'
    TRANSFERENCIA_BANCARIA = 'TRANSFERENCIA_BANCARIA'
    DINHEIRO = 'DINHEIRO'
    CARTAO_CREDITO = 'CARTAO_CREDITO'
    CARTAO_DEBITO = 'CARTAO_DEBITO'
    CHEQUE = 'CHEQUE'
    DEPOSITO_BANCARIO = 'DEPOSITO_BANCARIO'
    SEM_MOVIMENTACAO_FINANCEIRA = 'SEM_MOVIMENTACAO_FINANCEIRA'
    OUTROS = 'OUTROS'

    CHOICES = [
        (PIX, 'Pix'),
        (BOLETO, 'Boleto'),
        (TRANSFERENCIA_BANCARIA, 'Transferência bancária'),
        (DINHEIRO, 'Dinheiro'),
        (CARTAO_CREDITO, 'Cartão de crédito'),
        (CARTAO_DEBITO, 'Cartão de débito'),
        (CHEQUE, 'Cheque'),
        (DEPOSITO_BANCARIO, 'Depósito bancário'),
        (SEM_MOVIMENTACAO_FINANCEIRA, 'Sem movimentação financeira'),
        (OUTROS, 'Outros'),
    ]

    REQUER_CONTA_REAL = {
        PIX,
        BOLETO,
        TRANSFERENCIA_BANCARIA,
        DINHEIRO,
        CARTAO_CREDITO,
        CARTAO_DEBITO,
        CHEQUE,
        DEPOSITO_BANCARIO,
        OUTROS,
    }


FORMA_PAGAMENTO_LABELS = dict(FormaPagamentoCodigo.CHOICES)


class TipoMovimentoFinanceiro:
    RECEBIMENTO = 'RECEBIMENTO'
    PAGAMENTO = 'PAGAMENTO'
    RECEBIMENTO_PARCIAL = 'RECEBIMENTO_PARCIAL'
    PAGAMENTO_PARCIAL = 'PAGAMENTO_PARCIAL'
    ABATIMENTO = 'ABATIMENTO'
    ABATIMENTO_DEVOLUCAO = 'ABATIMENTO_DEVOLUCAO'
    GERACAO_CREDITO = 'GERACAO_CREDITO'
    USO_CREDITO = 'USO_CREDITO'
    REEMBOLSO_CLIENTE = 'REEMBOLSO_CLIENTE'
    REEMBOLSO_FORNECEDOR = 'REEMBOLSO_FORNECEDOR'
    ESTORNO = 'ESTORNO'
    AJUSTE_MANUAL = 'AJUSTE_MANUAL'

    CHOICES = [
        (RECEBIMENTO, 'Recebimento'),
        (PAGAMENTO, 'Pagamento'),
        (RECEBIMENTO_PARCIAL, 'Recebimento parcial'),
        (PAGAMENTO_PARCIAL, 'Pagamento parcial'),
        (ABATIMENTO, 'Abatimento'),
        (ABATIMENTO_DEVOLUCAO, 'Abatimento por devolução'),
        (GERACAO_CREDITO, 'Crédito gerado'),
        (USO_CREDITO, 'Uso de crédito'),
        (REEMBOLSO_CLIENTE, 'Reembolso ao cliente'),
        (REEMBOLSO_FORNECEDOR, 'Reembolso do fornecedor'),
        (ESTORNO, 'Estorno'),
        (AJUSTE_MANUAL, 'Ajuste manual'),
    ]

    SEM_MOVIMENTACAO_CAIXA = {
        ABATIMENTO,
        ABATIMENTO_DEVOLUCAO,
        USO_CREDITO,
        GERACAO_CREDITO,
        ESTORNO,
        AJUSTE_MANUAL,
    }


TIPO_MOVIMENTO_LABELS = dict(TipoMovimentoFinanceiro.CHOICES)


def label_forma_pagamento(codigo: str) -> str:
    return FORMA_PAGAMENTO_LABELS.get(codigo, codigo.replace('_', ' ').title())


def label_tipo_movimento(codigo: str) -> str:
    return TIPO_MOVIMENTO_LABELS.get(codigo, codigo.replace('_', ' ').title())


def forma_requer_conta_real(codigo: str) -> bool:
    return codigo in FormaPagamentoCodigo.REQUER_CONTA_REAL


def formas_pagamento_api_payload() -> list[dict]:
    return [{'codigo': c, 'label': label} for c, label in FormaPagamentoCodigo.CHOICES]


def tipos_movimento_api_payload() -> list[dict]:
    return [{'codigo': c, 'label': label} for c, label in TipoMovimentoFinanceiro.CHOICES]
