"""Histórico fiscal completo de NF-e Saída vinculadas ao Pedido de Venda."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.comercial.pedido_venda_apresentacao import label_emissao_sefaz
from apps.comercial.services.alocacao_atendimento_busca import chave_acesso_resumida
from apps.fiscal.models import NFeSaida
from apps.fiscal.nfe_emissao.cancelamento_dados import montar_resumo_cancelamento_nfe_saida
from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida
from apps.fiscal.nfe_saida_bloqueio import nf_cancelada_operacional
from apps.fiscal.nfe_saida_pedido_cancelamento import nf_cancelada_sefaz


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _round_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'))


def _ambiente_label(ambiente: str, sefaz: str) -> str:
    amb = (ambiente or '').strip().upper()
    if amb in ('PRODUCAO', 'PRODUÇÃO', '1'):
        return 'Produção'
    if amb in ('HOMOLOGACAO', 'HOMOLOGAÇÃO', '2'):
        return 'Homologação'
    if sefaz == 'AUTORIZADA_HOMOLOGACAO':
        return 'Homologação'
    if sefaz == 'AUTORIZADA_PRODUCAO':
        return 'Produção'
    return ''


def classificar_papel_fiscal_nfe_pedido(nf: NFeSaida) -> str:
    """
    Papel da NF-e no pedido:
    - ativa: autorizada e não cancelada (faturamento fiscal válido);
    - historico: cancelada (permanece visível, sem validade fiscal);
    - rejeitada: rejeitada/descartada/inutilizada no fluxo atual;
    - pendente: rascunho ou aguardando autorização.
    """
    st = (nf.status or '').strip().upper()
    sefaz = (nf.status_emissao_sefaz or '').strip().upper()

    if nf_cancelada_operacional(nf) or nf_cancelada_sefaz(nf):
        return 'historico'

    if st in ('DESCARTADA_INTERNA',) or 'REJEIT' in st or 'REJEIT' in sefaz:
        return 'rejeitada'

    if sefaz in ('AUTORIZADA_PRODUCAO', 'AUTORIZADA_HOMOLOGACAO'):
        return 'ativa'
    if st in ('AUTORIZADA', 'AUTORIZADA_PRODUCAO', 'AUTORIZADA_HOMOLOGACAO', 'EMITIDA', 'EMITIDO'):
        return 'ativa'

    return 'pendente'


def _mensagem_papel_fiscal(papel: str) -> str:
    return {
        'ativa': 'Documento fiscal ativo — representa faturamento fiscal válido do pedido.',
        'historico': 'Histórico fiscal — NF-e cancelada, sem validade para circulação ou faturamento ativo.',
        'pendente': 'Em elaboração — ainda não representa faturamento fiscal concluído.',
        'rejeitada': 'Não autorizada — não vale como faturamento fiscal ativo.',
    }.get(papel, '')


def _vinculo_faturamento_ativo(nf: NFeSaida) -> bool:
    fat = getattr(nf, 'faturamento_pedido_venda', None)
    if not fat:
        return False
    return (
        fat.nfe_saida_id == nf.pk
        and fat.status == FaturamentoPedidoVenda.Status.GERADO_NFE
    )


def montar_linha_historico_nfe_pedido(nf: NFeSaida) -> dict[str, Any]:
    ap = montar_apresentacao_nfe_saida(nf)
    cancel = montar_resumo_cancelamento_nfe_saida(nf)
    papel = classificar_papel_fiscal_nfe_pedido(nf)
    sefaz = (nf.status_emissao_sefaz or '').strip()
    st = (nf.status or '').strip()

    status_fiscal = label_emissao_sefaz(sefaz or st)
    if papel == 'historico':
        status_fiscal = 'Cancelada SEFAZ'
    elif papel == 'rejeitada':
        status_fiscal = label_emissao_sefaz(sefaz) or 'Rejeitada'
    elif papel == 'pendente' and st.upper() == 'RASCUNHO':
        status_fiscal = 'Rascunho'

    badge = ap.get('badge_principal') or {}
    return {
        'nfe_saida_id': nf.pk,
        'numero': nf.numero,
        'numero_interno': ap['numero_interno'],
        'titulo_exibicao': ap['titulo_exibicao'],
        'numero_faturamento': ap['numero_faturamento'],
        'numero_fiscal': ap['numero_fiscal'],
        'serie_fiscal': ap['serie_fiscal'],
        'status': st,
        'status_emissao_sefaz': sefaz,
        'status_fiscal_label': status_fiscal,
        'badge_status': (badge.get('label') or st or '—').strip(),
        'data': nf.data.isoformat() if nf.data else '',
        'faturamento_id': nf.faturamento_pedido_venda_id,
        'valor_total': str(_round_money(_dec(nf.valor_total))),
        'chave_acesso_resumida': chave_acesso_resumida(nf.chave_acesso),
        'protocolo_autorizacao': (nf.protocolo_autorizacao or '').strip(),
        'protocolo_cancelamento': (cancel.get('protocolo_cancelamento') or '').strip(),
        'cstat_autorizacao': (nf.cstat_autorizacao or '').strip(),
        'ambiente_emissao': (nf.ambiente_emissao or '').strip(),
        'ambiente_label': _ambiente_label(nf.ambiente_emissao or '', sefaz),
        'papel_fiscal': papel,
        'mensagem_papel_fiscal': _mensagem_papel_fiscal(papel),
        'vinculo_faturamento_ativo': _vinculo_faturamento_ativo(nf),
        'cancelada_em': nf.cancelada_em.isoformat() if nf.cancelada_em else cancel.get('cancelada_em'),
        'motivo_cancelamento': (nf.motivo_cancelamento or cancel.get('motivo_cancelamento') or '').strip(),
        'efeitos_autorizacao_aplicados_em': (
            nf.efeitos_autorizacao_aplicados_em.isoformat() if nf.efeitos_autorizacao_aplicados_em else None
        ),
        'efeitos_cancelamento_aplicados_em': (
            nf.efeitos_cancelamento_aplicados_em.isoformat()
            if nf.efeitos_cancelamento_aplicados_em
            else None
        ),
    }


def montar_historico_nfe_pedido_venda(pedido: PedidoVenda) -> list[dict[str, Any]]:
    """Todas as NF-e do pedido, da mais recente para a mais antiga."""
    linhas: list[dict[str, Any]] = []
    for nf in (
        NFeSaida.objects.filter(pedido_venda_id=pedido.pk)
        .select_related('faturamento_pedido_venda', 'pedido_venda')
        .order_by('-id')
    ):
        linhas.append(montar_linha_historico_nfe_pedido(nf))
    return linhas


def resumo_nfe_fiscal_ativa_pedido(historico: list[dict[str, Any]]) -> dict[str, Any]:
    ativas = [h for h in historico if h.get('papel_fiscal') == 'ativa']
    return {
        'tem_nfe_fiscal_ativa': bool(ativas),
        'nfe_fiscal_ativa_ids': [h['nfe_saida_id'] for h in ativas],
    }


def listar_nfs_fiscais_ativas_pedido(pedido: PedidoVenda | int) -> list[NFeSaida]:
    pedido_id = pedido.pk if isinstance(pedido, PedidoVenda) else int(pedido)
    ativas: list[NFeSaida] = []
    for nf in (
        NFeSaida.objects.filter(pedido_venda_id=pedido_id)
        .prefetch_related('itens__item_faturamento_pedido__item_pedido')
        .order_by('-pk')
    ):
        if classificar_papel_fiscal_nfe_pedido(nf) == 'ativa':
            ativas.append(nf)
    return ativas


def quantidades_cobertas_nfe_fiscal_ativa(pedido: PedidoVenda | int) -> dict[int, Decimal]:
    """Soma quantidades por item_pedido_id cobertas por NF-e fiscalmente ativas."""
    cobertura: dict[int, Decimal] = {}
    for nf in listar_nfs_fiscais_ativas_pedido(pedido):
        for linha in nf.itens.all():
            item_fat = linha.item_faturamento_pedido
            if not item_fat or not item_fat.item_pedido_id:
                continue
            pid = item_fat.item_pedido_id
            cobertura[pid] = cobertura.get(pid, Decimal('0')) + _dec(linha.quantidade)
    return cobertura


def derivar_status_comercial_nfe_fiscal_ativa(pedido: PedidoVenda) -> str | None:
    """
    Status comercial derivado de NF-e autorizada não cancelada.
    Retorna FATURADO, PARCIALMENTE_FATURADO ou None se não houver NF ativa.
    """
    from apps.comercial.faturamento_pedido_venda import _round_qty, quantidade_pedida_item

    itens = list(pedido.itens.exclude(status_item=ItemPedidoVenda.StatusItem.CANCELADO))
    if not itens:
        return None

    cobertura = quantidades_cobertas_nfe_fiscal_ativa(pedido)
    if not cobertura:
        return None

    todos = True
    algum = False
    for item in itens:
        pedida = quantidade_pedida_item(item)
        coberta = _round_qty(cobertura.get(item.pk, Decimal('0')))
        if coberta > 0:
            algum = True
        if coberta + Decimal('0.0005') < pedida:
            todos = False

    if todos and algum:
        return 'FATURADO'
    if algum:
        return 'PARCIALMENTE_FATURADO'
    return None
