"""Agregações leves para pendências operacionais no BI (Qualidade e Estoque)."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum

from apps.corridas.models import Corrida
from apps.fiscal.models import EstoqueCorrida
from apps.produtos.models import Produto
from apps.qualidade.models import CertificadoFornecedorEntrada, CertificadoQualidade, ItemCertificadoQualidade
from apps.qualidade.rastreabilidade_cq import (
    avaliar_rastreabilidade_item_certificado_qualidade,
    montar_resumo_rastreabilidade_certificado,
)


def resumo_pendencias_qualidade() -> dict[str, int]:
    cq_rascunho = CertificadoQualidade.objects.filter(status=CertificadoQualidade.Status.RASCUNHO).count()
    cf_rascunho = CertificadoFornecedorEntrada.objects.filter(
        status=CertificadoFornecedorEntrada.Status.RASCUNHO,
    ).count()
    cf_registrados = CertificadoFornecedorEntrada.objects.filter(
        status=CertificadoFornecedorEntrada.Status.REGISTRADO,
    ).count()
    corridas = Corrida.objects.count()

    cq_rastreabilidade_pendente = 0
    for cq in (
        CertificadoQualidade.objects.filter(status=CertificadoQualidade.Status.RASCUNHO)
        .prefetch_related('itens')
        .order_by('-criado_em')[:200]
    ):
        itens = [item for item in cq.itens.all() if item.incluir_no_certificado]
        if not itens:
            continue
        resumo = montar_resumo_rastreabilidade_certificado(itens)
        if resumo['pendentes'] > 0:
            cq_rastreabilidade_pendente += 1

    itens_rastreabilidade_pendente = 0
    for item in (
        ItemCertificadoQualidade.objects.filter(
            certificado__status=CertificadoQualidade.Status.RASCUNHO,
            incluir_no_certificado=True,
        )
        .select_related('certificado')
        .order_by('-id')[:500]
    ):
        if avaliar_rastreabilidade_item_certificado_qualidade(item)['status'] == 'PENDENTE':
            itens_rastreabilidade_pendente += 1

    return {
        'cq_emitidos': CertificadoQualidade.objects.filter(status=CertificadoQualidade.Status.EMITIDO).count(),
        'cq_rascunho': cq_rascunho,
        'cq_rastreabilidade_pendente': cq_rastreabilidade_pendente,
        'itens_rastreabilidade_pendente': itens_rastreabilidade_pendente,
        'cf_rascunho': cf_rascunho,
        'cf_registrados': cf_registrados,
        'corridas': corridas,
        'pendencias_total': cq_rascunho + cf_rascunho + cq_rastreabilidade_pendente,
    }


def resumo_pendencias_produto_estoque() -> dict[str, int]:
    saldo_map = {
        row['produto_id']: Decimal(str(row['total'] or 0))
        for row in EstoqueCorrida.objects.values('produto_id').annotate(total=Sum('saldo'))
    }
    produtos_com_saldo = {pid for pid, saldo in saldo_map.items() if saldo > Decimal('0')}
    produtos_com_corrida = set(Corrida.objects.values_list('produto_id', flat=True))
    produtos_sem_corrida = Produto.objects.exclude(pk__in=produtos_com_corrida).count()
    sem_corrida_com_saldo = len(produtos_com_saldo - produtos_com_corrida)

    sem_ncm_qs = Produto.objects.filter(Q(ncm='') | Q(ncm__isnull=True))
    sem_ncm = sem_ncm_qs.count()
    sem_ncm_com_saldo = sem_ncm_qs.filter(pk__in=produtos_com_saldo).count()

    return {
        'produtos_sem_corrida': produtos_sem_corrida,
        'sem_corrida_com_saldo': sem_corrida_com_saldo,
        'sem_ncm_com_saldo': sem_ncm_com_saldo,
        'sem_ncm': sem_ncm,
        'produtos_com_saldo': len(produtos_com_saldo),
    }
