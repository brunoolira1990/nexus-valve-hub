"""Reabertura operacional segura da conferência de NF-e de entrada de fornecedor."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q

from apps.comercial.models import ItemPedidoCompra
from apps.financeiro.models import TituloFinanceiro

from .models import (
    AlocacaoAtendimento,
    AtendimentoEstoqueLinha,
    EstoqueBarra,
    ItemNFeEntradaConferencia,
    ItemNFeEntradaConferenciaCorridaSplit,
    NFeEntradaConferencia,
    NFeEntradaConferenciaReaberturaEvento,
    NFeEntradaHistoricaImportada,
)

MOTIVO_MINIMO = 10


class ReaberturaEntradaFornecedorErro(ValueError):
    def __init__(self, mensagem: str, *, preview: dict[str, Any] | None = None):
        super().__init__(mensagem)
        self.preview = preview


def _fornecedor_nome(nf: NFeEntradaHistoricaImportada) -> str:
    if nf.fornecedor_emitente_id and nf.fornecedor_emitente:
        return nf.fornecedor_emitente.razao_social or ''
    emit = nf.emit_json if isinstance(nf.emit_json, dict) else {}
    return str(emit.get('xNome') or '').strip()


def _adicionar_impedimento(
    impedimentos: list[dict[str, str]],
    codigo: str,
    mensagem: str,
) -> None:
    if not any(item['codigo'] == codigo for item in impedimentos):
        impedimentos.append({'codigo': codigo, 'mensagem': mensagem})


def _resolver_conferencia(
    nf: NFeEntradaHistoricaImportada,
) -> NFeEntradaConferencia | None:
    try:
        return nf.conferencia
    except NFeEntradaConferencia.DoesNotExist:
        return None


def montar_preview_reabertura_entrada_fornecedor(
    nf: NFeEntradaHistoricaImportada,
    *,
    conferencia: NFeEntradaConferencia | None = None,
) -> dict[str, Any]:
    """Calcula elegibilidade sem alterar a NF-e, a conferência ou seus vínculos."""
    conf = conferencia if conferencia is not None else _resolver_conferencia(nf)
    impedimentos: list[dict[str, str]] = []

    if not nf.empresa_destinataria_id or (nf.papel_empresa_no_documento or '').lower() == 'emitente':
        _adicionar_impedimento(
            impedimentos,
            'DOCUMENTO_NAO_E_ENTRADA_DE_FORNECEDOR',
            'A reabertura é exclusiva para NF-e de terceiros recebida pela Nexus.',
        )

    if conf is None:
        _adicionar_impedimento(
            impedimentos,
            'CONFERENCIA_INEXISTENTE',
            'Esta entrada ainda não possui conferência para reabrir.',
        )
        return {
            'pode_reabrir': False,
            'estado_atual': None,
            'entrada_ja_aberta': False,
            'impedimentos': impedimentos,
            'resumo_vinculos': {},
            'orientacao': 'Inicie a conferência normalmente; não há uma conferência concluída para reabrir.',
            'numero_nfe': nf.numero or '',
            'serie_nfe': nf.serie or '',
            'fornecedor': _fornecedor_nome(nf),
            'nfe_entrada_historica_id': nf.id,
            'conferencia_id': None,
        }

    item_qs = ItemNFeEntradaConferencia.objects.filter(conferencia=conf)
    split_qs = ItemNFeEntradaConferenciaCorridaSplit.objects.filter(
        item_conferencia__conferencia=conf,
    )
    barra_qs = EstoqueBarra.objects.filter(item_conferencia__conferencia=conf)
    titulo_qs = TituloFinanceiro.objects.filter(
        tipo=TituloFinanceiro.Tipo.PAGAR,
        origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
        origem_id=nf.pk,
    )
    alocacao_qs = AlocacaoAtendimento.objects.filter(
        nf_entrada_historica_item__nf=nf,
    )
    atendimento_qs = AtendimentoEstoqueLinha.objects.filter(conferencia=conf)

    estoque_cabecalho = conf.estoque_aplicado_em is not None
    estoque_itens = item_qs.filter(
        Q(estoque_aplicado_em__isnull=False)
        | Q(estoque_corrida_id__isnull=False)
        | Q(corrida_estoque_id__isnull=False)
        | Q(quantidade_estoque_aplicada__gt=0),
    ).exists()
    estoque_splits = split_qs.filter(
        Q(estoque_corrida_id__isnull=False)
        | Q(corrida_estoque_id__isnull=False)
        | Q(quantidade_aplicada__gt=0),
    ).exists()
    barras_nao_canceladas = barra_qs.exclude(status=EstoqueBarra.Status.CANCELADA).count()

    if estoque_cabecalho or estoque_itens or estoque_splits or barras_nao_canceladas:
        _adicionar_impedimento(
            impedimentos,
            'ESTOQUE_APLICADO',
            'Esta entrada de fornecedor já possui estoque aplicado.',
        )

    baixa_pedido = (
        conf.pedido_baixa_aplicado_em is not None
        or item_qs.filter(
            Q(pedido_baixa_aplicada_em__isnull=False)
            | Q(quantidade_pedido_baixada__gt=0),
        ).exists()
    )
    if baixa_pedido:
        _adicionar_impedimento(
            impedimentos,
            'PEDIDO_COMPRA_BAIXADO',
            'Esta entrada alterou a quantidade recebida do Pedido de Compra.',
        )

    titulos_count = titulo_qs.count()
    if titulos_count:
        _adicionar_impedimento(
            impedimentos,
            'CONTA_PAGAR_VINCULADA',
            'Existe Conta a Pagar vinculada a esta entrada.',
        )

    alocacoes_count = alocacao_qs.count()
    if alocacoes_count:
        _adicionar_impedimento(
            impedimentos,
            'ALOCACAO_ENTRADA_VENDA',
            'Existem alocações para Pedidos de Venda.',
        )

    atendimentos_count = atendimento_qs.count()
    if atendimentos_count:
        _adicionar_impedimento(
            impedimentos,
            'ATENDIMENTO_ESTOQUE_VINCULADO',
            'Existe atendimento de estoque vinculado.',
        )

    if conf.status == NFeEntradaConferencia.Status.CANCELADA:
        _adicionar_impedimento(
            impedimentos,
            'CONFERENCIA_CANCELADA',
            'A conferência está cancelada e não pode ser reaberta.',
        )
    elif conf.status not in (
        NFeEntradaConferencia.Status.PENDENTE,
        NFeEntradaConferencia.Status.CONFERIDA,
        NFeEntradaConferencia.Status.PREPARADA,
    ):
        _adicionar_impedimento(
            impedimentos,
            'ESTADO_NAO_REABRIVEL',
            f'A conferência está no estado {conf.status} e não pode ser reaberta.',
        )

    resumo_vinculos = {
        'pedido_compra_id': conf.pedido_compra_id,
        'pedido_compra_selecionado': bool(conf.pedido_compra_id),
        'estoque_aplicado': estoque_cabecalho or estoque_itens or estoque_splits or bool(barras_nao_canceladas),
        'baixa_pedido_compra_aplicada': baixa_pedido,
        'contas_pagar_vinculadas': titulos_count,
        'alocacoes_entrada_venda': alocacoes_count,
        'atendimentos_estoque': atendimentos_count,
        'barras_estoque_nao_canceladas': barras_nao_canceladas,
        'itens_conferencia': item_qs.count(),
        'itens_com_produto': item_qs.filter(produto_id__isnull=False).count(),
        'equivalencias': sum(item.equivalencias.count() for item in item_qs.only('id')),
        'splits_corrida': split_qs.count(),
        'certificados_fornecedor': sum(
            item.itens_certificado_fornecedor.filter(ativo=True).count()
            for item in item_qs.only('id')
        ),
    }
    entrada_ja_aberta = conf.status == NFeEntradaConferencia.Status.PENDENTE
    pode_reabrir = not impedimentos
    if entrada_ja_aberta and pode_reabrir:
        orientacao = 'A entrada já está aberta para correção; nenhuma nova reabertura será registrada.'
    elif pode_reabrir:
        orientacao = 'Informe o motivo para reabrir somente a conferência interna do Nexus.'
    else:
        orientacao = (
            'Trate os impedimentos informados antes de tentar reabrir. '
            'Nenhum efeito será revertido automaticamente.'
        )

    return {
        'pode_reabrir': pode_reabrir,
        'estado_atual': conf.status,
        'entrada_ja_aberta': entrada_ja_aberta,
        'impedimentos': impedimentos,
        'resumo_vinculos': resumo_vinculos,
        'orientacao': orientacao,
        'numero_nfe': nf.numero or '',
        'serie_nfe': nf.serie or '',
        'fornecedor': _fornecedor_nome(nf),
        'nfe_entrada_historica_id': nf.id,
        'conferencia_id': conf.id,
    }


def _bloquear_dependencias(conferencia: NFeEntradaConferencia) -> None:
    """Serializa escritores concorrentes que usam NF/conferência/itens como raiz."""
    itens = list(
        ItemNFeEntradaConferencia.objects.select_for_update()
        .filter(conferencia=conferencia)
        .only('id', 'item_pedido_compra_id'),
    )
    item_ids = [item.id for item in itens]
    pedido_item_ids = [item.item_pedido_compra_id for item in itens if item.item_pedido_compra_id]

    if pedido_item_ids:
        list(ItemPedidoCompra.objects.select_for_update().filter(pk__in=pedido_item_ids).only('id'))
    list(
        ItemNFeEntradaConferenciaCorridaSplit.objects.select_for_update()
        .filter(item_conferencia_id__in=item_ids)
        .only('id'),
    )
    list(
        EstoqueBarra.objects.select_for_update()
        .filter(item_conferencia_id__in=item_ids)
        .only('id'),
    )
    list(
        TituloFinanceiro.objects.select_for_update()
        .filter(
            tipo=TituloFinanceiro.Tipo.PAGAR,
            origem_tipo=TituloFinanceiro.OrigemTipo.NFE_ENTRADA,
            origem_id=conferencia.nf_entrada_historica_id,
        )
        .only('id'),
    )
    list(
        AlocacaoAtendimento.objects.select_for_update()
        .filter(nf_entrada_historica_item__item_conferencia__conferencia=conferencia)
        .only('id'),
    )
    list(
        AtendimentoEstoqueLinha.objects.select_for_update()
        .filter(conferencia=conferencia)
        .only('id'),
    )


@transaction.atomic
def reabrir_entrada_fornecedor(
    nf_id: int,
    *,
    motivo: str,
    usuario=None,
) -> dict[str, Any]:
    """Reabre apenas a conferência, sem desfazer qualquer efeito operacional."""
    nf = (
        NFeEntradaHistoricaImportada.objects.select_for_update()
        .get(pk=nf_id)
    )
    conf = (
        NFeEntradaConferencia.objects.select_for_update()
        .filter(nf_entrada_historica=nf)
        .first()
    )
    if conf is not None:
        _bloquear_dependencias(conf)

    preview = montar_preview_reabertura_entrada_fornecedor(nf, conferencia=conf)
    motivo_limpo = str(motivo or '').strip()
    if len(motivo_limpo) < MOTIVO_MINIMO:
        raise ReaberturaEntradaFornecedorErro(
            f'Informe um motivo com pelo menos {MOTIVO_MINIMO} caracteres.',
            preview=preview,
        )
    if not preview['pode_reabrir']:
        raise ReaberturaEntradaFornecedorErro(
            'Esta entrada de fornecedor não pode ser reaberta.',
            preview=preview,
        )

    estado_anterior = conf.status
    if estado_anterior == NFeEntradaConferencia.Status.PENDENTE:
        return {
            'acao_realizada': False,
            'entrada_ja_aberta': True,
            'estado_anterior': estado_anterior,
            'estado_atual': estado_anterior,
            'evento_id': None,
            'mensagem': 'A entrada de fornecedor já está aberta para correção.',
            'preview': preview,
            'conferencia': conf,
        }

    evento = NFeEntradaConferenciaReaberturaEvento.objects.create(
        conferencia=conf,
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
        motivo=motivo_limpo,
        estado_anterior=estado_anterior,
        estado_posterior=NFeEntradaConferencia.Status.PENDENTE,
        resumo_tecnico=preview['resumo_vinculos'],
    )
    conf.status = NFeEntradaConferencia.Status.PENDENTE
    conf.preparado_em = None
    conf.save(update_fields=['status', 'preparado_em', 'atualizado_em'])

    return {
        'acao_realizada': True,
        'entrada_ja_aberta': False,
        'estado_anterior': estado_anterior,
        'estado_atual': conf.status,
        'evento_id': evento.id,
        'mensagem': (
            'Entrada de fornecedor reaberta para correção. '
            'A NF-e original e seus efeitos fiscais não foram alterados.'
        ),
        'preview': preview,
        'conferencia': conf,
    }
