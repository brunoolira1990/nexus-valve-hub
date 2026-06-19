"""Reparo controlado de itens de proposta presos após exclusão de pedido (pré-hotfix)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.comercial.commercial_defaults import (
    STATUS_ITEM_CANCELADO,
    STATUS_ITEM_CONVERTIDO,
    STATUS_ITEM_PENDENTE,
    STATUS_ITEM_PERDIDO,
    STATUS_PROPOSTA_CONVERTIDA,
    STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA,
    STATUS_PROPOSTA_REABERTA,
)
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, ItemProposta, Proposta, PropostaComercialHistorico
from apps.comercial.pedido_venda_exclusao import validar_exclusao_pedido_venda
from apps.comercial.proposta_comercial_historico import registrar_evento_comercial
from apps.comercial.proposta_comercial_status import (
    _comercial_snapshot,
    _norm_status,
    calcular_status_proposta_apos_exclusao_pedido,
    pedido_vinculado_item,
    reverter_item_proposta_apos_exclusao_pedido,
    status_item_proposta,
)

CONFIRMACAO_TOKEN = 'REPARAR_STATUS_COMERCIAL'

MSG_ITEM_STATUS_INVALIDO = 'Status comercial não é CONVERTIDO_EM_PEDIDO.'
MSG_PEDIDO_AINDA_EXISTE = 'Pedido de venda vinculado ainda existe — item não é órfão.'
MSG_ITEM_PEDIDO_VIVO = 'Item ainda possui linha de pedido de venda vinculada.'
MSG_PEDIDO_COM_EFEITOS = 'Pedido vinculado possui efeitos posteriores — reparo bloqueado.'
MSG_RESIDUO_FATURAMENTO = 'Faturamento ativo encontrado para pedido referenciado — reparo bloqueado.'
MSG_RESIDUO_NFE = 'NF-e vinculada ao pedido referenciado — reparo bloqueado.'
MSG_RESIDUO_ALOCACAO = 'Alocação de atendimento vinculada — reparo bloqueado.'
MSG_STATUS_PROPOSTA_INCONSISTENTE = (
    'Status da proposta indica conversão, mas não há itens convertidos nem pedidos ativos.'
)

STATUS_PROPOSTA_REPARO_CANDIDATO = frozenset(
    {
        STATUS_PROPOSTA_CONVERTIDA,
        STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA,
    },
)


@dataclass
class ItemReparoLinha:
    item_id: int
    acao: str
    motivo: str
    pedido_id_ref: int | None = None
    pedido_numero_ref: str = ''


@dataclass
class RelatorioReparoProposta:
    proposta_id: int
    proposta_numero: str
    status_atual: str
    status_novo_previsto: str | None = None
    reparar_status_proposta: bool = False
    motivo_reparo_status: str = ''
    linhas: list[ItemReparoLinha] = field(default_factory=list)

    @property
    def itens_reparaveis(self) -> list[int]:
        return [lin.item_id for lin in self.linhas if lin.acao == 'reparar']

    @property
    def itens_bloqueados(self) -> list[int]:
        return [lin.item_id for lin in self.linhas if lin.acao == 'bloquear']

    @property
    def itens_ignorados(self) -> list[int]:
        return [lin.item_id for lin in self.linhas if lin.acao == 'ignorar']

    @property
    def tem_reparo(self) -> bool:
        return bool(self.itens_reparaveis) or self.reparar_status_proposta


def _pedido_vivo_vinculado_item(item: ItemProposta) -> PedidoVenda | None:
    from apps.comercial.models import PedidoVenda

    if item.pedido_venda_gerado_id:
        pedido = PedidoVenda.objects.filter(pk=item.pedido_venda_gerado_id).first()
        if pedido:
            return pedido

    if item.item_pedido_venda_gerado_id:
        ipv = (
            ItemPedidoVenda.objects.filter(pk=item.item_pedido_venda_gerado_id)
            .select_related('pedido')
            .first()
        )
        if ipv and ipv.pedido_id and ipv.pedido:
            return ipv.pedido

    ipv = (
        ItemPedidoVenda.objects.filter(item_proposta_id=item.pk)
        .select_related('pedido')
        .order_by('id')
        .first()
    )
    if ipv and ipv.pedido_id and ipv.pedido:
        return ipv.pedido

    pedido_id, _ = pedido_vinculado_item(item)
    if pedido_id:
        return PedidoVenda.objects.filter(pk=pedido_id).first()
    return None


def _referencia_pedido_item(item: ItemProposta) -> tuple[int | None, str]:
    pedido_id, pedido_numero = pedido_vinculado_item(item)
    if pedido_id:
        return pedido_id, pedido_numero
    com = _comercial_snapshot(item)
    pid = com.get('pedido_venda_id')
    pnum = com.get('pedido_venda_numero') or ''
    try:
        return (int(pid) if pid else None), str(pnum)
    except (TypeError, ValueError):
        return None, str(pnum)


def _tem_efeitos_residuais_pedido_referenciado(pedido_id: int) -> tuple[bool, str]:
    from apps.fiscal.models import AlocacaoAtendimento, NFeSaida

    if NFeSaida.objects.filter(pedido_venda_id=pedido_id).exists():
        return True, MSG_RESIDUO_NFE

    if (
        FaturamentoPedidoVenda.objects.filter(pedido_id=pedido_id)
        .exclude(status=FaturamentoPedidoVenda.Status.CANCELADO)
        .exists()
    ):
        return True, MSG_RESIDUO_FATURAMENTO

    item_ids = list(ItemPedidoVenda.objects.filter(pedido_id=pedido_id).values_list('pk', flat=True))
    if item_ids and AlocacaoAtendimento.objects.filter(pedido_venda_item_id__in=item_ids).exists():
        return True, MSG_RESIDUO_ALOCACAO

    return False, ''


def avaliar_item_para_reparo(item: ItemProposta) -> ItemReparoLinha:
    pedido_id_ref, pedido_numero_ref = _referencia_pedido_item(item)
    base = {
        'item_id': item.pk,
        'pedido_id_ref': pedido_id_ref,
        'pedido_numero_ref': pedido_numero_ref,
    }

    if (item.status_comercial or '').strip() != STATUS_ITEM_CONVERTIDO:
        return ItemReparoLinha(
            acao='ignorar',
            motivo=MSG_ITEM_STATUS_INVALIDO,
            **base,
        )

    pedido_vivo = _pedido_vivo_vinculado_item(item)
    if pedido_vivo is not None:
        try:
            validar_exclusao_pedido_venda(pedido_vivo)
        except ValidationError as exc:
            detail = exc.detail
            msg = detail.get('detail') if isinstance(detail, dict) else str(detail)
            return ItemReparoLinha(
                acao='bloquear',
                motivo=f'{MSG_PEDIDO_COM_EFEITOS} ({msg})',
                pedido_id_ref=pedido_vivo.pk,
                pedido_numero_ref=pedido_vivo.numero,
                item_id=item.pk,
            )
        return ItemReparoLinha(
            acao='ignorar',
            motivo=f'{MSG_PEDIDO_AINDA_EXISTE} ({pedido_vivo.numero}, id={pedido_vivo.pk}).',
            pedido_id_ref=pedido_vivo.pk,
            pedido_numero_ref=pedido_vivo.numero,
            item_id=item.pk,
        )

    if ItemPedidoVenda.objects.filter(item_proposta_id=item.pk).exists():
        return ItemReparoLinha(
            acao='bloquear',
            motivo=MSG_ITEM_PEDIDO_VIVO,
            **base,
        )

    if pedido_id_ref:
        bloqueado, motivo = _tem_efeitos_residuais_pedido_referenciado(pedido_id_ref)
        if bloqueado:
            return ItemReparoLinha(acao='bloquear', motivo=motivo, **base)

    return ItemReparoLinha(
        acao='reparar',
        motivo='Vínculo órfão — pedido de venda não encontrado.',
        **base,
    )


def _prever_status_proposta_apos_reparo(proposta: Proposta, itens_reparaveis: set[int]) -> str:
    def status_efetivo(item: ItemProposta) -> str:
        if item.pk in itens_reparaveis:
            return STATUS_ITEM_PENDENTE
        return status_item_proposta(item)

    itens = list(proposta.itens.all())
    ativos = [
        it for it in itens
        if status_efetivo(it) not in (STATUS_ITEM_CANCELADO, STATUS_ITEM_PERDIDO)
    ]
    if ativos and all(status_efetivo(it) == STATUS_ITEM_CONVERTIDO for it in ativos):
        return STATUS_PROPOSTA_CONVERTIDA
    if proposta.pedidos_gerados.exists() or any(
        status_efetivo(it) == STATUS_ITEM_CONVERTIDO for it in itens
    ):
        return STATUS_PROPOSTA_PARCIALMENTE_CONVERTIDA
    st = _norm_status(proposta.status)
    if st == STATUS_PROPOSTA_REABERTA:
        return STATUS_PROPOSTA_REABERTA
    return 'Aprovada'


def _tem_item_convertido_no_banco(proposta: Proposta) -> bool:
    return any(
        (item.status_comercial or '').strip() == STATUS_ITEM_CONVERTIDO
        for item in proposta.itens.all()
    )


def _tem_pedido_vivo_na_proposta(proposta: Proposta) -> bool:
    if proposta.pedidos_gerados.exists():
        return True
    return any(_pedido_vivo_vinculado_item(item) is not None for item in proposta.itens.all())


def _proposta_precisa_reparo_status(proposta: Proposta) -> bool:
    if _norm_status(proposta.status) not in STATUS_PROPOSTA_REPARO_CANDIDATO:
        return False
    if _tem_item_convertido_no_banco(proposta):
        return False
    if _tem_pedido_vivo_na_proposta(proposta):
        return False
    status_correto = calcular_status_proposta_apos_exclusao_pedido(proposta)
    return _norm_status(proposta.status) != _norm_status(status_correto)


def analisar_reparo_status_comercial_proposta(proposta: Proposta) -> RelatorioReparoProposta:
    proposta = Proposta.objects.prefetch_related('itens').get(pk=proposta.pk)
    linhas = [avaliar_item_para_reparo(item) for item in proposta.itens.all()]
    relatorio = RelatorioReparoProposta(
        proposta_id=proposta.pk,
        proposta_numero=proposta.numero,
        status_atual=proposta.status or '',
        linhas=linhas,
    )
    itens_reparaveis = set(relatorio.itens_reparaveis)
    if itens_reparaveis:
        relatorio.status_novo_previsto = _prever_status_proposta_apos_reparo(proposta, itens_reparaveis)
    elif _proposta_precisa_reparo_status(proposta):
        relatorio.reparar_status_proposta = True
        relatorio.motivo_reparo_status = MSG_STATUS_PROPOSTA_INCONSISTENTE
        relatorio.status_novo_previsto = calcular_status_proposta_apos_exclusao_pedido(proposta)
    return relatorio


@transaction.atomic
def executar_reparo_status_comercial_proposta(
    proposta: Proposta,
    *,
    usuario=None,
) -> dict[str, Any]:
    proposta = Proposta.objects.select_for_update().prefetch_related('itens').get(pk=proposta.pk)
    relatorio = analisar_reparo_status_comercial_proposta(proposta)

    if relatorio.itens_bloqueados:
        bloqueados = ', '.join(str(i) for i in relatorio.itens_bloqueados)
        raise ValueError(
            f'Reparo bloqueado para itens com efeitos posteriores ou vínculos ativos: {bloqueados}.',
        )

    itens_reparados: list[dict[str, Any]] = []
    status_anterior = proposta.status or ''
    for linha in relatorio.linhas:
        if linha.acao != 'reparar':
            continue
        item = ItemProposta.objects.select_for_update().get(pk=linha.item_id, proposta_id=proposta.pk)
        reverter_item_proposta_apos_exclusao_pedido(item, usuario=usuario)
        itens_reparados.append(
            {
                'item_proposta_id': item.pk,
                'pedido_id_ref': linha.pedido_id_ref,
                'pedido_numero_ref': linha.pedido_numero_ref,
            },
        )

    status_proposta_reparado = relatorio.reparar_status_proposta
    if itens_reparados or status_proposta_reparado:
        proposta = Proposta.objects.select_for_update().prefetch_related('itens').get(pk=proposta.pk)
        proposta.status = calcular_status_proposta_apos_exclusao_pedido(proposta)
        proposta.save(update_fields=['status'])

        if itens_reparados and status_proposta_reparado:
            descricao = (
                f'Reparo de status comercial: {len(itens_reparados)} item(ns) órfão(s) '
                'retornaram para pendente e o status da proposta foi recalculado.'
            )
        elif itens_reparados:
            descricao = (
                f'Reparo de status comercial: {len(itens_reparados)} item(ns) órfão(s) '
                'retornaram para pendente após exclusão prévia de pedido de venda.'
            )
        else:
            descricao = (
                'Reparo de status comercial: status da proposta recalculado '
                'após exclusão prévia de pedido de venda sem itens convertidos.'
            )

        registrar_evento_comercial(
            proposta,
            PropostaComercialHistorico.TipoEvento.REPARO_STATUS_COMERCIAL_PEDIDO,
            descricao=descricao,
            usuario=usuario,
            dados_json={
                'itens_reparados': itens_reparados,
                'status_proposta_reparado': status_proposta_reparado,
                'status_anterior': status_anterior,
                'status_novo': proposta.status,
            },
        )

    return {
        'proposta_id': proposta.pk,
        'proposta_numero': proposta.numero,
        'status_anterior': status_anterior,
        'status_novo': proposta.status,
        'itens_reparados': itens_reparados,
        'status_proposta_reparado': status_proposta_reparado,
        'itens_ignorados': relatorio.itens_ignorados,
        'relatorio': relatorio,
    }


def formatar_relatorio_reparo(relatorio: RelatorioReparoProposta) -> str:
    linhas = [
        f'Proposta {relatorio.proposta_numero} (id={relatorio.proposta_id})',
        f'Status atual: {relatorio.status_atual or "—"}',
    ]
    if relatorio.status_novo_previsto is not None:
        linhas.append(f'Status previsto após reparo: {relatorio.status_novo_previsto}')
    if relatorio.reparar_status_proposta:
        linhas.append('Status da proposta: será recalculado.')
        linhas.append(f'  Motivo: {relatorio.motivo_reparo_status}')

    if not relatorio.linhas:
        linhas.append('Nenhum item encontrado na proposta.')
        return '\n'.join(linhas)

    linhas.append('')
    for item in relatorio.linhas:
        ref = ''
        if item.pedido_id_ref or item.pedido_numero_ref:
            ref = f' | pedido ref: {item.pedido_numero_ref or "—"} (id={item.pedido_id_ref or "—"})'
        linhas.append(f'  Item #{item.item_id} [{item.acao.upper()}]: {item.motivo}{ref}')

    linhas.append('')
    linhas.append(f'Reparáveis: {len(relatorio.itens_reparaveis)}')
    linhas.append(f'Bloqueados: {len(relatorio.itens_bloqueados)}')
    linhas.append(f'Ignorados: {len(relatorio.itens_ignorados)}')
    if relatorio.reparar_status_proposta:
        linhas.append('Status proposta: reparo necessário')
    return '\n'.join(linhas)
