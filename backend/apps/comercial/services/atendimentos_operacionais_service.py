"""ERP 4.0.13.1 — listagem consolidada de atendimentos operacionais (AlocacaoAtendimento)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.fiscal.modelo_operacional import (
    DestinoFisico,
    OrigemFisica,
    StatusEntradaFiscal,
    TipoAtendimentoItem,
)
from apps.fiscal.models import AlocacaoAtendimento


def queryset_atendimentos_operacionais() -> QuerySet:
    from apps.comercial.services.alocacao_atendimento_service import queryset_base

    return queryset_base().select_related(
        'pedido_venda_item__pedido__cliente',
        'produto',
    )


def _parse_bool(val: Any) -> bool:
    if val is True:
        return True
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ('1', 'true', 'yes', 'sim', 'on')


def _parse_date(val: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not val:
        return None
    try:
        d = datetime.strptime(val.strip()[:10], '%Y-%m-%d').date()
    except ValueError:
        return None
    if end_of_day:
        return timezone.make_aware(datetime.combine(d, datetime.max.time().replace(microsecond=0)))
    return timezone.make_aware(datetime.combine(d, datetime.min.time()))


def aplicar_search(qs: QuerySet, search: str) -> QuerySet:
    term = (search or '').strip()
    if not term:
        return qs
    from apps.core.document_numbering import filtrar_queryset_por_numeros_documento

    return filtrar_queryset_por_numeros_documento(
        qs,
        term,
        'pedido_venda_item__pedido__numero',
        'faturamento_item__faturamento__numero_faturamento',
        'item_nf_saida__nf__numero',
        'pedido_compra_item__pedido__numero',
        q_extra=(
            Q(pedido_venda_item__pedido__cliente__razao_social__icontains=term)
            | Q(pedido_venda_item__pedido__cliente__nome_fantasia__icontains=term)
            | Q(produto__codigo_completo__icontains=term)
            | Q(produto__descricao__icontains=term)
            | Q(fornecedor__razao_social__icontains=term)
            | Q(fornecedor__nome_fantasia__icontains=term)
            | Q(observacao_operacional__icontains=term)
        ),
    ).distinct()


def filtrar_atendimentos_operacionais(params: dict[str, Any]) -> QuerySet:
    from apps.comercial.services.alocacao_atendimento_service import filtrar_alocacoes

    base_params = {
        k: params[k]
        for k in (
            'pedido_venda',
            'produto',
            'fornecedor',
            'tipo_atendimento',
            'status_entrada_fiscal',
            'origem_fisica',
            'destino_fisico',
        )
        if params.get(k) is not None
    }
    if params.get('pedido_venda_id'):
        base_params['pedido_venda'] = params['pedido_venda_id']
    if params.get('produto_id'):
        base_params['produto'] = params['produto_id']
    if params.get('fornecedor_id'):
        base_params['fornecedor'] = params['fornecedor_id']
    if params.get('nfe_saida_id'):
        base_params['nfe_saida'] = params['nfe_saida_id']

    qs = filtrar_alocacoes(base_params) if base_params else queryset_atendimentos_operacionais()

    if params.get('cliente_id'):
        qs = qs.filter(pedido_venda_item__pedido__cliente_id=params['cliente_id'])
    if params.get('pedido_compra_id'):
        qs = qs.filter(pedido_compra_item__pedido_id=params['pedido_compra_id'])

    if _parse_bool(params.get('tem_compra_vinculada')):
        qs = qs.filter(pedido_compra_item_id__isnull=False)
    if _parse_bool(params.get('somente_sem_compra')):
        qs = qs.filter(pedido_compra_item_id__isnull=True)
    if _parse_bool(params.get('tem_nfe_entrada_vinculada')):
        qs = qs.filter(
            Q(nf_entrada_historica_item_id__isnull=False) | Q(nf_entrada_item_id__isnull=False),
        )
    if _parse_bool(params.get('tem_cte_vinculado')) or _parse_bool(params.get('somente_com_cte')):
        qs = qs.filter(cte_historico_importado_id__isnull=False)

    if _parse_bool(params.get('somente_pendentes')):
        qs = qs.filter(
            Q(quantidade_pendente__gt=0) | Q(status_entrada_fiscal=StatusEntradaFiscal.PENDENTE),
        )

    data_inicio = _parse_date(params.get('data_inicio'))
    data_fim = _parse_date(params.get('data_fim'), end_of_day=True)
    if data_inicio:
        qs = qs.filter(criado_em__gte=data_inicio)
    if data_fim:
        qs = qs.filter(criado_em__lte=data_fim)

    search = (params.get('search') or '').strip()
    if search:
        qs = aplicar_search(qs, search)

    return qs.select_related('pedido_venda_item__pedido__cliente')


def _fmt_decimal(v: Decimal | None) -> str:
    if v is None:
        return '0.000'
    return f'{v:.3f}'


def _choice_label(choices, value: str) -> str:
    return dict(choices).get(value, value or '')


def _cliente_nome(cliente) -> str:
    if not cliente:
        return ''
    return (cliente.nome_fantasia or cliente.razao_social or '').strip()


def _nfe_titulo(nf) -> str:
    if not nf:
        return ''
    from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida

    return (montar_apresentacao_nfe_saida(nf) or {}).get('titulo_exibicao') or ''


def _alertas_linha(alocacao: AlocacaoAtendimento) -> list[str]:
    from apps.comercial.services.alocacao_atendimento_vinculos import montar_vinculos_exibicao

    alertas: list[str] = []
    v = montar_vinculos_exibicao(alocacao)
    for msg in v.get('alertas_vinculo') or []:
        if msg not in alertas:
            alertas.append(msg)
    if alocacao.status_entrada_fiscal == StatusEntradaFiscal.PENDENTE:
        alertas.append('Entrada fiscal pendente')
    if not alocacao.pedido_compra_item_id:
        alertas.append('Sem pedido de compra vinculado')
    if not (alocacao.nf_entrada_historica_item_id or alocacao.nf_entrada_item_id):
        if alocacao.status_entrada_fiscal in (
            StatusEntradaFiscal.PENDENTE,
            StatusEntradaFiscal.RECEBIDA,
        ):
            alertas.append('Sem NF-e entrada vinculada')
    if not alocacao.cte_historico_importado_id and (
        alocacao.nf_entrada_historica_item_id
        or alocacao.status_entrada_fiscal == StatusEntradaFiscal.PENDENTE
    ):
        alertas.append('CT-e não vinculado')
    return alertas


def serializar_atendimento_operacional(alocacao: AlocacaoAtendimento) -> dict[str, Any]:
    from apps.comercial.services.resumo_atendimento_operacional import _montar_resumo_from_alocacoes

    pedido = None
    if alocacao.pedido_venda_item_id and alocacao.pedido_venda_item:
        ped = alocacao.pedido_venda_item.pedido
        if ped:
            pedido = {'id': ped.pk, 'numero': ped.numero}

    faturamento = None
    if alocacao.faturamento_item_id and alocacao.faturamento_item:
        fat = alocacao.faturamento_item.faturamento
        if fat:
            faturamento = {'id': fat.pk, 'numero_faturamento': fat.numero_faturamento or ''}

    nfe_saida = None
    nf = None
    if alocacao.item_nf_saida_id and alocacao.item_nf_saida:
        nf = alocacao.item_nf_saida.nf
        if nf:
            nfe_saida = {'id': nf.pk, 'titulo': _nfe_titulo(nf)}

    cliente = None
    if alocacao.pedido_venda_item_id and alocacao.pedido_venda_item:
        cli = getattr(alocacao.pedido_venda_item.pedido, 'cliente', None)
        if cli:
            cliente = {'id': cli.pk, 'nome': _cliente_nome(cli)}

    produto = alocacao.produto
    produto_data = {
        'id': produto.pk,
        'codigo': produto.codigo_completo or '',
        'descricao': produto.descricao or '',
    }

    fornecedor = None
    if alocacao.fornecedor_id and alocacao.fornecedor:
        f = alocacao.fornecedor
        fornecedor = {
            'id': f.pk,
            'nome': (f.nome_fantasia or f.razao_social or '').strip(),
        }

    pedido_compra = None
    if alocacao.pedido_compra_item_id and alocacao.pedido_compra_item:
        pc = alocacao.pedido_compra_item.pedido
        if pc:
            pedido_compra = {'id': pc.pk, 'numero': pc.numero}

    nfe_entrada = None
    if alocacao.nf_entrada_historica_item_id and alocacao.nf_entrada_historica_item:
        item_nf = alocacao.nf_entrada_historica_item
        if item_nf.nf_id and item_nf.nf:
            nf_e = item_nf.nf
            status_conf = ''
            try:
                status_conf = item_nf.nf.conferencia.status
            except Exception:
                status_conf = ''
            nfe_entrada = {
                'id': nf_e.pk,
                'numero': f'{nf_e.numero}/{nf_e.serie or "—"}',
                'status_conferencia': status_conf,
            }
    elif alocacao.nf_entrada_item_id and alocacao.nf_entrada_item:
        item_nf = alocacao.nf_entrada_item
        if item_nf.nf_id and item_nf.nf:
            nf_e = item_nf.nf
            nfe_entrada = {
                'id': nf_e.pk,
                'numero': getattr(nf_e, 'numero', '') or f'#{nf_e.pk}',
                'status_conferencia': '',
            }

    cte = None
    if alocacao.cte_historico_importado_id and alocacao.cte_historico_importado:
        c = alocacao.cte_historico_importado
        cte = {
            'id': c.pk,
            'numero': f'{c.numero}/{c.serie or "—"}',
            'status_conferencia': c.status_conferencia or '',
        }

    resumo = _montar_resumo_from_alocacoes([alocacao], contexto='documento')

    return {
        'id': alocacao.pk,
        'pedido_venda': pedido,
        'faturamento': faturamento,
        'nfe_saida': nfe_saida,
        'cliente': cliente,
        'produto': produto_data,
        'quantidade_necessaria': _fmt_decimal(alocacao.quantidade_necessaria),
        'quantidade_atendida': _fmt_decimal(alocacao.quantidade_atendida),
        'quantidade_pendente': _fmt_decimal(alocacao.quantidade_pendente),
        'tipo_atendimento': alocacao.tipo_atendimento,
        'tipo_atendimento_label': _choice_label(TipoAtendimentoItem.choices, alocacao.tipo_atendimento),
        'status_entrada_fiscal': alocacao.status_entrada_fiscal,
        'status_entrada_fiscal_label': _choice_label(
            StatusEntradaFiscal.choices,
            alocacao.status_entrada_fiscal,
        ),
        'origem_fisica': alocacao.origem_fisica,
        'origem_fisica_label': _choice_label(OrigemFisica.choices, alocacao.origem_fisica),
        'destino_fisico': alocacao.destino_fisico,
        'destino_fisico_label': _choice_label(DestinoFisico.choices, alocacao.destino_fisico),
        'fornecedor': fornecedor,
        'pedido_compra': pedido_compra,
        'nfe_entrada': nfe_entrada,
        'cte': cte,
        'badges': resumo.get('badges', []),
        'alertas': _alertas_linha(alocacao),
        'observacao_operacional': alocacao.observacao_operacional or '',
        'criado_em': alocacao.criado_em.isoformat() if alocacao.criado_em else None,
    }


def calcular_kpis_atendimentos_operacionais(qs: QuerySet | None = None) -> dict[str, int]:
    base = qs if qs is not None else queryset_atendimentos_operacionais()
    return {
        'total': base.count(),
        'entradas_pendentes': base.filter(status_entrada_fiscal=StatusEntradaFiscal.PENDENTE).count(),
        'entradas_conciliadas': base.filter(status_entrada_fiscal=StatusEntradaFiscal.CONCILIADA).count(),
        'retiradas_fornecedor': base.filter(
            tipo_atendimento__in=(
                TipoAtendimentoItem.RETIRADA_FORNECEDOR,
                TipoAtendimentoItem.RETIRADA_FORNECEDOR_TRANSPORTADORA,
            ),
        ).count(),
        'entregas_diretas': base.filter(
            tipo_atendimento=TipoAtendimentoItem.ENTREGA_DIRETA_FORNECEDOR_CLIENTE,
        ).count(),
        'sem_compra_vinculada': base.filter(pedido_compra_item_id__isnull=True).count(),
        'com_cte_conferido': base.filter(cte_historico_importado_id__isnull=False).count(),
    }


def parse_filtros_query_params(query_params) -> dict[str, Any]:
    """Converte query string da API em dict de filtros."""
    p = query_params
    out: dict[str, Any] = {}
    str_keys = (
        'search',
        'tipo_atendimento',
        'status_entrada_fiscal',
        'origem_fisica',
        'destino_fisico',
        'data_inicio',
        'data_fim',
    )
    for key in str_keys:
        val = (p.get(key) or '').strip()
        if val:
            out[key] = val

    int_keys = (
        'cliente_id',
        'produto_id',
        'pedido_venda_id',
        'nfe_saida_id',
        'fornecedor_id',
        'pedido_compra_id',
    )
    for key in int_keys:
        val = (p.get(key) or '').strip()
        if not val:
            continue
        try:
            out[key] = int(val)
        except ValueError:
            continue

    bool_keys = (
        'somente_pendentes',
        'somente_sem_compra',
        'tem_compra_vinculada',
        'tem_nfe_entrada_vinculada',
        'tem_cte_vinculado',
        'somente_com_cte',
    )
    for key in bool_keys:
        val = p.get(key)
        if val is not None and str(val).strip() != '':
            out[key] = val

    return out
