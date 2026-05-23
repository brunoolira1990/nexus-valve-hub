"""NF-e Saída 3.5 — payload unificado de conferência pré-emissão."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_bloqueio import (
    dados_complementares_editaveis,
    itens_comerciais_editaveis,
    origem_comercial_travada,
    pode_atualizar_impostos_nfe,
)
from apps.fiscal.snapshot_fiscal_helpers import (
    cfop_from_snapshot_fiscal,
    get_cofins_snapshot,
    get_icms_snapshot,
    get_ipi_snapshot,
    get_ncm_snapshot,
    get_pis_snapshot,
    get_reforma_tributaria_snapshot,
    montar_reforma_item_exibicao,
    reforma_configurada_no_snapshot,
    status_reforma_item,
)
from apps.fiscal.nfe_saida_conferencia_diagnostico import (
    alertas_fiscal_gerais,
    alertas_fiscal_item,
    diagnostico_reforma_item,
)
from apps.fiscal.nfe_saida_prontidao import montar_payload_prontidao, pode_marcar_pronta, pode_validar_conferencia
from apps.fiscal.validacao_nfe_saida import validar_nfe_saida_para_emissao


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0')


def _fmt_dec(v: Decimal, places: int = 2) -> str:
    q = Decimal('0.001') if places == 3 else Decimal('0.01')
    return str(v.quantize(q))


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _origem_label(nf: NFeSaida) -> str:
    if nf.faturamento_pedido_venda_id:
        return 'FATURAMENTO'
    if nf.pedido_venda_id:
        return 'PEDIDO'
    return 'MANUAL'


def _descricao_item(item: ItemNFeSaida) -> str:
    snap = item.snapshot_produto or {}
    if snap.get('descricao'):
        return str(snap['descricao'])
    if item.produto_id:
        return item.produto.descricao
    return ''


def _unidade_item(item: ItemNFeSaida) -> str:
    snap_c = item.snapshot_comercial or {}
    return _text(snap_c.get('unidade_negociada') or (item.snapshot_produto or {}).get('unidade') or 'PC')


def _pedido_cliente_efetivo_item(nf: NFeSaida, item: ItemNFeSaida) -> tuple[str, str]:
    num = _text(item.pedido_cliente_numero) or _text(nf.pedido_cliente_numero)
    linha = _text(item.pedido_cliente_item)
    return num, linha


def _montar_item_conferencia(nf: NFeSaida, item: ItemNFeSaida, idx: int) -> dict[str, Any]:
    snap_f = item.snapshot_fiscal or {}
    snap_c = item.snapshot_comercial or {}
    qtd = _dec(item.quantidade)
    v_unit = _dec(item.valor)
    v_prod = qtd * v_unit
    desconto = _dec(snap_c.get('desconto'))
    v_total = v_prod - desconto
    reforma_raw = get_reforma_tributaria_snapshot(snap_f)
    reforma = montar_reforma_item_exibicao(reforma_raw, valor_produto=v_prod)
    fiscal_icms = get_icms_snapshot(snap_f)
    fiscal_ipi = get_ipi_snapshot(snap_f)
    fiscal_pis = get_pis_snapshot(snap_f)
    fiscal_cofins = get_cofins_snapshot(snap_f)
    fiscal_atual = {
        'ncm': get_ncm_snapshot(snap_f) or _text((item.snapshot_produto or {}).get('ncm')),
        'icms': fiscal_icms,
        'ipi': fiscal_ipi,
        'pis': fiscal_pis,
        'cofins': fiscal_cofins,
        'origem_regra': _text(snap_f.get('origem_regra_fiscal_saida')),
        'snapshot_fiscal': snap_f,
    }
    pc_num, pc_item = _pedido_cliente_efetivo_item(nf, item)
    return {
        'n_item': idx,
        'item_id': item.pk,
        'produto_id': item.produto_id,
        'produto_codigo': _text((item.snapshot_produto or {}).get('codigo_completo') or (item.snapshot_produto or {}).get('codigo')),
        'descricao': _descricao_item(item),
        'ncm': get_ncm_snapshot(snap_f) or _text((item.snapshot_produto or {}).get('ncm')),
        'cfop': cfop_from_snapshot_fiscal(snap_f),
        'unidade': _unidade_item(item),
        'quantidade': _fmt_dec(qtd, 3),
        'valor_unitario': _fmt_dec(v_unit),
        'desconto': _fmt_dec(desconto),
        'valor_total': _fmt_dec(v_total),
        'corrida_numero': item.corrida.numero if item.corrida_id else '',
        'pedido_cliente_numero': pc_num,
        'pedido_cliente_item': pc_item,
        'pedido_cliente_numero_editavel': item.pedido_cliente_numero,
        'pedido_cliente_item_editavel': item.pedido_cliente_item,
        'observacao_item': item.observacao_item,
        'informacao_adicional_item': item.informacao_adicional_item,
        'status_fiscal': 'COM_SNAPSHOT' if snap_f else 'SEM_SNAPSHOT',
        'status_reforma': status_reforma_item(reforma_raw),
        'comercial': {
            'codigo': _text((item.snapshot_produto or {}).get('codigo_completo')),
            'descricao': _descricao_item(item),
            'unidade': _unidade_item(item),
            'quantidade': _fmt_dec(qtd, 3),
            'valor_unitario': _fmt_dec(v_unit),
            'desconto': _fmt_dec(desconto),
            'valor_total': _fmt_dec(v_total),
            'corrida': item.corrida.numero if item.corrida_id else '',
            'item_faturamento_id': item.item_faturamento_pedido_id,
            'snapshot_comercial': snap_c,
        },
        'fiscal_atual': fiscal_atual,
        'fiscal_alertas': alertas_fiscal_item(snap_f, fiscal_atual),
        'reforma_tributaria': reforma,
        'reforma_configurada': reforma_configurada_no_snapshot(snap_f),
        'reforma_diagnostico': diagnostico_reforma_item(nf, item, snap_f, reforma_raw),
    }


def _somar_totais_fiscais(itens: list[dict]) -> dict[str, str]:
    tot_icms = tot_ipi = tot_pis = tot_cofins = tot_cbs = tot_ibs_uf = tot_ibs_mun = Decimal('0')
    for row in itens:
        fa = row.get('fiscal_atual') or {}
        fr = row.get('reforma_tributaria') or {}
        tot_icms += _dec((fa.get('icms') or {}).get('valor'))
        tot_ipi += _dec((fa.get('ipi') or {}).get('valor'))
        tot_pis += _dec((fa.get('pis') or {}).get('valor'))
        tot_cofins += _dec((fa.get('cofins') or {}).get('valor'))
        tot_cbs += _dec(fr.get('valor_cbs'))
        tot_ibs_uf += _dec(fr.get('valor_ibs_estadual'))
        tot_ibs_mun += _dec(fr.get('valor_ibs_municipal'))
    return {
        'valor_icms': _fmt_dec(tot_icms),
        'valor_ipi': _fmt_dec(tot_ipi),
        'valor_pis': _fmt_dec(tot_pis),
        'valor_cofins': _fmt_dec(tot_cofins),
        'valor_cbs': _fmt_dec(tot_cbs),
        'valor_ibs_estadual': _fmt_dec(tot_ibs_uf),
        'valor_ibs_municipal': _fmt_dec(tot_ibs_mun),
        'total_ibs_cbs': _fmt_dec(tot_cbs + tot_ibs_uf + tot_ibs_mun),
        'total_tributos_atuais': _fmt_dec(tot_icms + tot_ipi + tot_pis + tot_cofins),
    }


def _resumo_reforma_geral(itens: list[dict]) -> dict[str, Any]:
    com = sum(1 for i in itens if i.get('reforma_configurada'))
    sem_cst = sum(
        1
        for i in itens
        if i.get('reforma_configurada') and not _text((i.get('reforma_tributaria') or {}).get('cst_ibs_cbs'))
    )
    sem_class = sum(
        1
        for i in itens
        if i.get('reforma_configurada')
        and not _text((i.get('reforma_tributaria') or {}).get('classificacao_tributaria'))
    )
    status = 'NAO_CONFIGURADA'
    if com:
        if sem_cst or sem_class:
            status = 'PENDENTE'
        elif any(i.get('status_reforma') == 'ATENCAO' for i in itens):
            status = 'ATENCAO'
        else:
            status = 'OK'
    return {
        'status': status,
        'itens_com_reforma': com,
        'itens_sem_reforma': len(itens) - com,
        'itens_sem_cst': sem_cst,
        'itens_sem_classificacao': sem_class,
    }


def montar_conferencia_nfe_saida(nf: NFeSaida) -> dict[str, Any]:
    nf = (
        NFeSaida.objects.select_related(
            'cliente',
            'transportadora',
            'pedido_venda',
            'pedido_venda__empresa_emitente',
            'faturamento_pedido_venda',
        )
        .prefetch_related('itens__produto', 'itens__corrida', 'itens__item_faturamento_pedido')
        .get(pk=nf.pk)
    )
    itens_rows = [
        _montar_item_conferencia(nf, item, idx)
        for idx, item in enumerate(nf.itens.all().order_by('pk'), start=1)
    ]
    totais_fiscais = _somar_totais_fiscais(itens_rows)
    soma_produtos = sum((_dec(i['valor_total']) for i in itens_rows), Decimal('0'))
    pedido = nf.pedido_venda
    empresa = pedido.empresa_emitente if pedido and pedido.empresa_emitente_id else None
    checklist = validar_nfe_saida_para_emissao(nf)

    return {
        'nfe': {
            'id': nf.pk,
            'numero': nf.numero,
            'status': nf.status,
            'data': nf.data.isoformat(),
            'valor_total': float(nf.valor_total),
            'cliente_id': nf.cliente_id,
            'cliente_nome': nf.cliente.razao_social,
            'pedido_venda_id': nf.pedido_venda_id,
            'pedido_venda_numero': pedido.numero if pedido else '',
            'faturamento_pedido_venda_id': nf.faturamento_pedido_venda_id,
            'origem': _origem_label(nf),
            'modo_atendimento_estoque': nf.modo_atendimento_estoque,
            'observacao_origem': nf.observacao_origem,
            'pedido_cliente_numero': nf.pedido_cliente_numero,
            'pedido_cliente_observacao': nf.pedido_cliente_observacao,
            'empresa_emitente_nome': empresa.razao_social if empresa else '',
            'empresa_emitente_id': pedido.empresa_emitente_id if pedido else None,
            'natureza_operacao': 'Venda de mercadoria',
            'tipo_operacao': 'SAIDA',
            'finalidade_emissao': 'NORMAL',
        },
        'itens': itens_rows,
        'totais_comerciais': {
            'total_produtos': _fmt_dec(soma_produtos),
            'frete': _fmt_dec(nf.valor_frete),
            'total_nf': _fmt_dec(nf.valor_total),
            'divergencia_itens_nf': abs(soma_produtos - _dec(nf.valor_total)) > Decimal('0.02'),
        },
        'fiscal_atual': {
            'por_item': [
                {
                    'item_id': i['item_id'],
                    'descricao': i['descricao'],
                    'ncm': i['ncm'],
                    'cfop': i['cfop'],
                    'fiscal': i['fiscal_atual'],
                    'alertas': i.get('fiscal_alertas') or [],
                }
                for i in itens_rows
            ],
            'totais': totais_fiscais,
            'alertas_gerais': alertas_fiscal_gerais(totais_fiscais),
        },
        'reforma_tributaria': {
            'resumo': _resumo_reforma_geral(itens_rows),
            'totais': {
                'valor_cbs': totais_fiscais['valor_cbs'],
                'valor_ibs_estadual': totais_fiscais['valor_ibs_estadual'],
                'valor_ibs_municipal': totais_fiscais['valor_ibs_municipal'],
                'total_ibs_cbs': totais_fiscais['total_ibs_cbs'],
            },
            'itens': [
                {
                    'item_id': i['item_id'],
                    'descricao': i['descricao'],
                    'status': i['status_reforma'],
                    'dados': i['reforma_tributaria'],
                    'reforma_configurada': i.get('reforma_configurada'),
                    'diagnostico': i.get('reforma_diagnostico') or '',
                }
                for i in itens_rows
            ],
        },
        'transporte': {
            'transportadora_id': nf.transportadora_id,
            'transportadora_nome': nf.transportadora.razao_social if nf.transportadora_id else '',
            'transportadora_cnpj': nf.transportadora.cnpj if nf.transportadora_id else '',
            'modalidade_frete': nf.modalidade_frete or '9',
            'valor_frete': float(nf.valor_frete),
            'quantidade_volumes': nf.quantidade_volumes,
            'peso_bruto': float(nf.peso_bruto),
            'peso_liquido': float(nf.peso_liquido),
            'especie_volumes': nf.especie_volumes,
            'marca_volumes': nf.marca_volumes,
            'numeracao_volumes': nf.numeracao_volumes,
            'placa_veiculo': nf.placa_veiculo,
            'uf_veiculo': nf.uf_veiculo,
        },
        'observacoes': {
            'observacoes_nfe': nf.observacoes_nfe,
            'informacoes_adicionais': nf.informacoes_adicionais,
            'informacoes_fisco': nf.informacoes_fisco,
            'observacoes_internas': nf.observacoes_internas,
            'observacao_origem': nf.observacao_origem,
        },
        'checklist': checklist,
        'prontidao': montar_payload_prontidao(nf),
        'permissoes': {
            'origem_comercial_travada': origem_comercial_travada(nf),
            'itens_comerciais_editaveis': itens_comerciais_editaveis(nf),
            'dados_complementares_editaveis': dados_complementares_editaveis(nf),
            'fiscal_editavel': itens_comerciais_editaveis(nf) and not origem_comercial_travada(nf),
            'pode_atualizar_impostos': pode_atualizar_impostos_nfe(nf, itens_count=len(itens_rows)),
            'pode_validar_conferencia': pode_validar_conferencia(nf),
            'pode_marcar_pronta': pode_marcar_pronta(nf, checklist),
        },
    }
