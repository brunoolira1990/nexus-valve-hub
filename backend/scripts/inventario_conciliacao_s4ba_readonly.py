#!/usr/bin/env python
"""S4B-A — inventário anônimo da conciliação Entrada ↔ Venda (SOMENTE LEITURA).

NÃO executar automaticamente em produção nesta etapa.
NÃO imprimir IDs, clientes, fornecedores, produtos, documentos, chaves NF-e,
quantidades individuais nem observações.

Uso manual (quando autorizado), a partir de backend/:

  python manage.py shell < scripts/inventario_conciliacao_s4ba_readonly.py
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.db.models import Count

from apps.comercial.services.alocacao_entrada_venda_service import (
    TOL,
    estado_operacional_entrada,
    quantidade_disponivel_entrada,
    total_alocado_entrada,
)
from apps.fiscal.dfe_classificacao import eh_documento_homologacao
from apps.fiscal.models import AlocacaoAtendimento, ItemNFeEntradaConferencia


def _estado_para_origem(hist_id: int) -> str:
    try:
        conf = ItemNFeEntradaConferencia.objects.get(item_nfe_historico_id=hist_id)
        disponivel = quantidade_disponivel_entrada(conf)
    except Exception:
        disponivel = Decimal('0')
    alocado = total_alocado_entrada(hist_id)
    return estado_operacional_entrada(quantidade_disponivel=disponivel, total_alocado=alocado)


def run_inventario_anonimo() -> None:
    qs = AlocacaoAtendimento.objects.all()
    total = qs.count()
    print('=== S4B-A inventário anônimo (read-only) ===')
    print(f'total_alocacoes={total}')

    por_tipo = {
        row['tipo_atendimento']: row['c']
        for row in qs.values('tipo_atendimento').annotate(c=Count('id'))
    }
    print(f'por_tipo_atendimento={por_tipo}')

    por_status = {
        row['status_entrada_fiscal']: row['c']
        for row in qs.values('status_entrada_fiscal').annotate(c=Count('id'))
    }
    print(f'por_status_entrada_fiscal={por_status}')

    hist_ids = list(
        qs.exclude(nf_entrada_historica_item_id__isnull=True)
        .values_list('nf_entrada_historica_item_id', flat=True)
        .distinct(),
    )
    estados = Counter(_estado_para_origem(int(hid)) for hid in hist_ids)
    print(f'origens_historicas_por_estado_quantitativo={dict(estados)}')

    combos = Counter()
    for row in qs.values('tipo_atendimento', 'status_entrada_fiscal').annotate(c=Count('id')):
        combos[f"{row['tipo_atendimento']}|{row['status_entrada_fiscal']}"] = row['c']
    print(f'combinacoes_tipo_x_status={dict(combos)}')

    itens_pv_multi = (
        qs.exclude(pedido_venda_item_id__isnull=True)
        .values('pedido_venda_item_id')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
        .count()
    )
    print(f'itens_pv_com_mais_de_uma_alocacao={itens_pv_multi}')

    origens_multi = (
        qs.exclude(nf_entrada_historica_item_id__isnull=True)
        .values('nf_entrada_historica_item_id')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
        .count()
    )
    print(f'itens_entrada_historica_com_mais_de_uma_alocacao={origens_multi}')

    print(f'origens_com_estado_divergente={estados.get("DIVERGENTE", 0)}')
    print(f'tolerancia_decimal_usada={TOL}')

    homolog = 0
    sem_cstat_ok = 0
    for aloc in qs.exclude(nf_entrada_historica_item_id__isnull=True).select_related(
        'nf_entrada_historica_item__nf',
    ):
        nf = getattr(aloc.nf_entrada_historica_item, 'nf', None)
        if nf is None:
            continue
        if eh_documento_homologacao(nf):
            homolog += 1
        cstat = str(getattr(nf, 'cstat', '') or '').strip()
        if cstat and cstat != '100':
            sem_cstat_ok += 1
    print(f'vinculos_com_nf_homologacao={homolog}')
    print(f'vinculos_com_cstat_diferente_de_100={sem_cstat_ok}')
    print('=== fim inventário (nenhuma escrita) ===')


run_inventario_anonimo()
