"""Serializers auxiliares — Reforma Tributária NF-e para API."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida
from apps.fiscal.reforma_tributaria.calculo import calcular_reforma_tributaria_nfe_item
from apps.fiscal.reforma_tributaria.config import reforma_nfe_config, status_reforma_nfe_documento
from apps.fiscal.reforma_tributaria.validacoes import alerta_reforma_antes_homologacao

STATUS_LABELS = {
    'nao_aplicavel': 'Reforma Tributária não aplicada a esta NF-e.',
    'nao_preparada': 'Estrutura em pesquisa/preparação — XML/DANFE seguem layout atual.',
    'preparacao': 'Estrutura preparada, mas não incluída no XML/DANFE.',
    'configurada_sem_xml': 'Dados configurados na conferência; XML/DANFE ainda sem grupos RTC.',
    'homologacao': 'Dados da Reforma incluídos no XML/DANFE de homologação (quando flags ativas).',
    'bloqueada_producao': 'Geração em produção bloqueada até validação oficial.',
}


def montar_payload_reforma_tributaria_nfe(nf: NFeSaida) -> dict[str, Any]:
    cfg = reforma_nfe_config()
    status = status_reforma_nfe_documento(nf)
    itens = []
    if hasattr(nf, 'itens'):
        for item in nf.itens.all():
            calc = calcular_reforma_tributaria_nfe_item(item)
            if calc.get('aplicavel'):
                itens.append({'item_id': item.pk, **calc})

    tot_cbs = tot_ibs = tot_is = 0
    for row in itens:
        tot_cbs += float(row.get('cbs', {}).get('valor', 0) or 0)
        tot_ibs += float(row.get('ibs', {}).get('total', 0) or 0)

    alerta = alerta_reforma_antes_homologacao(nf)

    return {
        'status': status,
        'status_label': STATUS_LABELS.get(status, status),
        'config': {
            'enabled': cfg['enabled'],
            'modo': cfg['modo'],
            'incluir_xml': cfg['incluir_xml'],
            'incluir_danfe': cfg['incluir_danfe'],
            'producao_bloqueada': cfg['producao_bloqueada'],
        },
        'alerta_homologacao': alerta,
        'itens': itens,
        'totais': {
            'valor_cbs': f'{tot_cbs:.2f}',
            'valor_ibs': f'{tot_ibs:.2f}',
            'valor_imposto_seletivo': f'{tot_is:.2f}',
        },
    }
