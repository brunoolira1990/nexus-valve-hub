"""Efeitos ERP de uma NF-e de devolução (finNFe=4) autorizada na SEFAZ.

Incidente de produção: a entrada de devolução foi autorizada e o ERP não reagiu —
o pedido ficou travado como faturado, o título continuou em aberto e o estoque não
recebeu as mercadorias de volta. Este módulo fecha o ciclo reusando as rotinas que o
cancelamento de NF-e saída já exercita, em vez de reimplementar estorno, baixa ou
movimentação de estoque.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.fiscal.models import ItemNFeEntrada, NFeEntrada, NFeSaida
from apps.fiscal.nfe_saida_efeitos import _dec

logger = logging.getLogger(__name__)

CENTAVO = Decimal('0.01')
MOTIVO_ABATIMENTO = 'Devolução de venda autorizada (NF-e entrada finNFe=4)'
PREFIXO_CORRIDA_DEVOLUCAO = 'DEV'
STATUS_AUTORIZADOS = (
    NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
    NFeEntrada.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
)


def _numero_documento(nf: NFeEntrada | NFeSaida) -> str:
    return str(getattr(nf, 'numero_nfe', '') or getattr(nf, 'numero', '') or nf.pk).strip()


def _numero_corrida_devolucao(nf_entrada: NFeEntrada, item: ItemNFeEntrada) -> str:
    return f'{PREFIXO_CORRIDA_DEVOLUCAO}-{_numero_documento(nf_entrada)}-{item.produto_id}'


def resolver_fornecedor_para_corrida_devolucao(
    nf_entrada: NFeEntrada,
    item: ItemNFeEntrada,
) -> tuple[int | None, str]:
    """`Corrida.fornecedor` é obrigatório; devolve (id, origem) ou (None, '') quando não há como saber.

    Ordem: o fornecedor informado na própria entrada, o do lote mais recente do mesmo
    produto (o material devolvido saiu daqui) e, por último, o destinatário quando ele
    também é cadastrado como fornecedor. Criar um Fornecedor genérico está fora de
    cogitação: poluiria o cadastro para tapar um buraco de rastreabilidade.
    """
    from apps.corridas.models import Corrida

    if nf_entrada.fornecedor_id:
        return nf_entrada.fornecedor_id, 'nf_entrada'

    corrida = (
        Corrida.objects.filter(produto_id=item.produto_id)
        .exclude(fornecedor_id__isnull=True)
        .order_by('-data_recebimento', '-id')
        .first()
    )
    if corrida:
        return corrida.fornecedor_id, 'corrida_do_produto'

    cliente = nf_entrada.cliente_destinatario
    if cliente:
        from apps.fiscal.fornecedor_entrada import buscar_fornecedores_por_cnpj

        correspondentes = buscar_fornecedores_por_cnpj(getattr(cliente, 'cnpj', '') or '', apenas_ativos=True)
        if correspondentes:
            return correspondentes[0].pk, 'destinatario_fornecedor'

    return None, ''


def _aplicar_estoque_devolucao(nf_entrada: NFeEntrada) -> dict[str, Any]:
    """Credita o saldo na corrida original do item; sem corrida, abre uma de devolução.

    A entrada de devolução é `ENTRADA_PROPRIA_EMITIDA`, tipo que o serializer da tela
    de Entrada Própria ignora de propósito (`_aplicar_estoque_se_manual`), então este é
    o único ponto onde o saldo volta — sem risco de dobrar o crédito.
    """
    from apps.fiscal.aplicacao_estoque_conferencia import resolver_ou_criar_corrida
    from apps.fiscal.estoque_services import aplicar_entrada_item

    creditados: list[dict[str, Any]] = []
    pendentes: list[dict[str, Any]] = []

    for item in nf_entrada.itens.select_related('corrida', 'produto').order_by('id'):
        if _dec(item.quantidade) <= 0:
            continue

        creditado_sem_corrida_original = False
        origem_fornecedor = ''
        if not item.corrida_id:
            fornecedor_id, origem_fornecedor = resolver_fornecedor_para_corrida_devolucao(nf_entrada, item)
            if not fornecedor_id:
                pendentes.append(
                    {
                        'item_id': item.pk,
                        'produto_id': item.produto_id,
                        'quantidade': str(_dec(item.quantidade)),
                        'motivo': 'Sem fornecedor resolvível para abrir corrida de devolução.',
                    },
                )
                continue
            try:
                corrida = resolver_ou_criar_corrida(
                    produto_id=item.produto_id,
                    fornecedor_id=fornecedor_id,
                    numero_texto=_numero_corrida_devolucao(nf_entrada, item),
                    data_recebimento=timezone.localdate(),
                    nf_entrada_ref=_numero_documento(nf_entrada),
                )
            except ValueError as exc:
                pendentes.append(
                    {
                        'item_id': item.pk,
                        'produto_id': item.produto_id,
                        'quantidade': str(_dec(item.quantidade)),
                        'motivo': str(exc),
                    },
                )
                continue
            creditado_sem_corrida_original = True
            item.corrida = corrida
            item.save(update_fields=['corrida'])

        aplicar_entrada_item(item)
        creditados.append(
            {
                'item_id': item.pk,
                'produto_id': item.produto_id,
                'corrida_id': item.corrida_id,
                'corrida_numero': item.corrida.numero if item.corrida_id else '',
                'creditado_sem_corrida_original': creditado_sem_corrida_original,
                'fornecedor_origem': origem_fornecedor,
                'quantidade': str(_dec(item.quantidade)),
            },
        )

    return {'creditados': creditados, 'pendentes': pendentes}


def _aplicar_financeiro_devolucao(
    nf_entrada: NFeEntrada,
    nf_saida: NFeSaida,
    *,
    usuario=None,
) -> dict[str, Any]:
    """Abate os títulos da saída original e converte a sobra em crédito do cliente.

    Só age quando a saída gerou títulos: uma devolução de nota em homologação não tem
    nada a abater e não pode fabricar crédito. Título já recebido (ou saldo menor que a
    devolução) não derruba a automação — vira `CreditoFinanceiro`, que é o tratamento
    que o financeiro dá a dinheiro que entrou mas voltou em mercadoria.
    """
    from apps.financeiro.models import CreditoFinanceiro, TituloFinanceiro
    from apps.financeiro.services.credito import criar_credito_financeiro
    from apps.financeiro.services.movimento import MovimentoFinanceiroError, registrar_abatimento_devolucao
    from apps.fiscal.nfe_saida_financeiro import titulos_vinculados_nfe

    titulos = list(
        titulos_vinculados_nfe(nf_saida).order_by('data_vencimento', 'id'),
    )
    if not titulos:
        return {
            'status': 'sem_titulo',
            'valor_devolvido': str(_dec(nf_entrada.valor_total)),
            'abatido': '0',
            'credito_id': None,
            'mensagens': ['Saída original sem títulos gerados — nada a abater ou creditar.'],
        }

    documento = _numero_documento(nf_entrada)
    data_movimento = nf_entrada.data or timezone.localdate()
    restante = _dec(nf_entrada.valor_total)
    if restante <= CENTAVO:
        return {
            'status': 'sem_valor',
            'valor_devolvido': str(_dec(nf_entrada.valor_total)),
            'abatido': '0',
            'credito_id': None,
            'mensagens': ['Valor da devolução igual a zero — financeiro intocado.'],
        }

    mensagens: list[str] = []
    baixas: list[dict[str, Any]] = []
    abatido = Decimal('0')

    for titulo in titulos:
        if restante <= CENTAVO:
            break
        if not titulo.pode_baixar:
            mensagens.append(f'Título {titulo.pk} sem saldo em aberto (status {titulo.status}).')
            continue
        alvo = min(restante, _dec(titulo.valor_aberto))
        if alvo <= CENTAVO:
            continue
        try:
            baixa = registrar_abatimento_devolucao(
                titulo,
                valor=alvo,
                data_abatimento=data_movimento,
                motivo=MOTIVO_ABATIMENTO,
                documento_referencia=documento,
                usuario=usuario,
            )
        except MovimentoFinanceiroError as exc:
            mensagens.append(f'Título {titulo.pk}: {exc}')
            continue
        abatido += alvo
        restante = max(Decimal('0'), restante - alvo)
        baixas.append(
            {
                'titulo_id': titulo.pk,
                'baixa_id': baixa.pk,
                'valor': str(alvo),
                'status_apos': titulo.status,
            },
        )

    credito_id = None
    if restante > CENTAVO:
        cliente_id = nf_saida.cliente_id or nf_entrada.cliente_destinatario_id
        if not cliente_id:
            mensagens.append(
                f'R$ {restante} sem abatimento e sem cliente vinculado — crédito não gerado.',
            )
        else:
            credito = criar_credito_financeiro(
                tipo=CreditoFinanceiro.Tipo.CLIENTE,
                cliente_id=cliente_id,
                valor_original=restante,
                data_credito=data_movimento,
                motivo=MOTIVO_ABATIMENTO,
                origem_tipo=CreditoFinanceiro.OrigemTipo.DEVOLUCAO,
                origem_descricao=f'NF-e de devolução {_numero_documento(nf_saida)}',
                origem_numero=documento,
                observacoes=(
                    f'Sobra da devolução: abatido R$ {abatido} nos títulos da saída, '
                    f'R$ {restante} convertido em crédito.'
                ),
                usuario=usuario,
            )
            credito_id = credito.pk

    return {
        'status': 'aplicado',
        'valor_devolvido': str(_dec(nf_entrada.valor_total)),
        'abatido': str(abatido),
        'credito_id': credito_id,
        'credito_valor': str(restante) if credito_id else '0',
        'baixas': baixas,
        'titulos_afetados': sorted({b['titulo_id'] for b in baixas}),
        'mensagens': mensagens,
    }


def _estornar_e_liberar_pedido(nf_saida: NFeSaida) -> tuple[list[dict[str, Any]], list[int]]:
    """Estorna `quantidade_faturada` e libera o faturamento para nova NF-e, sem apagar vínculos.

    Apagar `ItemFaturamentoPedidoVenda` quebraria o próprio estorno (ele percorre a FK
    `item_faturamento_pedido`) e nularia o vínculo de uma nota autorizada. A liberação
    canônica — a mesma do cancelamento SEFAZ — descola o faturamento da nota e o item
    volta a `PENDENTE`, que já é o que habilita a edição do pedido.
    """
    from apps.comercial.faturamento_pedido_venda import recalcular_status_pedido
    from apps.comercial.models import PedidoVenda
    from apps.fiscal.nfe_saida_ciclo_vida import _liberar_faturamento_para_nova_nfe
    from apps.fiscal.nfe_saida_efeitos import _lock_faturamento
    from apps.fiscal.nfe_saida_pedido_cancelamento import _estornar_quantidades_pedido_da_nfe

    estorno_resumo, pedido_ids = _estornar_quantidades_pedido_da_nfe(nf_saida)

    fat = _lock_faturamento(nf_saida.faturamento_pedido_venda_id)
    if fat.nfe_saida_id == nf_saida.pk:
        _liberar_faturamento_para_nova_nfe(fat)

    for pid in sorted(pedido_ids):
        pedido = PedidoVenda.objects.select_for_update().get(pk=pid)
        recalcular_status_pedido(pedido)

    return estorno_resumo, sorted(pedido_ids)


@transaction.atomic
def aplicar_efeitos_devolucao_pos_autorizacao(
    nf_entrada: NFeEntrada,
    *,
    usuario=None,
) -> dict[str, Any]:
    """Aplica pedido + estoque + financeiro de uma entrada de devolução autorizada.

    Idempotente pelo carimbo `efeitos_devolucao_aplicados_em`: um reprocessamento de
    retorno SEFAZ sobre a mesma nota não pode creditar estoque duas vezes.
    """
    if (nf_entrada.fin_nfe or '').strip() != '4':
        return {'aplicado': False, 'motivo': 'Não é devolução (finNFe≠4).'}
    if not nf_entrada.nfe_saida_origem_id:
        return {'aplicado': False, 'motivo': 'Sem nfe_saida_origem.'}

    nf_saida = nf_entrada.nfe_saida_origem
    if not nf_saida.faturamento_pedido_venda_id:
        return {'aplicado': False, 'motivo': 'NF saída sem faturamento.'}
    if nf_entrada.efeitos_devolucao_aplicados_em:
        return {'aplicado': False, 'motivo': 'Já aplicado antes.'}

    estorno_resumo, pedidos_afetados = _estornar_e_liberar_pedido(nf_saida)
    estoque = _aplicar_estoque_devolucao(nf_entrada)
    financeiro = _aplicar_financeiro_devolucao(nf_entrada, nf_saida, usuario=usuario)

    nf_entrada.efeitos_devolucao_aplicados_em = timezone.now()
    if usuario and getattr(usuario, 'is_authenticated', False):
        nf_entrada.efeitos_devolucao_por = usuario
    nf_entrada.save(update_fields=['efeitos_devolucao_aplicados_em', 'efeitos_devolucao_por'])

    resumo = {
        'aplicado': True,
        'nfe_entrada_id': nf_entrada.pk,
        'nfe_saida_id': nf_saida.pk,
        'estorno_resumo': estorno_resumo,
        'pedidos_afetados': pedidos_afetados,
        'estoque': estoque,
        'financeiro': financeiro,
    }
    logger.info(
        'DEVOLUCAO_EFEITOS_APLICADOS nfe_entrada_id=%s nfe_saida_id=%s pedidos=%s '
        'estoque_creditado=%s estoque_pendente=%s abatido=%s credito_id=%s',
        nf_entrada.pk,
        nf_saida.pk,
        pedidos_afetados,
        len(estoque['creditados']),
        len(estoque['pendentes']),
        financeiro.get('abatido', '0'),
        financeiro.get('credito_id'),
    )
    return resumo


def listar_devolucoes_com_efeitos_pendentes():
    """Devoluções autorizadas cujos efeitos ainda não foram aplicados — a fila de reparo.

    Uma falha no orquestrador roda depois do commit da autorização: o status SEFAZ fica
    como está e o carimbo não é gravado. A ausência do carimbo é, portanto, a marca de
    pendência (sem migration). Reprocessar é seguro — o orquestrador é idempotente e
    cada nova aplicação roda em transação própria.
    """
    return (
        NFeEntrada.objects.filter(
            fin_nfe='4',
            nfe_saida_origem__isnull=False,
            efeitos_devolucao_aplicados_em__isnull=True,
            status_emissao_sefaz__in=list(STATUS_AUTORIZADOS),
        )
        .order_by('-autorizada_em', '-id')
        .select_related('nfe_saida_origem')
    )
