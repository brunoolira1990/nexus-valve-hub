from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import (
    CotacaoFornecedor,
    CotacaoFornecedorItem,
    CotacaoFornecedorParticipante,
    CotacaoFornecedorRespostaItem,
    CotacaoFornecedorHistorico,
    ItemProposta,
    PropostaComercialHistorico,
)


TIPOS_FRETE = {'CIF', 'FOB', 'INCLUSO', 'OUTRO'}


def normalizar_tipo_frete(tipo_codigo='', tipo_texto='') -> str:
    valor = (tipo_codigo or tipo_texto or '').strip().upper()
    aliases = {'INCLUSAO': 'INCLUSO', 'INCLUSO_NO_PRECO': 'INCLUSO'}
    return aliases.get(valor, valor if valor in TIPOS_FRETE else '')


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_custo_resposta(resposta, item=None) -> dict:
    completude = classificar_completude_resposta(resposta, item)
    if completude['status'] != 'COMPLETA PARA CALCULO':
        return {
            'status': completude['status'],
            'motivos': completude['motivos'],
            'tipo_frete': completude['tipo_frete'],
            'valor_produtos': None,
            'custo_total_estimado': None,
            'custo_unitario_efetivo': None,
            'quantidade_normalizada': None,
            'frete_efetivo': None,
        }
    unidade_cotada = (resposta.unidade_cotada or '').strip().upper()
    unidade_base = (getattr(item, 'unidade', '') or '').strip().upper() if item else unidade_cotada
    fator = Decimal('1') if unidade_cotada == unidade_base else Decimal(str(resposta.fator_conversao))
    quantidade_normalizada = Decimal(str(resposta.quantidade_atendida)) * fator
    frete_efetivo = Decimal('0') if completude['tipo_frete'] in {'CIF', 'INCLUSO'} else Decimal(str(resposta.frete or 0))
    valor_produtos = quantidade_normalizada * Decimal(str(resposta.preco_unitario))
    custo_total = valor_produtos + sum(
        Decimal(str(getattr(resposta, campo))) for campo in ('ipi_custo', 'icms_st_custo', 'outros_tributos_custo', 'despesas_adicionais')
    ) + frete_efetivo
    custo_total = _money(custo_total)
    return {
        'status': completude['status'],
        'motivos': [],
        'tipo_frete': completude['tipo_frete'],
        'valor_produtos': _money(valor_produtos),
        'custo_total_estimado': custo_total,
        'custo_unitario_efetivo': _money(custo_total / quantidade_normalizada),
        'quantidade_normalizada': quantidade_normalizada,
        'frete_efetivo': _money(frete_efetivo),
    }


def classificar_completude_resposta(resposta, item=None) -> dict:
    motivos = []
    if resposta.status_item == CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO:
        if resposta.preco_unitario is None:
            motivos.append('preço ausente')
        if resposta.quantidade_atendida <= 0:
            motivos.append('quantidade atendida ausente')
        if not (resposta.unidade_cotada or '').strip():
            motivos.append('unidade cotada ausente')
        if any(getattr(resposta, campo) is None for campo in ('ipi_custo', 'icms_st_custo', 'outros_tributos_custo', 'despesas_adicionais')):
            motivos.append('tributos/despesas de entrada incompletos')
    tipo_frete = normalizar_tipo_frete(resposta.frete_tipo_codigo, resposta.frete_tipo)
    if not tipo_frete:
        motivos.append('tipo de frete ausente')
    if tipo_frete in {'FOB', 'OUTRO'} and resposta.frete is None:
        motivos.append(f'frete {tipo_frete} sem valor')
    if resposta.fator_conversao is None:
        unidade_cotada = (resposta.unidade_cotada or '').strip()
        unidade_base = (getattr(item, 'unidade', '') or '').strip() if item else ''
        if unidade_cotada and unidade_base and unidade_cotada.upper() != unidade_base.upper():
            motivos.append('unidade incompatível sem fator')
    return {
        'status': 'COMPLETA PARA CALCULO' if not motivos else 'CUSTO INCOMPLETO',
        'motivos': motivos,
        'tipo_frete': tipo_frete,
    }


def _snapshot_item(item: ItemProposta) -> dict:
    produto = item.produto
    return {
        'produto_id': item.produto_id,
        'codigo_completo': getattr(produto, 'codigo_completo', '') if produto else '',
        'descricao': (getattr(produto, 'descricao', '') if produto else '') or item.descricao_avulsa,
        'unidade': item.unidade_negociada or getattr(produto, 'unidade', '') if produto else item.unidade_negociada,
    }


def _evento(cotacao, tipo: str, descricao: str, usuario=None, dados=None):
    texto = f'Cotação {cotacao.numero}: {descricao}'
    if cotacao.proposta_id:
        return PropostaComercialHistorico.objects.create(
            proposta=cotacao.proposta,
            tipo_evento=tipo,
            descricao=texto,
            usuario=usuario,
            dados_json=dados or {},
        )
    return CotacaoFornecedorHistorico.objects.create(
        cotacao=cotacao,
        evento=tipo,
        descricao=texto,
        usuario=usuario,
        dados_json=dados or {},
    )


def atualizar_status(cotacao: CotacaoFornecedor):
    if cotacao.status == CotacaoFornecedor.Status.CANCELADA:
        return cotacao
    participantes = list(cotacao.participantes.all())
    respostas = list(CotacaoFornecedorRespostaItem.objects.filter(cotacao_item__cotacao=cotacao))
    if not participantes:
        novo = CotacaoFornecedor.Status.RASCUNHO
    elif not respostas:
        novo = CotacaoFornecedor.Status.EM_COTACAO
    elif all(p.status in (CotacaoFornecedorParticipante.Status.RESPONDIDO, CotacaoFornecedorParticipante.Status.RECUSADO, CotacaoFornecedorParticipante.Status.SEM_RETORNO) for p in participantes):
        novo = CotacaoFornecedor.Status.CONCLUIDA
    else:
        novo = CotacaoFornecedor.Status.PARCIAL
    if cotacao.status != novo:
        anterior = cotacao.status
        cotacao.status = novo
        cotacao.save(update_fields=['status', 'atualizado_em'])
        _evento(cotacao, 'COTACAO_STATUS_ALTERADO', f'status alterado de {anterior} para {novo}')
    return cotacao


@transaction.atomic
def adicionar_item(cotacao, item_proposta_id=None, quantidade=None, observacao_tecnica='', usuario=None, *, produto=None, descricao_item='', unidade=''):
    if cotacao.status == CotacaoFornecedor.Status.CANCELADA:
        raise ValueError('Cotação cancelada não aceita novos itens.')
    if cotacao.proposta_id:
        if item_proposta_id is None:
            raise ValueError('Cotação vinculada exige item da Proposta.')
        item = ItemProposta.objects.select_related('produto').get(pk=item_proposta_id, proposta=cotacao.proposta)
        if quantidade is None:
            quantidade = item.quantidade_negociada or item.quantidade
        obj = CotacaoFornecedorItem.objects.create(
            cotacao=cotacao,
            item_proposta=item,
            produto=item.produto,
            produto_snapshot=_snapshot_item(item),
            descricao_item='',
            unidade=item.unidade_negociada or getattr(item.produto, 'unidade', '') if item.produto else item.unidade_negociada,
            quantidade=quantidade,
            observacao_tecnica=observacao_tecnica or '',
        )
        _evento(cotacao, 'ITEM_COTACAO_ADICIONADO', f'item da Proposta #{item.pk} adicionado', usuario, {'item_id': item.pk})
        return obj
    if item_proposta_id is not None:
        raise ValueError('Cotação manual não aceita item da Proposta.')
    if not descricao_item.strip() or not unidade.strip() or quantidade is None or Decimal(str(quantidade)) <= 0:
        raise ValueError('Item manual exige descrição, unidade e quantidade maior que zero.')
    snapshot = {}
    if produto is not None:
        snapshot = {'produto_id': produto.pk, 'codigo_completo': getattr(produto, 'codigo_completo', ''), 'descricao': produto.descricao, 'unidade': getattr(produto, 'unidade', '')}
    obj = CotacaoFornecedorItem.objects.create(
        cotacao=cotacao,
        produto=produto,
        produto_snapshot=snapshot,
        descricao_item=descricao_item.strip(),
        unidade=unidade.strip(),
        quantidade=quantidade,
        observacao_tecnica=observacao_tecnica or '',
    )
    _evento(cotacao, 'ITEM_COTACAO_ADICIONADO', 'item manual adicionado', usuario, {'item_id': obj.pk})
    return obj


@transaction.atomic
def adicionar_participante(cotacao, fornecedor, usuario=None):
    if cotacao.status == CotacaoFornecedor.Status.CANCELADA:
        raise ValueError('Cotação cancelada não aceita fornecedores.')
    obj, created = CotacaoFornecedorParticipante.objects.get_or_create(cotacao=cotacao, fornecedor=fornecedor)
    if not created:
        raise ValueError('O fornecedor já participa desta cotação.')
    _evento(cotacao, 'FORNECEDOR_COTACAO_ADICIONADO', f'fornecedor #{fornecedor.pk} adicionado', usuario, {'fornecedor_id': fornecedor.pk})
    return obj


@transaction.atomic
def registrar_resposta(*, participante, cotacao_item, dados, usuario=None):
    if participante.cotacao_id != cotacao_item.cotacao_id:
        raise ValueError('Participante e item pertencem a cotações diferentes.')
    if participante.cotacao.status == CotacaoFornecedor.Status.CANCELADA:
        raise ValueError('Cotação cancelada não aceita respostas.')
    status_item = dados.get('status_item', CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO)
    if status_item == CotacaoFornecedorRespostaItem.StatusItem.RESPONDIDO and dados.get('preco_unitario') is None:
        raise ValueError('Resposta respondida exige preço unitário.')
    if Decimal(str(dados.get('quantidade_atendida') or 0)) < 0:
        raise ValueError('Quantidade atendida não pode ser negativa.')
    defaults = {
        'preco_unitario': dados.get('preco_unitario'),
        'prazo_entrega': dados.get('prazo_entrega') or '',
        'condicao_pagamento': dados.get('condicao_pagamento') or '',
        'preco_unitario_bruto': dados.get('preco_unitario_bruto'),
        'desconto': dados.get('desconto'),
        'quantidade_atendida': dados.get('quantidade_atendida') or 0,
        'unidade_cotada': dados.get('unidade_cotada') or '',
        'fator_conversao': dados.get('fator_conversao'),
        'frete': dados.get('frete'),
        'frete_tipo': dados.get('frete_tipo') or '',
        'frete_tipo_codigo': normalizar_tipo_frete(dados.get('frete_tipo_codigo'), dados.get('frete_tipo')),
        'ipi_custo': dados.get('ipi_custo'),
        'icms_st_custo': dados.get('icms_st_custo'),
        'outros_tributos_custo': dados.get('outros_tributos_custo'),
        'despesas_adicionais': dados.get('despesas_adicionais'),
        'marca_fabricante': dados.get('marca_fabricante') or '',
        'validade': dados.get('validade'),
        'observacao': dados.get('observacao') or '',
        'status_item': status_item,
    }
    resposta, created = CotacaoFornecedorRespostaItem.objects.update_or_create(
        participante=participante,
        cotacao_item=cotacao_item,
        defaults=defaults,
    )
    agora = timezone.now()
    participante.status = CotacaoFornecedorParticipante.Status.RESPONDIDO
    participante.respondido_em = agora
    participante.save(update_fields=['status', 'respondido_em'])
    atualizar_status(participante.cotacao)
    _evento(participante.cotacao, 'RESPOSTA_COTACAO_REGISTRADA' if created else 'RESPOSTA_COTACAO_ALTERADA', f'resposta do item #{cotacao_item.pk}', usuario, {'resposta_id': resposta.pk, 'item_id': cotacao_item.pk, 'participante_id': participante.pk})
    return resposta


@transaction.atomic
def selecionar_referencia(*, resposta, usuario):
    cotacao = resposta.cotacao_item.cotacao
    if cotacao.status == CotacaoFornecedor.Status.CANCELADA:
        raise ValueError('Cotação cancelada não aceita seleção de referência.')
    anteriores = CotacaoFornecedorRespostaItem.objects.filter(cotacao_item=resposta.cotacao_item, selecionada_como_referencia=True).exclude(pk=resposta.pk)
    if anteriores.exists():
        anteriores.update(selecionada_como_referencia=False)
        _evento(cotacao, 'REFERENCIA_COTACAO_SUBSTITUIDA', f'referência do item #{resposta.cotacao_item_id} substituída', usuario, {'item_id': resposta.cotacao_item_id, 'nova_resposta_id': resposta.pk})
    resposta.selecionada_como_referencia = True
    resposta.selecionada_por = usuario
    resposta.selecionada_em = timezone.now()
    resposta.save(update_fields=['selecionada_como_referencia', 'selecionada_por', 'selecionada_em', 'atualizado_em'])
    if not anteriores.exists():
        _evento(cotacao, 'REFERENCIA_COTACAO_SELECIONADA', f'referência do item #{resposta.cotacao_item_id} selecionada', usuario, {'item_id': resposta.cotacao_item_id, 'resposta_id': resposta.pk})
    return resposta


@transaction.atomic
def cancelar_cotacao(cotacao, usuario=None):
    if cotacao.status == CotacaoFornecedor.Status.CANCELADA:
        return cotacao
    cotacao.status = CotacaoFornecedor.Status.CANCELADA
    cotacao.save(update_fields=['status', 'atualizado_em'])
    _evento(cotacao, 'COTACAO_CANCELADA', 'cotação cancelada', usuario)
    return cotacao
