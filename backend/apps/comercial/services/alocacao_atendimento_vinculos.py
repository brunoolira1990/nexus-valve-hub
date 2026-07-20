"""ERP 4.0.13 — validação e exibição de vínculos em AlocacaoAtendimento."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist

from apps.fiscal.dfe_classificacao import (
    eh_documento_autorizado,
    eh_documento_homologacao,
    eh_documento_producao,
)
from apps.fiscal.modelo_operacional import StatusEntradaFiscal
from apps.comercial.services.alocacao_atendimento_service import AlocacaoAtendimentoErro
from apps.fiscal.models import AlocacaoAtendimento


def _produto_id_alocacao(dados: dict[str, Any], alocacao: AlocacaoAtendimento | None) -> int | None:
    prod = dados.get('produto')
    if prod is not None:
        return prod.pk if hasattr(prod, 'pk') else int(prod)
    if alocacao:
        return alocacao.produto_id
    return None


def _checar_produto_compativel(
    produto_alocacao: int | None,
    produto_vinculo: int | None,
    *,
    contexto: str,
) -> None:
    if not produto_alocacao or not produto_vinculo:
        return
    if produto_alocacao != produto_vinculo:
        raise AlocacaoAtendimentoErro(
            f'O {contexto} selecionado pertence a outro produto. Ajuste o produto da alocação ou escolha outro vínculo.',
        )


def validar_vinculos_alocacao(
    dados: dict[str, Any],
    *,
    alocacao: AlocacaoAtendimento | None = None,
) -> None:
    """Valida vínculos opcionais — sem efeito financeiro/estoque (apenas regras de elegibilidade)."""
    produto_aloc = _produto_id_alocacao(dados, alocacao)

    pci = dados.get('pedido_compra_item')
    if pci is None and alocacao:
        pci = alocacao.pedido_compra_item
    if pci is not None:
        pci_obj = pci if hasattr(pci, 'pedido_id') else None
        if pci_obj is None:
            from apps.comercial.models import ItemPedidoCompra

            try:
                pci_obj = ItemPedidoCompra.objects.select_related('pedido', 'produto').get(
                    pk=pci.pk if hasattr(pci, 'pk') else pci,
                )
            except ItemPedidoCompra.DoesNotExist as exc:
                raise AlocacaoAtendimentoErro('Item do pedido de compra não encontrado.') from exc
        _checar_produto_compativel(produto_aloc, pci_obj.produto_id, contexto='item do pedido de compra')

    nf_hist_item = dados.get('nf_entrada_historica_item')
    if nf_hist_item is None and alocacao:
        nf_hist_item = alocacao.nf_entrada_historica_item
    if nf_hist_item is not None:
        from apps.fiscal.dfe_classificacao import eh_documento_autorizado, eh_documento_producao
        from apps.fiscal.models import ItemNFeEntradaHistoricaImportada

        try:
            item_nf = ItemNFeEntradaHistoricaImportada.objects.select_related(
                'nf',
                'item_conferencia',
                'item_conferencia__produto',
            ).get(pk=nf_hist_item.pk if hasattr(nf_hist_item, 'pk') else nf_hist_item)
        except ItemNFeEntradaHistoricaImportada.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item da NF-e entrada importada não encontrado.') from exc
        nf = item_nf.nf
        if eh_documento_homologacao(nf):
            raise AlocacaoAtendimentoErro(
                'A NF-e de entrada selecionada é de homologação e não pode ser vinculada ao atendimento.',
            )
        if not eh_documento_producao(nf):
            raise AlocacaoAtendimentoErro(
                'A NF-e de entrada selecionada não é de produção e não pode ser vinculada operacionalmente.',
            )
        if not eh_documento_autorizado(nf):
            raise AlocacaoAtendimentoErro(
                'A NF-e de entrada selecionada não está autorizada (cStat) e não pode ser vinculada.',
            )
        conf_prod = None
        try:
            conf = item_nf.item_conferencia
        except ObjectDoesNotExist:
            conf = None
        if conf is not None:
            conf_prod = conf.produto_id
        _checar_produto_compativel(produto_aloc, conf_prod, contexto='item da NF-e entrada')

    nf_entrada_item = dados.get('nf_entrada_item')
    if nf_entrada_item is None and alocacao:
        nf_entrada_item = alocacao.nf_entrada_item
    if nf_entrada_item is not None:
        from apps.fiscal.models import ItemNFeEntrada

        try:
            item_op = ItemNFeEntrada.objects.select_related('nf', 'produto').get(
                pk=nf_entrada_item.pk if hasattr(nf_entrada_item, 'pk') else nf_entrada_item,
            )
        except ItemNFeEntrada.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('Item da NF-e entrada operacional não encontrado.') from exc
        _checar_produto_compativel(produto_aloc, item_op.produto_id, contexto='item da NF-e entrada')

    cte = dados.get('cte_historico_importado')
    if cte is None and alocacao:
        cte = alocacao.cte_historico_importado
    if cte is not None:
        from apps.fiscal.models import CTeHistoricoImportado

        try:
            cte_obj = CTeHistoricoImportado.objects.select_related('transportadora').get(
                pk=cte.pk if hasattr(cte, 'pk') else cte,
            )
        except CTeHistoricoImportado.DoesNotExist as exc:
            raise AlocacaoAtendimentoErro('CT-e histórico não encontrado.') from exc
        if eh_documento_homologacao(cte_obj):
            raise AlocacaoAtendimentoErro(
                'O CT-e selecionado é de homologação e não pode ser vinculado ao atendimento.',
            )
        if not eh_documento_producao(cte_obj) or not eh_documento_autorizado(cte_obj):
            raise AlocacaoAtendimentoErro(
                'O CT-e selecionado deve ser de produção e autorizado para vínculo operacional.',
            )
        if cte_obj.cancelado or cte_obj.ignorado_operacionalmente:
            raise AlocacaoAtendimentoErro('O CT-e selecionado está cancelado ou ignorado operacionalmente.')
        if cte_obj.status_conferencia in (
            CTeHistoricoImportado.StatusConferencia.DIVERGENTE,
            CTeHistoricoImportado.StatusConferencia.IGNORADO,
            CTeHistoricoImportado.StatusConferencia.CANCELADO,
        ):
            raise AlocacaoAtendimentoErro('O CT-e selecionado não está apto (divergente, ignorado ou cancelado).')
        if cte_obj.status_conferencia not in (
            CTeHistoricoImportado.StatusConferencia.CONFERIDO,
            CTeHistoricoImportado.StatusConferencia.PREPARADO,
        ):
            raise AlocacaoAtendimentoErro('O CT-e selecionado ainda não foi conferido.')


def montar_vinculos_exibicao(alocacao: AlocacaoAtendimento) -> dict[str, Any]:
    """Labels legíveis dos vínculos (sem dados sensíveis extras)."""
    fornecedor_label = ''
    if alocacao.fornecedor_id and alocacao.fornecedor:
        f = alocacao.fornecedor
        fornecedor_label = (f.nome_fantasia or f.razao_social or '').strip()

    pedido_compra_label = ''
    pedido_compra_id = None
    if alocacao.pedido_compra_item_id and alocacao.pedido_compra_item:
        pci = alocacao.pedido_compra_item
        pedido_compra_id = pci.pedido_id
        if pci.pedido_id and pci.pedido:
            pedido_compra_label = pci.pedido.numero

    nfe_entrada_label = ''
    nfe_entrada_status = ''
    nfe_entrada_historica_id = None
    if alocacao.nf_entrada_historica_item_id and alocacao.nf_entrada_historica_item:
        item = alocacao.nf_entrada_historica_item
        if item.nf_id and item.nf:
            nf = item.nf
            nfe_entrada_historica_id = nf.pk
            nfe_entrada_label = f'NF-e {nf.numero}/{nf.serie or "—"}'
            try:
                nfe_entrada_status = item.nf.conferencia.status
            except Exception:
                nfe_entrada_status = ''
    elif alocacao.nf_entrada_item_id and alocacao.nf_entrada_item:
        item = alocacao.nf_entrada_item
        if item.nf_id and item.nf:
            nfe_entrada_label = getattr(item.nf, 'numero', '') or f'NF-e #{item.nf_id}'

    cte_label = ''
    cte_status = ''
    if alocacao.cte_historico_importado_id and alocacao.cte_historico_importado:
        cte = alocacao.cte_historico_importado
        transp = ''
        if cte.transportadora_id and cte.transportadora:
            t = cte.transportadora
            transp = (t.nome_fantasia or t.razao_social or '').strip()
        cte_label = f'CT-e {cte.numero}/{cte.serie or "—"}'
        if transp:
            cte_label += f' — {transp}'
        cte_status = cte.status_conferencia or ''

    alertas: list[str] = []
    if alocacao.status_entrada_fiscal == StatusEntradaFiscal.PENDENTE:
        alertas.append(
            'Entrada fiscal pendente — não bloqueia emissão da NF-e conforme operação Nexus.',
        )
    if any(
        [
            alocacao.pedido_compra_item_id,
            alocacao.nf_entrada_historica_item_id,
            alocacao.cte_historico_importado_id,
            alocacao.nf_entrada_item_id,
        ],
    ):
        alertas.append(
            'Vínculos operacionais — não geram financeiro, estoque, expedição ou rateio automático.',
        )

    return {
        'fornecedor_label': fornecedor_label or None,
        'pedido_compra_label': pedido_compra_label or None,
        'pedido_compra_id': pedido_compra_id,
        'nfe_entrada_label': nfe_entrada_label or None,
        'nfe_entrada_historica_id': nfe_entrada_historica_id,
        'nfe_entrada_status_conferencia': nfe_entrada_status or None,
        'cte_label': cte_label or None,
        'cte_status_conferencia': cte_status or None,
        'tem_compra_vinculada': bool(alocacao.pedido_compra_item_id),
        'tem_nfe_entrada_vinculada': bool(
            alocacao.nf_entrada_historica_item_id or alocacao.nf_entrada_item_id,
        ),
        'tem_cte_vinculado': bool(alocacao.cte_historico_importado_id),
        'alertas_vinculo': alertas,
    }
