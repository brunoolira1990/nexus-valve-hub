"""Ajustes fiscais manuais (F2) — só em apuração RASCUNHO."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from django.db import transaction
from django.db.models import QuerySet

from ..models import ApuracaoAjusteManual, ApuracaoFiscal, LogsAuditoriaApuracao
from .fechamento import ApuracaoFiscalError, _registrar_log


def sinal_ajuste(tipo: str) -> Decimal:
    """
    Impacto no saldo final (ICMS gerencial):
    - DEBITO: +valor (aumenta saldo a pagar)
    - CREDITO: -valor (reduz saldo)
    - ESTORNO: -valor (anula/reduz como crédito)
    """
    if tipo == ApuracaoAjusteManual.Tipo.DEBITO:
        return Decimal('1')
    if tipo in (ApuracaoAjusteManual.Tipo.CREDITO, ApuracaoAjusteManual.Tipo.ESTORNO):
        return Decimal('-1')
    raise ApuracaoFiscalError(f'Tipo de ajuste inválido: {tipo}', codigo='TIPO_AJUSTE_INVALIDO')


def impacto_ajuste(tipo: str, valor: Decimal | str | int | float) -> Decimal:
    v = Decimal(str(valor))
    return (sinal_ajuste(tipo) * v).quantize(Decimal('0.01'))


def somar_ajustes_liquido(ajustes: Iterable[ApuracaoAjusteManual] | QuerySet) -> Decimal:
    total = Decimal('0')
    for a in ajustes:
        total += impacto_ajuste(a.tipo, a.valor)
    return total.quantize(Decimal('0.01'))


def saldo_final_apuracao(apuracao: ApuracaoFiscal, *, liquido: Decimal | None = None) -> Decimal:
    """saldo_icms (snapshot) + Σ impactos dos ajustes manuais."""
    base = Decimal(str(apuracao.saldo_icms or 0))
    if liquido is None:
        liquido = somar_ajustes_liquido(apuracao.ajustes_manuais.all())
    return (base + liquido).quantize(Decimal('0.01'))


def _exigir_rascunho(apuracao: ApuracaoFiscal) -> None:
    if apuracao.status != ApuracaoFiscal.Status.RASCUNHO:
        raise ApuracaoFiscalError(
            'Ajustes manuais só são permitidos com apuração em RASCUNHO.',
            codigo='APURACAO_FECHADA_AJUSTE',
        )


def listar_ajustes(apuracao_id: int) -> QuerySet[ApuracaoAjusteManual]:
    return (
        ApuracaoAjusteManual.objects.filter(apuracao_id=apuracao_id)
        .select_related('usuario')
        .order_by('-criado_em', '-id')
    )


@transaction.atomic
def adicionar_ajuste(
    apuracao_id: int,
    *,
    tipo: str,
    valor: Decimal | str | int | float,
    motivo: str,
    usuario,
) -> tuple[ApuracaoAjusteManual, Decimal, Decimal]:
    """
    Cria ajuste e log AJUSTE_ADICIONADO.

    Returns: (ajuste, ajustes_liquido, saldo_final)
    """
    apuracao = ApuracaoFiscal.objects.select_for_update().get(pk=apuracao_id)
    _exigir_rascunho(apuracao)

    tipo_n = str(tipo or '').strip().upper()
    if tipo_n not in {
        ApuracaoAjusteManual.Tipo.DEBITO,
        ApuracaoAjusteManual.Tipo.CREDITO,
        ApuracaoAjusteManual.Tipo.ESTORNO,
    }:
        raise ApuracaoFiscalError('Tipo deve ser DEBITO, CREDITO ou ESTORNO.', codigo='TIPO_AJUSTE_INVALIDO')

    motivo_limpo = (motivo or '').strip()
    if len(motivo_limpo) < 5:
        raise ApuracaoFiscalError(
            'Motivo obrigatório com pelo menos 5 caracteres.',
            codigo='MOTIVO_OBRIGATORIO',
        )

    valor_d = Decimal(str(valor)).quantize(Decimal('0.01'))
    if valor_d <= 0:
        raise ApuracaoFiscalError('Valor deve ser maior que zero.', codigo='VALOR_INVALIDO')

    ajuste = ApuracaoAjusteManual.objects.create(
        apuracao=apuracao,
        tipo=tipo_n,
        valor=valor_d,
        motivo=motivo_limpo,
        usuario=usuario if getattr(usuario, 'pk', None) else None,
    )
    liquido = somar_ajustes_liquido(apuracao.ajustes_manuais.all())
    final = saldo_final_apuracao(apuracao, liquido=liquido)
    _registrar_log(
        apuracao,
        acao=LogsAuditoriaApuracao.Acao.AJUSTE_ADICIONADO,
        usuario=usuario,
        detalhe={
            'ajuste_id': ajuste.id,
            'tipo': ajuste.tipo,
            'valor': str(ajuste.valor),
            'motivo': ajuste.motivo,
            'impacto': str(impacto_ajuste(ajuste.tipo, ajuste.valor)),
            'ajustes_liquido': str(liquido),
            'saldo_icms_snapshot': str(apuracao.saldo_icms),
            'saldo_final': str(final),
        },
    )
    return ajuste, liquido, final


@transaction.atomic
def remover_ajuste(
    apuracao_id: int,
    ajuste_id: int,
    *,
    usuario,
) -> tuple[ApuracaoAjusteManual, Decimal, Decimal]:
    """
    Remove ajuste e log AJUSTE_REMOVIDO.

    Returns: (ajuste_removido_snapshot_in_memory, ajustes_liquido, saldo_final)
    """
    apuracao = ApuracaoFiscal.objects.select_for_update().get(pk=apuracao_id)
    _exigir_rascunho(apuracao)

    try:
        ajuste = ApuracaoAjusteManual.objects.select_for_update().get(
            pk=ajuste_id, apuracao_id=apuracao_id
        )
    except ApuracaoAjusteManual.DoesNotExist as exc:
        raise ApuracaoFiscalError('Ajuste não encontrado nesta apuração.', codigo='AJUSTE_NAO_ENCONTRADO') from exc

    detalhe = {
        'ajuste_id': ajuste.id,
        'tipo': ajuste.tipo,
        'valor': str(ajuste.valor),
        'motivo': ajuste.motivo,
        'impacto': str(impacto_ajuste(ajuste.tipo, ajuste.valor)),
    }
    ajuste_id_removido = ajuste.id
    tipo_rem = ajuste.tipo
    valor_rem = ajuste.valor
    motivo_rem = ajuste.motivo
    ajuste.delete()

    liquido = somar_ajustes_liquido(apuracao.ajustes_manuais.all())
    final = saldo_final_apuracao(apuracao, liquido=liquido)
    detalhe.update(
        {
            'ajustes_liquido': str(liquido),
            'saldo_icms_snapshot': str(apuracao.saldo_icms),
            'saldo_final': str(final),
        }
    )
    _registrar_log(
        apuracao,
        acao=LogsAuditoriaApuracao.Acao.AJUSTE_REMOVIDO,
        usuario=usuario,
        detalhe=detalhe,
    )
    # objeto “fantasma” para serializar resposta
    fantasma = ApuracaoAjusteManual(
        id=ajuste_id_removido,
        apuracao_id=apuracao_id,
        tipo=tipo_rem,
        valor=valor_rem,
        motivo=motivo_rem,
    )
    return fantasma, liquido, final


def resumo_ajustes(apuracao: ApuracaoFiscal) -> dict[str, Any]:
    qs = list(apuracao.ajustes_manuais.all())
    liquido = somar_ajustes_liquido(qs)
    return {
        'quantidade': len(qs),
        'ajustes_liquido': liquido,
        'saldo_icms_snapshot': Decimal(str(apuracao.saldo_icms or 0)),
        'saldo_final': saldo_final_apuracao(apuracao, liquido=liquido),
    }
