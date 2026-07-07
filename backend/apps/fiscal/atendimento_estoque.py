"""Compromisso de estoque (faturamento antecipado) — Fase 3.8."""

from __future__ import annotations

from decimal import Decimal

from datetime import date

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.fiscal.conferencia_pedido import (
    STATUS_ELEGIBILIDADE_APTO,
    STATUS_ELEGIBILIDADE_APTO_COM_ALERTA,
    STATUS_ELEGIBILIDADE_BLOQUEADO,
    STATUS_ELEGIBILIDADE_NAO_MOVIMENTA,
    avaliar_elegibilidade_estoque_item_conferencia,
    carregar_certificados_fornecedor_por_item_conferencia,
)
from apps.fiscal.models import (
    AtendimentoEstoque,
    AtendimentoEstoqueLinha,
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    ItemNFeSaida,
    NFeEntradaConferencia,
    NFeSaida,
)
from apps.produtos.models import Produto
from apps.regras_fiscais.entrada_fiscal import (
    avaliar_item_entrada_fiscal,
    carregar_regras_fiscais_entrada_ativas,
    montar_contexto_fiscal_entrada,
)


def _dec(value) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal('0')


def unidade_item_nf_saida(item: ItemNFeSaida) -> str:
    produto = item.produto
    return (produto.get_unidade_estoque_efetiva() or produto.unidade or 'UN').strip().upper() or 'UN'


def atendimento_ativo_por_item(item: ItemNFeSaida) -> AtendimentoEstoque | None:
    return (
        AtendimentoEstoque.objects.filter(item_nf_saida=item)
        .exclude(status=AtendimentoEstoque.Status.CANCELADO)
        .order_by('-id')
        .first()
    )


def _recalcular_status_atendimento(atend: AtendimentoEstoque) -> None:
    if atend.status == AtendimentoEstoque.Status.CANCELADO:
        return
    comprometida = _dec(atend.quantidade_comprometida)
    atendida = _dec(atend.quantidade_atendida)
    if atendida <= 0:
        atend.status = AtendimentoEstoque.Status.PENDENTE
        atend.atendido_em = None
    elif atendida < comprometida:
        atend.status = AtendimentoEstoque.Status.PARCIAL
        atend.atendido_em = None
    else:
        atend.status = AtendimentoEstoque.Status.ATENDIDO
        if not atend.atendido_em:
            atend.atendido_em = timezone.now()


def recalcular_status_atendimento(atend: AtendimentoEstoque) -> AtendimentoEstoque:
    """Recalcula quantidade_atendida a partir das linhas e atualiza status."""
    if atend.status == AtendimentoEstoque.Status.CANCELADO:
        return atend
    total = _dec(
        AtendimentoEstoqueLinha.objects.filter(atendimento=atend).aggregate(total=Sum('quantidade'))['total'],
    )
    atend.quantidade_atendida = total
    _recalcular_status_atendimento(atend)
    atend.save(
        update_fields=['quantidade_atendida', 'status', 'atendido_em', 'atualizado_em'],
    )
    return atend


_STATUS_CONFERENCIA_VINCULO = frozenset(
    {
        NFeEntradaConferencia.Status.PREPARADA,
        NFeEntradaConferencia.Status.CONFERIDA,
    },
)

_ELEGIBILIDADE_PODE_ATENDER = frozenset(
    {
        STATUS_ELEGIBILIDADE_APTO,
        STATUS_ELEGIBILIDADE_APTO_COM_ALERTA,
    },
)


def _avaliar_elegibilidade_item_conferencia(item_conf: ItemNFeEntradaConferencia) -> dict:
    conferencia = item_conf.conferencia
    contexto = montar_contexto_fiscal_entrada(conferencia)
    regras = carregar_regras_fiscais_entrada_ativas()
    resultado_fiscal = avaliar_item_entrada_fiscal(item_conf, contexto, regras)
    cert_map = carregar_certificados_fornecedor_por_item_conferencia([item_conf.id])
    return avaliar_elegibilidade_estoque_item_conferencia(
        item_conf,
        resultado_fiscal=resultado_fiscal,
        divergencias_aceitas=conferencia.divergencias_aceitas,
        certificado_fornecedor_info=cert_map.get(item_conf.id, {}),
    )


def validar_item_conferencia_pode_atender(item_conf: ItemNFeEntradaConferencia) -> dict:
    conferencia = item_conf.conferencia
    if conferencia.status not in _STATUS_CONFERENCIA_VINCULO:
        raise ValueError(
            f'Conferência em status "{conferencia.status}" não permite vincular atendimento. '
            'Prepare a entrada antes de vincular.',
        )
    if item_conf.status == ItemNFeEntradaConferencia.Status.IGNORADO:
        raise ValueError('Linha ignorada na conferência não pode atender compromissos.')
    if not item_conf.produto_id:
        raise ValueError('Vincule o produto na linha da conferência antes de atender.')
    eleg = _avaliar_elegibilidade_item_conferencia(item_conf)
    status_eleg = (eleg.get('status') or '').upper()
    if status_eleg == STATUS_ELEGIBILIDADE_BLOQUEADO:
        raise ValueError('Linha bloqueada para atendimento: ' + '; '.join(eleg.get('mensagens') or ['elegibilidade BLOQUEADO']))
    if status_eleg == STATUS_ELEGIBILIDADE_NAO_MOVIMENTA:
        raise ValueError('Linha não movimenta estoque e não pode atender compromissos.')
    return eleg


def quantidade_alocada_item_conferencia(item_conf: ItemNFeEntradaConferencia) -> Decimal:
    return _dec(
        AtendimentoEstoqueLinha.objects.filter(item_conferencia=item_conf).aggregate(
            total=Sum('quantidade'),
        )['total'],
    )


def quantidade_disponivel_item_conferencia(item_conf: ItemNFeEntradaConferencia) -> Decimal:
    return max(_dec(item_conf.quantidade_nf) - quantidade_alocada_item_conferencia(item_conf), Decimal('0'))


def _resolver_item_certificado_fornecedor(item_conf: ItemNFeEntradaConferencia):
    from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada

    qs = ItemCertificadoFornecedorEntrada.objects.filter(
        item_conferencia=item_conf,
        ativo=True,
    ).select_related('certificado_fornecedor')
    registrado = qs.filter(certificado_fornecedor__status=CertificadoFornecedorEntrada.Status.REGISTRADO).first()
    if registrado:
        return registrado
    return qs.first()


def _serializar_atendimento_resumo(atend: AtendimentoEstoque) -> dict:
    return {
        'id': atend.id,
        'status': atend.status,
        'produto_id': atend.produto_id,
        'nf_saida_id': atend.nf_saida_id,
        'numero_nf_saida': atend.nf_saida.numero if atend.nf_saida_id else '',
        'cliente_nome': atend.nf_saida.cliente.razao_social if atend.nf_saida_id else '',
        'quantidade_comprometida': _fmt_qty(_dec(atend.quantidade_comprometida)),
        'quantidade_atendida': _fmt_qty(_dec(atend.quantidade_atendida)),
        'quantidade_pendente': _fmt_qty(quantidade_pendente_atendimento(atend)),
        'unidade': atend.unidade,
        'estoque_fisico_aplicado': atend.estoque_fisico_aplicado,
    }


def _serializar_linha(linha: AtendimentoEstoqueLinha) -> dict:
    return {
        'id': linha.id,
        'atendimento_id': linha.atendimento_id,
        'item_conferencia_id': linha.item_conferencia_id,
        'conferencia_id': linha.conferencia_id,
        'quantidade': _fmt_qty(_dec(linha.quantidade)),
        'corrida_texto': linha.corrida_texto,
        'lote': linha.lote,
        'item_certificado_fornecedor_id': linha.item_certificado_fornecedor_id,
        'criado_em': linha.criado_em.isoformat() if linha.criado_em else None,
    }


def montar_resposta_vinculo(
    atend: AtendimentoEstoque,
    item_conf: ItemNFeEntradaConferencia,
    *,
    linha: AtendimentoEstoqueLinha | None = None,
) -> dict:
    return {
        'atendimento': _serializar_atendimento_resumo(atend),
        'linha': _serializar_linha(linha) if linha else None,
        'saldo_pendente_linha_conferencia': _fmt_qty(quantidade_disponivel_item_conferencia(item_conf)),
        'saldo_pendente_atendimento': _fmt_qty(quantidade_pendente_atendimento(atend)),
        'quantidade_alocada_linha_conferencia': _fmt_qty(quantidade_alocada_item_conferencia(item_conf)),
    }


def listar_vinculos_item_conferencia(item_conf: ItemNFeEntradaConferencia) -> list[dict]:
    linhas = (
        AtendimentoEstoqueLinha.objects.filter(item_conferencia=item_conf)
        .select_related('atendimento', 'atendimento__nf_saida', 'atendimento__nf_saida__cliente')
        .order_by('criado_em', 'id')
    )
    out = []
    for linha in linhas:
        atend = linha.atendimento
        out.append(
            {
                'linha_id': linha.id,
                'atendimento_id': atend.id,
                'numero_nf_saida': atend.nf_saida.numero if atend.nf_saida_id else '',
                'cliente_nome': atend.nf_saida.cliente.razao_social if atend.nf_saida_id else '',
                'quantidade': _fmt_qty(_dec(linha.quantidade)),
                'status_atendimento': atend.status,
            },
        )
    return out


def sugerir_atendimentos_para_item_conferencia(item_conf: ItemNFeEntradaConferencia) -> dict:
    eleg = validar_item_conferencia_pode_atender(item_conf)
    disponivel = quantidade_disponivel_item_conferencia(item_conf)
    atendimentos = (
        AtendimentoEstoque.objects.filter(
            produto_id=item_conf.produto_id,
            status__in=[AtendimentoEstoque.Status.PENDENTE, AtendimentoEstoque.Status.PARCIAL],
            estoque_fisico_aplicado=False,
        )
        .exclude(status=AtendimentoEstoque.Status.CANCELADO)
        .select_related('nf_saida', 'nf_saida__cliente')
        .order_by('criado_em', 'id')
    )

    sugestoes = []
    restante = disponivel
    for atend in atendimentos:
        pendente = quantidade_pendente_atendimento(atend)
        if pendente <= 0:
            continue
        sugerida = min(pendente, restante) if restante > 0 else Decimal('0')
        sugestoes.append(
            {
                'atendimento_id': atend.id,
                'numero_nf_saida': atend.nf_saida.numero,
                'cliente_id': atend.nf_saida.cliente_id,
                'cliente_nome': atend.nf_saida.cliente.razao_social,
                'status': atend.status,
                'quantidade_pendente': _fmt_qty(pendente),
                'quantidade_sugerida': _fmt_qty(sugerida),
                'dias_em_aberto': dias_em_aberto_atendimento(atend),
                'criado_em': atend.criado_em.isoformat() if atend.criado_em else None,
            },
        )
        if restante > 0 and sugerida > 0:
            restante -= sugerida

    return {
        'item_conferencia_id': item_conf.id,
        'produto_id': item_conf.produto_id,
        'quantidade_nf': _fmt_qty(_dec(item_conf.quantidade_nf)),
        'quantidade_disponivel': _fmt_qty(disponivel),
        'quantidade_alocada': _fmt_qty(quantidade_alocada_item_conferencia(item_conf)),
        'elegibilidade_estoque': eleg,
        'sugestoes': sugestoes,
        'vinculos': listar_vinculos_item_conferencia(item_conf),
    }


def listar_linhas_conferencia_elegiveis(*, produto_id: int) -> list[dict]:
    linhas = (
        ItemNFeEntradaConferencia.objects.filter(
            produto_id=produto_id,
            conferencia__status__in=_STATUS_CONFERENCIA_VINCULO,
        )
        .exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
        .select_related('conferencia', 'conferencia__nf_entrada_historica', 'produto')
        .order_by('-conferencia__atualizado_em', 'id')
    )
    out = []
    for item_conf in linhas:
        try:
            eleg = _avaliar_elegibilidade_item_conferencia(item_conf)
        except Exception:
            continue
        if (eleg.get('status') or '').upper() not in _ELEGIBILIDADE_PODE_ATENDER:
            continue
        disp = quantidade_disponivel_item_conferencia(item_conf)
        if disp <= 0:
            continue
        nf = item_conf.conferencia.nf_entrada_historica
        out.append(
            {
                'item_conferencia_id': item_conf.id,
                'conferencia_id': item_conf.conferencia_id,
                'nf_numero': nf.numero if nf else '',
                'quantidade_nf': _fmt_qty(_dec(item_conf.quantidade_nf)),
                'quantidade_disponivel': _fmt_qty(disp),
                'unidade_nf': item_conf.unidade_nf,
                'corrida': item_conf.corrida,
                'lote': item_conf.lote,
            },
        )
    return out


@transaction.atomic
def vincular_item_conferencia_a_atendimento(
    item_conf: ItemNFeEntradaConferencia,
    atendimento: AtendimentoEstoque,
    quantidade,
) -> tuple[AtendimentoEstoqueLinha, AtendimentoEstoque]:
    validar_item_conferencia_pode_atender(item_conf)
    qtd = _dec(quantidade)
    if qtd <= 0:
        raise ValueError('Quantidade deve ser maior que zero.')

    atend = (
        AtendimentoEstoque.objects.select_for_update()
        .select_related('nf_saida', 'nf_saida__cliente', 'produto')
        .get(pk=atendimento.pk)
    )
    if atend.status == AtendimentoEstoque.Status.CANCELADO:
        raise ValueError('Atendimento cancelado não pode receber vínculo.')
    if atend.status == AtendimentoEstoque.Status.ATENDIDO:
        raise ValueError('Atendimento já atendido não pode receber quantidade adicional.')
    if atend.produto_id != item_conf.produto_id:
        raise ValueError('Produto do atendimento deve ser o mesmo da linha da conferência.')
    if atend.estoque_fisico_aplicado:
        raise ValueError('Atendimento com estoque físico aplicado não pode ser vinculado nesta fase.')

    pendente = quantidade_pendente_atendimento(atend)
    if qtd > pendente:
        raise ValueError(
            f'Quantidade ({qtd}) excede o pendente do atendimento ({pendente}).',
        )
    disponivel = quantidade_disponivel_item_conferencia(item_conf)
    if qtd > disponivel:
        raise ValueError(
            f'Quantidade ({qtd}) excede o disponível na linha da conferência ({disponivel}).',
        )

    item_cf = _resolver_item_certificado_fornecedor(item_conf)
    linha = AtendimentoEstoqueLinha.objects.create(
        atendimento=atend,
        item_conferencia=item_conf,
        conferencia=item_conf.conferencia,
        quantidade=qtd,
        item_certificado_fornecedor=item_cf,
        corrida_texto=(item_conf.corrida or '').strip(),
        lote=(item_conf.lote or '').strip(),
    )
    recalcular_status_atendimento(atend)
    return linha, atend


@transaction.atomic
def desvincular_linha_atendimento(linha_id: int) -> tuple[AtendimentoEstoque, ItemNFeEntradaConferencia]:
    linha = (
        AtendimentoEstoqueLinha.objects.select_related('atendimento', 'item_conferencia', 'item_conferencia__conferencia')
        .get(pk=linha_id)
    )
    atend = AtendimentoEstoque.objects.select_for_update().get(pk=linha.atendimento_id)
    item_conf = linha.item_conferencia
    linha.delete()
    recalcular_status_atendimento(atend)
    return atend, item_conf


def criar_ou_atualizar_atendimento_item_antecipado(item: ItemNFeSaida) -> AtendimentoEstoque:
    """Cria ou atualiza compromisso ativo para item de NF saída antecipada."""
    atend = atendimento_ativo_por_item(item)
    nova_q = _dec(item.quantidade)
    unidade = unidade_item_nf_saida(item)

    if atend:
        atendida_efetiva = _dec(
            AtendimentoEstoqueLinha.objects.filter(atendimento=atend).aggregate(total=Sum('quantidade'))['total'],
        )
        if atendida_efetiva > nova_q:
            raise ValueError(
                f'Item da NF saída #{item.id}: quantidade comprometida ({nova_q}) não pode ser menor '
                f'que a quantidade já atendida ({atendida_efetiva}).',
            )
        if atend.produto_id != item.produto_id and (
            _dec(atend.quantidade_atendida) > 0 or atend.status != AtendimentoEstoque.Status.PENDENTE
        ):
            raise ValueError(
                f'Item da NF saída #{item.id}: não é possível alterar o produto com atendimento parcial ou concluído.',
            )
        atend.produto = item.produto
        atend.quantidade_comprometida = nova_q
        atend.unidade = unidade
        atend.nf_saida = item.nf
        _recalcular_status_atendimento(atend)
        atend.save(
            update_fields=[
                'produto',
                'quantidade_comprometida',
                'unidade',
                'nf_saida',
                'status',
                'atendido_em',
                'atualizado_em',
            ],
        )
        return atend

    return AtendimentoEstoque.objects.create(
        origem_tipo=AtendimentoEstoque.OrigemTipo.NF_SAIDA,
        item_nf_saida=item,
        nf_saida=item.nf,
        produto=item.produto,
        quantidade_comprometida=nova_q,
        quantidade_atendida=Decimal('0'),
        unidade=unidade,
        status=AtendimentoEstoque.Status.PENDENTE,
    )


def cancelar_atendimento_item(
    item: ItemNFeSaida,
    *,
    motivo: str = 'Item removido da NF de saída.',
) -> None:
    atend = atendimento_ativo_por_item(item)
    if not atend:
        return
    atend.status = AtendimentoEstoque.Status.CANCELADO
    atend.motivo_cancelamento = motivo[:255]
    atend.cancelado_em = timezone.now()
    atend.save(update_fields=['status', 'motivo_cancelamento', 'cancelado_em', 'atualizado_em'])


def sincronizar_atendimentos_nf_antecipada(nf: NFeSaida) -> None:
    for item in nf.itens.select_related('produto').all():
        criar_ou_atualizar_atendimento_item_antecipado(item)


def validar_troca_modo_atendimento(instance: NFeSaida, novo_modo: str) -> None:
    from django.db.models import Q

    modo_atual = instance.modo_atendimento_estoque or NFeSaida.ModoAtendimentoEstoque.IMEDIATO
    if modo_atual == novo_modo:
        return

    if modo_atual == NFeSaida.ModoAtendimentoEstoque.IMEDIATO and novo_modo == NFeSaida.ModoAtendimentoEstoque.ANTECIPADO:
        raise ValueError(
            'Não é possível alterar para modo antecipado em NF já registrada com baixa imediata. '
            'Crie uma nova NF em modo antecipado.',
        )

    if modo_atual == NFeSaida.ModoAtendimentoEstoque.ANTECIPADO and novo_modo == NFeSaida.ModoAtendimentoEstoque.IMEDIATO:
        qs = AtendimentoEstoque.objects.filter(nf_saida=instance).exclude(
            status=AtendimentoEstoque.Status.CANCELADO,
        ).filter(Q(quantidade_atendida__gt=0) | ~Q(status=AtendimentoEstoque.Status.PENDENTE))
        if qs.exists():
            raise ValueError(
                'Não é possível alterar para modo imediato: existem atendimentos parciais ou já atendidos.',
            )
        cancelar_atendimentos_pendentes_nf(instance, motivo='Modo alterado para imediato.')


def sync_itens_nf_saida_antecipada(
    nf: NFeSaida,
    itens_data: list[dict],
    *,
    item_ids_payload: list[int | None] | None = None,
) -> None:
    """
    Sincroniza itens da NF antecipada preservando IDs quando informados.
    itens_data: dicts com produto, quantidade, valor, corrida (opcional).
    item_ids_payload: ids na mesma ordem de itens_data (opcional).
    """
    if item_ids_payload is None:
        item_ids_payload = [None] * len(itens_data)

    existing = {it.id: it for it in nf.itens.select_related('produto').all()}
    kept: set[int] = set()

    for row, item_id in zip(itens_data, item_ids_payload, strict=False):
        produto = row['produto']
        quantidade = row['quantidade']
        valor = row['valor']
        corrida = row.get('corrida')

        if item_id and item_id in existing:
            item = existing[item_id]
            kept.add(item_id)
            atend = atendimento_ativo_por_item(item)
            if item.produto_id != produto.id and atend and (
                _dec(atend.quantidade_atendida) > 0 or atend.status != AtendimentoEstoque.Status.PENDENTE
            ):
                raise ValueError(
                    f'Item {item_id}: não é possível alterar o produto com atendimento parcial ou concluído.',
                )
            item.produto = produto
            item.quantidade = quantidade
            item.valor = valor
            item.corrida = corrida
            if 'snapshot_produto' in row:
                item.snapshot_produto = row['snapshot_produto']
            item.save()
            criar_ou_atualizar_atendimento_item_antecipado(item)
        else:
            item = ItemNFeSaida.objects.create(
                nf=nf,
                produto=produto,
                quantidade=quantidade,
                valor=valor,
                corrida=corrida,
                snapshot_produto=row.get('snapshot_produto') or {},
            )
            kept.add(item.id)
            criar_ou_atualizar_atendimento_item_antecipado(item)

    for item_id, item in existing.items():
        if item_id not in kept:
            cancelar_atendimento_item(item)
            item.delete()


def cancelar_atendimentos_pendentes_nf(nf: NFeSaida, *, motivo: str) -> None:
    AtendimentoEstoque.objects.filter(nf_saida=nf).exclude(
        status=AtendimentoEstoque.Status.CANCELADO,
    ).update(
        status=AtendimentoEstoque.Status.CANCELADO,
        motivo_cancelamento=motivo[:255],
        cancelado_em=timezone.now(),
    )


def montar_resumo_atendimento_estoque_nf(nf: NFeSaida) -> dict:
    qs = AtendimentoEstoque.objects.filter(nf_saida=nf).exclude(
        status=AtendimentoEstoque.Status.CANCELADO,
    )
    agg = qs.aggregate(
        comprometida=Sum('quantidade_comprometida'),
        atendida=Sum('quantidade_atendida'),
    )
    comprometida = _dec(agg['comprometida'])
    atendida = _dec(agg['atendida'])
    pendente = max(comprometida - atendida, Decimal('0'))

    statuses = set(qs.values_list('status', flat=True))
    if not statuses:
        status_rollup = 'SEM_COMPROMISSO'
    elif statuses == {AtendimentoEstoque.Status.ATENDIDO}:
        status_rollup = 'ATENDIDO'
    elif AtendimentoEstoque.Status.PENDENTE in statuses and len(statuses) == 1:
        status_rollup = 'PENDENTE'
    elif AtendimentoEstoque.Status.PENDENTE in statuses:
        status_rollup = 'PARCIAL'
    else:
        status_rollup = 'PARCIAL'

    return {
        'quantidade_comprometida_total': str(comprometida),
        'quantidade_atendida_total': str(atendida),
        'quantidade_pendente_total': str(pendente),
        'status_atendimento_estoque': status_rollup,
        'total_atendimentos_ativos': qs.count(),
    }


def quantidade_pendente_atendimento(atend: AtendimentoEstoque) -> Decimal:
    if atend.status == AtendimentoEstoque.Status.CANCELADO:
        return Decimal('0')
    return max(_dec(atend.quantidade_comprometida) - _dec(atend.quantidade_atendida), Decimal('0'))


def dias_em_aberto_atendimento(atend: AtendimentoEstoque, *, hoje: date | None = None) -> int:
    ref = hoje or timezone.localdate()
    criado = timezone.localtime(atend.criado_em).date() if atend.criado_em else ref
    return max((ref - criado).days, 0)


def queryset_atendimentos_estoque():
    return AtendimentoEstoque.objects.select_related(
        'produto',
        'nf_saida',
        'nf_saida__cliente',
    ).order_by('-criado_em', '-id')


def filtrar_atendimentos_estoque(qs, params) -> 'QuerySet':
    status = (params.get('status') or '').strip().upper()
    if status:
        qs = qs.filter(status=status)

    produto = params.get('produto') or params.get('produto_id')
    if produto:
        qs = qs.filter(produto_id=int(produto))

    nf_saida = params.get('nf_saida') or params.get('nf_saida_id')
    if nf_saida:
        qs = qs.filter(nf_saida_id=int(nf_saida))

    cliente = params.get('cliente') or params.get('cliente_id')
    if cliente:
        qs = qs.filter(nf_saida__cliente_id=int(cliente))

    data_inicial = params.get('data_inicial')
    if data_inicial:
        qs = qs.filter(criado_em__date__gte=data_inicial)

    data_final = params.get('data_final')
    if data_final:
        qs = qs.filter(criado_em__date__lte=data_final)

    pendentes = params.get('pendentes')
    if pendentes is not None and str(pendentes).strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}:
        qs = qs.filter(
            status__in=[
                AtendimentoEstoque.Status.PENDENTE,
                AtendimentoEstoque.Status.PARCIAL,
            ],
        ).filter(quantidade_comprometida__gt=F('quantidade_atendida'))

    return qs


def _fmt_qty(value: Decimal) -> str:
    return f'{value:.3f}'


def montar_saldo_consolidado_produto(produto: Produto) -> dict:
    saldo_fisico = _dec(
        EstoqueCorrida.objects.filter(produto_id=produto.id).aggregate(total=Sum('saldo'))['total'],
    )

    saldo_barras_m: Decimal | None = None
    saldo_pecas_kg: Decimal | None = None
    if produto.get_controla_composicao_fisica_efetivo():
        from apps.fiscal.aplicacao_estoque_barra_conferencia import (
            saldo_barras_produto_metros,
            saldo_pecas_produto_kg,
        )

        if produto.get_tipo_composicao_fisica_efetivo() == 'PECA_KG':
            saldo_pecas_kg = saldo_pecas_produto_kg(produto.id)
        else:
            saldo_barras_m = saldo_barras_produto_metros(produto.id)

    ativos = AtendimentoEstoque.objects.filter(produto_id=produto.id).exclude(
        status=AtendimentoEstoque.Status.CANCELADO,
    )
    comprometidos = ativos.filter(
        status__in=[AtendimentoEstoque.Status.PENDENTE, AtendimentoEstoque.Status.PARCIAL],
    )

    quantidade_comprometida = _dec(
        comprometidos.aggregate(total=Sum('quantidade_comprometida'))['total'],
    )
    quantidade_pendente = Decimal('0')
    for row in comprometidos.only('quantidade_comprometida', 'quantidade_atendida', 'status'):
        quantidade_pendente += quantidade_pendente_atendimento(row)

    quantidade_atendida_sem_fisico = _dec(
        ativos.filter(estoque_fisico_aplicado=False).aggregate(total=Sum('quantidade_atendida'))['total'],
    )

    saldo_disponivel = saldo_fisico - quantidade_pendente
    alertas: list[str] = []
    if saldo_disponivel < 0:
        alertas.append('Saldo disponível negativo por compromissos antecipados.')
    if quantidade_atendida_sem_fisico > 0:
        alertas.append(
            'Existe quantidade atendida logisticamente ainda sem aplicação física de estoque.',
        )

    return {
        'produto_id': produto.id,
        'produto_codigo': produto.codigo_completo or '',
        'produto_descricao': produto.descricao,
        'saldo_fisico': _fmt_qty(saldo_fisico),
        'saldo_barras_m': _fmt_qty(saldo_barras_m) if saldo_barras_m is not None else None,
        'saldo_pecas_kg': _fmt_qty(saldo_pecas_kg) if saldo_pecas_kg is not None else None,
        'quantidade_comprometida': _fmt_qty(quantidade_comprometida),
        'quantidade_pendente_atendimento': _fmt_qty(quantidade_pendente),
        'quantidade_atendida_sem_fisico': _fmt_qty(quantidade_atendida_sem_fisico),
        'saldo_disponivel': _fmt_qty(saldo_disponivel),
        'alertas': alertas,
    }


def listar_saldos_consolidados(*, produto_id: int | None = None) -> list[dict]:
    produto_ids: set[int] = set()
    if produto_id:
        produto_ids.add(produto_id)
    else:
        produto_ids.update(
            EstoqueCorrida.objects.values_list('produto_id', flat=True).distinct(),
        )
        produto_ids.update(
            AtendimentoEstoque.objects.exclude(status=AtendimentoEstoque.Status.CANCELADO)
            .values_list('produto_id', flat=True)
            .distinct(),
        )
        from apps.fiscal.models import EstoqueBarra

        produto_ids.update(
            EstoqueBarra.objects.values_list('produto_id', flat=True).distinct(),
        )

    if not produto_ids:
        return []

    produtos = Produto.objects.filter(id__in=produto_ids).order_by('codigo_completo', 'descricao')
    if produto_id:
        produtos = produtos.filter(id=produto_id)

    return [montar_saldo_consolidado_produto(p) for p in produtos]
