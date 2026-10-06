"""Gera rascunho de NF-e Saida a partir de conferencia de compra (NFeEntradaConferencia).

Representa a devolucao da mercadoria ao fornecedor. Nao transmite SEFAZ, nao
aplica estoque, nao mexe em XML — apenas cria o rascunho no banco.

Referencia espelho: nfe_entrada_from_saida_devolucao.py (fluxo inverso).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.fiscal.models import (
    ItemDevolucaoCompra,
    ItemNFeEntradaConferencia,
    ItemNFeSaida,
    NFeEntradaConferencia,
    NFeSaida,
)


MOTIVOS_LABEL = {
    'NAO_CONFORME': 'Devolucao de mercadoria nao conforme',
    'DEFEITO': 'Devolucao de mercadoria com defeito',
    'ERRO_PEDIDO': 'Devolucao por erro de pedido',
    'AVARIA_TRANSPORTE': 'Devolucao por avaria no transporte',
    'OUTRO': '',
}

STATUS_ITEM_DEVOLVIVEL = frozenset({'CONFERIDO', 'PRODUTO_VINCULADO'})
STATUS_CONFERENCIA_PERMITIDO = frozenset({'CONFERIDA', 'PREPARADA'})


class NFeSaidaFromEntradaError(ValueError):
    pass


# --- Helpers -----------------------------------------------------------------


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise NFeSaidaFromEntradaError(f'Valor numerico invalido: {val!r}') from exc


def _cfop_devolucao_saida(*, uf_empresa: str, uf_fornecedor: str) -> str:
    ue = (uf_empresa or '').strip().upper()
    uf = (uf_fornecedor or '').strip().upper()
    if ue and uf and ue == uf:
        return '5202'
    return '6202'


def _saldo_item(item_conf: ItemNFeEntradaConferencia) -> Decimal:
    devolvido = (
        ItemDevolucaoCompra.objects
        .filter(item_conferencia=item_conf)
        .aggregate(total=Sum('quantidade_devolvida'))['total']
        or Decimal('0')
    )
    return _dec(item_conf.quantidade_estoque_calculada) - _dec(devolvido)


def _resolver_quantidades(
    *,
    conferencia: NFeEntradaConferencia,
    itens: list[dict] | None,
) -> list[tuple[ItemNFeEntradaConferencia, Decimal]]:
    """Retorna [(item_conferencia, quantidade_a_devolver)].

    Se itens=None/vazio -> usa todos os itens devolviveis com saldo > 0.
    Se itens preenchido -> valida cada entrada (pertence a conferencia, qtd > 0,
    qtd <= saldo).
    """
    if itens:
        selecionados: list[tuple[ItemNFeEntradaConferencia, Decimal]] = []
        ids_vistos: set[int] = set()
        for entrada in itens:
            item_id = entrada.get('item_conferencia_id')
            qtd = _dec(entrada.get('quantidade'))
            if item_id is None:
                raise NFeSaidaFromEntradaError(
                    'Item de devolucao sem "item_conferencia_id".'
                )
            if item_id in ids_vistos:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id} duplicado na selecao.'
                )
            ids_vistos.add(item_id)
            try:
                item_conf = ItemNFeEntradaConferencia.objects.get(pk=item_id)
            except ItemNFeEntradaConferencia.DoesNotExist as exc:
                raise NFeSaidaFromEntradaError(
                    f'Item de conferencia {item_id} nao existe.'
                ) from exc
            if item_conf.conferencia_id != conferencia.pk:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id} nao pertence a conferencia {conferencia.pk}.'
                )
            if item_conf.status not in STATUS_ITEM_DEVOLVIVEL:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id} com status {item_conf.status!r} nao pode ser devolvido.'
                )
            if qtd <= 0:
                raise NFeSaidaFromEntradaError(
                    f'Quantidade invalida para item {item_id}: {qtd}.'
                )
            saldo = _saldo_item(item_conf)
            if qtd > saldo:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id}: quantidade solicitada ({qtd}) maior que '
                    f'saldo disponivel ({saldo}).'
                )
            selecionados.append((item_conf, qtd))
        return selecionados

    # Sem selecao explicita: pega tudo com saldo > 0
    qs = (
        ItemNFeEntradaConferencia.objects
        .filter(conferencia=conferencia, status__in=STATUS_ITEM_DEVOLVIVEL)
        .order_by('item_nfe_historico__n_item', 'id')
    )
    resultado: list[tuple[ItemNFeEntradaConferencia, Decimal]] = []
    for item_conf in qs:
        saldo = _saldo_item(item_conf)
        if saldo > 0:
            resultado.append((item_conf, saldo))
    return resultado


def _montar_snapshot_fiscal(*, cfop: str) -> dict[str, Any]:
    """Shape compativel com o esperado pelo XML de saida. CSTs serao preenchidos
    pelo Commit 5 (RegraFiscalSaida). Aqui ficam placeholders neutros."""
    return {
        'cfop': cfop,
        'icms': {'cst': '', 'orig': '0', 'base': None, 'aliquota': None, 'valor': None},
        'pis': {'cst': '', 'base': None, 'aliquota': None, 'valor': None},
        'cofins': {'cst': '', 'base': None, 'aliquota': None, 'valor': None},
    }


def _gerar_numero_interno(*, chave_compra: str) -> str:
    sufixo = (chave_compra or '')[-8:].strip() or 'SEMCHAVE'
    # uuid4[:6] evita colisao em devolucoes simultaneas
    return f'DEV-{sufixo}-{uuid4().hex[:6]}'[:64]


# --- Entrada principal -------------------------------------------------------


@transaction.atomic
def gerar_saida_devolucao_compra(
    conferencia: NFeEntradaConferencia,
    *,
    itens: list[dict] | None = None,
    motivo: str,
    observacao: str = '',
    usuario=None,
) -> dict[str, Any]:
    """Cria rascunho de NFeSaida de devolucao ao fornecedor.

    itens: lista de {'item_conferencia_id': int, 'quantidade': str|Decimal}.
           Se None/vazia, usa todos os itens conferidos com saldo > 0.
    motivo: uma das chaves de MOTIVOS_LABEL.
    """
    del usuario  # reservado para trilha futura

    # 1. Lock na conferencia (evita duas devolucoes simultaneas).
    # Postgres recusa FOR UPDATE em outer join de FK nullable, então
    # travamos só a linha de NFeEntradaConferencia (self) e carregamos os
    # relacionados via lazy access logo abaixo.
    conf = (
        NFeEntradaConferencia.objects
        .select_for_update(of=('self',))
        .get(pk=conferencia.pk)
    )

    # 2. Validacoes
    status_conf = (conf.status or '').strip().upper()
    if status_conf not in STATUS_CONFERENCIA_PERMITIDO:
        raise NFeSaidaFromEntradaError(
            f'Conferencia com status {conf.status!r} nao permite devolucao '
            f'(esperado: {", ".join(sorted(STATUS_CONFERENCIA_PERMITIDO))}).'
        )

    historica = conf.nf_entrada_historica
    if historica is None:
        raise NFeSaidaFromEntradaError('Conferencia sem NF-e historica vinculada.')

    fornecedor = historica.fornecedor_emitente
    if fornecedor is None:
        raise NFeSaidaFromEntradaError(
            'NF-e de compra sem fornecedor_emitente vinculado.'
        )

    empresa = historica.empresa_destinataria
    if empresa is None:
        raise NFeSaidaFromEntradaError(
            'NF-e de compra sem empresa_destinataria vinculada.'
        )

    motivo_norm = (motivo or '').strip().upper()
    if motivo_norm not in MOTIVOS_LABEL:
        raise NFeSaidaFromEntradaError(
            f'Motivo invalido: {motivo!r}. Valores: {", ".join(MOTIVOS_LABEL)}.'
        )
    if motivo_norm == 'OUTRO' and not (observacao or '').strip():
        raise NFeSaidaFromEntradaError('Motivo "OUTRO" exige observacao.')

    chave_compra = (historica.chave_acesso or '').strip()
    if len(chave_compra) != 44:
        raise NFeSaidaFromEntradaError(
            'NF-e historica sem chave de acesso valida (44 digitos).'
        )

    # 3. Selecao de itens
    pares = _resolver_quantidades(conferencia=conf, itens=itens)
    if not pares:
        raise NFeSaidaFromEntradaError(
            'Nenhum item elegivel para devolucao (saldo zerado ou nenhum conferido).'
        )

    # 4. CFOP (por UF — Commit 5 refina via RegraFiscalSaida)
    cfop = _cfop_devolucao_saida(
        uf_empresa=getattr(empresa, 'uf', '') or '',
        uf_fornecedor=getattr(fornecedor, 'uf', '') or '',
    )
    snapshot_fiscal = _montar_snapshot_fiscal(cfop=cfop)

    # 5. Criar NFeSaida
    motivo_label = MOTIVOS_LABEL[motivo_norm]
    obs_final = (
        f'Devolucao de compra - {motivo_label or "outro"}. {observacao.strip()}'
    ).strip()

    nf_saida = NFeSaida.objects.create(
        numero=_gerar_numero_interno(chave_compra=chave_compra),
        cliente=None,
        fornecedor=fornecedor,
        nfe_entrada_conferencia_origem=conf,
        data=date.today(),
        valor_total=Decimal('0'),
        status='RASCUNHO',
        observacoes_nfe=obs_final,
    )

    # 6. Criar itens + vinculos
    valor_total = Decimal('0')
    for item_conf, qtd in pares:
        produto = item_conf.produto
        snap_prod = (
            item_conf.snapshot_produto
            if isinstance(item_conf.snapshot_produto, dict)
            else {}
        )
        item_saida = ItemNFeSaida.objects.create(
            nf=nf_saida,
            produto=produto,
            quantidade=qtd,
            valor=_dec(item_conf.valor_unitario_nf),
            snapshot_produto=snap_prod,
            snapshot_fiscal=dict(snapshot_fiscal),
            observacao_item=f'Devolucao do item conferencia {item_conf.pk}',
        )
        ItemDevolucaoCompra.objects.create(
            item_nf_saida=item_saida,
            item_conferencia=item_conf,
            quantidade_devolvida=qtd,
        )
        valor_total += qtd * _dec(item_conf.valor_unitario_nf)

    # 7. Fechar total (2 casas — mesmo do Decimal(14,2) do model)
    nf_saida.valor_total = valor_total.quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP,
    )
    nf_saida.save(update_fields=['valor_total'])

    return {
        'ok': True,
        'ja_existia': False,
        'nf_saida_id': nf_saida.pk,
        'numero': nf_saida.numero,
        'valor_total': str(nf_saida.valor_total),
        'itens_criados': len(pares),
        'cfop': cfop,
        'mensagem': (
            'Rascunho de devolucao criado. Revise os dados e emita pela tela '
            'de NF-e de Saida.'
        ),
    }
