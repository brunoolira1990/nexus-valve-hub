"""Fase 3.11 — aplicação física de estoque a partir da conferência NF-e entrada."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.corridas.models import Corrida
from apps.fiscal.conferencia_pedido import (
    STATUS_ELEGIBILIDADE_APTO,
    STATUS_ELEGIBILIDADE_APTO_COM_ALERTA,
    STATUS_ELEGIBILIDADE_BLOQUEADO,
    STATUS_ELEGIBILIDADE_NAO_MOVIMENTA,
    aplicar_pos_save_item_conferencia,
    avaliar_elegibilidade_estoque_item_conferencia,
    carregar_certificados_fornecedor_por_item_conferencia,
)
from apps.fiscal.models import (
    AtendimentoEstoque,
    AtendimentoEstoqueLinha,
    EstoqueCorrida,
    ItemNFeEntradaConferencia,
    NFeEntradaConferencia,
)
from apps.regras_fiscais.entrada_fiscal import (
    avaliar_item_entrada_fiscal,
    carregar_regras_fiscais_entrada_ativas,
    montar_contexto_fiscal_entrada,
)


class ItemAplicadoEstoqueDict(TypedDict):
    item_conferencia_id: int
    produto_id: int
    corrida: str
    lote: str
    quantidade: str
    estoque_corrida_id: int
    saldo_anterior: str
    saldo_novo: str


class ItemIgnoradoEstoqueDict(TypedDict):
    item_conferencia_id: int
    motivo: str


class PendenciaAplicacaoEstoqueDict(TypedDict):
    item_conferencia_id: int | None
    motivo: str


class ResultadoAplicacaoEstoqueDict(TypedDict):
    aplicado: bool
    conferencia_id: int
    itens_aplicados: list[ItemAplicadoEstoqueDict]
    itens_ignorados: list[ItemIgnoradoEstoqueDict]
    pendencias: list[PendenciaAplicacaoEstoqueDict]
    alertas: list[str]


@dataclass
class _ItemPlano:
    item: ItemNFeEntradaConferencia
    resultado_fiscal: dict[str, Any]
    elegibilidade: dict[str, Any]
    quantidade: Decimal
    categoria: str  # aplicar | ignorar | bloqueio | alerta
    motivo: str = ''


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _fmt_qty(v: Decimal) -> str:
    return f'{v:.3f}'


def normalizar_numero_corrida(texto: str) -> str:
    return (texto or '').strip().upper()[:64]


def quantidade_aplicar_item(item_conf: ItemNFeEntradaConferencia) -> Decimal:
    q = _dec(item_conf.quantidade_estoque_calculada)
    if q > 0:
        return q
    return _dec(item_conf.quantidade_nf)


def resolver_ou_criar_corrida(
    *,
    produto_id: int,
    fornecedor_id: int,
    numero_texto: str,
    data_recebimento: date,
    nf_entrada_ref: str = '',
) -> Corrida:
    numero = normalizar_numero_corrida(numero_texto)
    if not numero:
        raise ValueError('Número de corrida obrigatório para aplicar estoque.')
    if not fornecedor_id:
        raise ValueError(
            'Fornecedor da NF não identificado no cadastro; não é possível criar corrida mestre.',
        )

    existente = Corrida.objects.filter(numero=numero).first()
    if existente:
        if existente.produto_id != produto_id or existente.fornecedor_id != fornecedor_id:
            raise ValueError(
                f'Corrida "{numero}" já cadastrada para outro produto ou fornecedor.',
            )
        return existente

    return Corrida.objects.create(
        numero=numero,
        produto_id=produto_id,
        fornecedor_id=fornecedor_id,
        data_recebimento=data_recebimento,
        nf_entrada=(nf_entrada_ref or '')[:64],
    )


def _data_recebimento_conferencia(conferencia: NFeEntradaConferencia) -> date:
    nf = conferencia.nf_entrada_historica
    if nf.dh_emissao:
        return nf.dh_emissao.date()
    return timezone.localdate()


def _avaliar_contexto_itens(
    conferencia: NFeEntradaConferencia,
    itens: list[ItemNFeEntradaConferencia],
) -> list[_ItemPlano]:
    contexto = montar_contexto_fiscal_entrada(conferencia)
    regras = carregar_regras_fiscais_entrada_ativas()
    cert_map = carregar_certificados_fornecedor_por_item_conferencia([it.id for it in itens])
    planos: list[_ItemPlano] = []

    for item in itens:
        if item.estoque_aplicado_em:
            planos.append(
                _ItemPlano(
                    item=item,
                    resultado_fiscal={},
                    elegibilidade={},
                    quantidade=Decimal('0'),
                    categoria='bloqueio',
                    motivo='Linha já teve estoque físico aplicado.',
                ),
            )
            continue

        rf = avaliar_item_entrada_fiscal(item, contexto, regras)
        eleg = avaliar_elegibilidade_estoque_item_conferencia(
            item,
            resultado_fiscal=rf,
            divergencias_aceitas=conferencia.divergencias_aceitas,
            certificado_fornecedor_info=cert_map.get(item.id),
        )
        qty = quantidade_aplicar_item(item)
        status_eleg = (eleg.get('status') or '').upper()

        if item.status == ItemNFeEntradaConferencia.Status.IGNORADO:
            planos.append(
                _ItemPlano(item, rf, eleg, qty, 'ignorar', 'Linha ignorada na conferência.'),
            )
            continue

        if status_eleg == STATUS_ELEGIBILIDADE_NAO_MOVIMENTA:
            msg = (eleg.get('mensagens') or ['Não movimenta estoque.'])[0]
            planos.append(_ItemPlano(item, rf, eleg, qty, 'ignorar', msg))
            continue

        if status_eleg == STATUS_ELEGIBILIDADE_BLOQUEADO:
            msg = '; '.join(eleg.get('mensagens') or ['Elegibilidade bloqueada.'])
            planos.append(_ItemPlano(item, rf, eleg, qty, 'bloqueio', msg))
            continue

        if not item.produto_id:
            planos.append(
                _ItemPlano(item, rf, eleg, qty, 'bloqueio', 'Item sem produto vinculado.'),
            )
            continue

        if (rf.get('status') or '').upper() == 'BLOQUEADO':
            planos.append(
                _ItemPlano(item, rf, eleg, qty, 'bloqueio', 'Item bloqueado por regra fiscal.'),
            )
            continue

        if not (item.corrida or '').strip():
            planos.append(
                _ItemPlano(item, rf, eleg, qty, 'bloqueio', 'Item sem corrida informada.'),
            )
            continue

        if qty <= 0:
            planos.append(
                _ItemPlano(item, rf, eleg, qty, 'bloqueio', 'Quantidade a aplicar deve ser maior que zero.'),
            )
            continue

        if rf.get('movimenta_estoque') is False:
            planos.append(
                _ItemPlano(
                    item,
                    rf,
                    eleg,
                    qty,
                    'ignorar',
                    'Regra fiscal indica que não movimenta estoque.',
                ),
            )
            continue

        if status_eleg == STATUS_ELEGIBILIDADE_APTO_COM_ALERTA:
            planos.append(_ItemPlano(item, rf, eleg, qty, 'alerta', ''))
            continue

        if status_eleg == STATUS_ELEGIBILIDADE_APTO:
            planos.append(_ItemPlano(item, rf, eleg, qty, 'aplicar', ''))
            continue

        planos.append(
            _ItemPlano(item, rf, eleg, qty, 'bloqueio', f'Status de elegibilidade desconhecido: {status_eleg}.'),
        )

    return planos


def montar_preview_aplicacao_estoque_conferencia(
    conferencia: NFeEntradaConferencia,
    *,
    confirmar_alertas: bool = False,
) -> ResultadoAplicacaoEstoqueDict:
    return _montar_resultado_plano(conferencia, confirmar_alertas=confirmar_alertas, aplicar=False)


def _montar_resultado_plano(
    conferencia: NFeEntradaConferencia,
    *,
    confirmar_alertas: bool,
    aplicar: bool,
) -> ResultadoAplicacaoEstoqueDict:
    resultado: ResultadoAplicacaoEstoqueDict = {
        'aplicado': False,
        'conferencia_id': conferencia.id,
        'itens_aplicados': [],
        'itens_ignorados': [],
        'pendencias': [],
        'alertas': [],
    }

    if conferencia.estoque_aplicado_em:
        resultado['pendencias'].append(
            {
                'item_conferencia_id': None,
                'motivo': 'Conferência já teve estoque físico aplicado.',
            },
        )
        return resultado

    if conferencia.status not in (
        NFeEntradaConferencia.Status.CONFERIDA,
        NFeEntradaConferencia.Status.PREPARADA,
    ):
        resultado['pendencias'].append(
            {
                'item_conferencia_id': None,
                'motivo': 'Conferência deve estar CONFERIDA ou PREPARADA para aplicar estoque.',
            },
        )
        return resultado

    if not conferencia.nf_entrada_historica.fornecedor_emitente_id:
        resultado['pendencias'].append(
            {
                'item_conferencia_id': None,
                'motivo': 'NF sem fornecedor cadastrado; não é possível criar corrida mestre.',
            },
        )
        return resultado

    itens = list(
        conferencia.itens.select_related(
            'item_nfe_historico',
            'produto',
            'conferencia__nf_entrada_historica__fornecedor_emitente',
        ).all(),
    )
    for item in itens:
        aplicar_pos_save_item_conferencia(item, conferencia)

    planos = _avaliar_contexto_itens(conferencia, itens)

    bloqueios = [p for p in planos if p.categoria == 'bloqueio']
    alertas_planos = [p for p in planos if p.categoria == 'alerta']

    for p in bloqueios:
        resultado['pendencias'].append(
            {
                'item_conferencia_id': p.item.id,
                'motivo': p.motivo,
            },
        )

    for p in alertas_planos:
        for msg in p.elegibilidade.get('mensagens') or []:
            if msg and msg not in resultado['alertas']:
                resultado['alertas'].append(msg)

    if bloqueios:
        return resultado

    for p in planos:
        if p.categoria == 'ignorar':
            resultado['itens_ignorados'].append(
                {
                    'item_conferencia_id': p.item.id,
                    'motivo': p.motivo,
                },
            )

    if alertas_planos and not confirmar_alertas:
        if not resultado['alertas']:
            resultado['alertas'].append(
                'Existem itens aptos com alerta; confirme com confirmar_alertas=true.',
            )
        return resultado

    if not aplicar:
        for p in planos:
            if p.categoria == 'aplicar':
                resultado['itens_aplicados'].append(
                    {
                        'item_conferencia_id': p.item.id,
                        'produto_id': p.item.produto_id or 0,
                        'corrida': (p.item.corrida or '').strip(),
                        'lote': (p.item.lote or '').strip(),
                        'quantidade': _fmt_qty(p.quantidade),
                        'estoque_corrida_id': 0,
                        'saldo_anterior': '—',
                        'saldo_novo': '—',
                    },
                )
        return resultado

    return resultado


@transaction.atomic
def aplicar_estoque_fisico_conferencia(
    conferencia: NFeEntradaConferencia,
    *,
    confirmar_alertas: bool = False,
    observacao: str = '',
    usuario=None,
) -> ResultadoAplicacaoEstoqueDict:
    conferencia = (
        NFeEntradaConferencia.objects.select_for_update(of=('self',))
        .select_related('nf_entrada_historica__fornecedor_emitente')
        .get(pk=conferencia.pk)
    )

    preview = _montar_resultado_plano(
        conferencia,
        confirmar_alertas=confirmar_alertas,
        aplicar=False,
    )
    if preview['pendencias'] or (preview['alertas'] and not confirmar_alertas):
        return preview

    itens = list(
        conferencia.itens.select_related(
            'item_nfe_historico',
            'produto',
        ).all(),
    )
    planos = _avaliar_contexto_itens(conferencia, itens)
    aplicaveis = [p for p in planos if p.categoria == 'aplicar']

    if not aplicaveis and not preview['itens_ignorados']:
        preview['pendencias'].append(
            {
                'item_conferencia_id': None,
                'motivo': 'Nenhum item elegível para aplicar estoque.',
            },
        )
        return preview

    nf = conferencia.nf_entrada_historica
    fornecedor_id = nf.fornecedor_emitente_id
    data_rec = _data_recebimento_conferencia(conferencia)
    nf_ref = nf.numero or ''

    resultado = preview
    resultado['itens_aplicados'] = []
    agora = timezone.now()

    for plano in aplicaveis:
        item = ItemNFeEntradaConferencia.objects.select_for_update(of=('self',)).get(pk=plano.item.pk)
        if item.estoque_aplicado_em:
            raise ValueError(f'Item {item.id} já aplicado (concorrência).')

        corrida = resolver_ou_criar_corrida(
            produto_id=item.produto_id,
            fornecedor_id=fornecedor_id,
            numero_texto=item.corrida,
            data_recebimento=data_rec,
            nf_entrada_ref=nf_ref,
        )

        ec, _ = EstoqueCorrida.objects.select_for_update(of=('self',)).get_or_create(
            produto_id=item.produto_id,
            corrida_id=corrida.id,
            defaults={'saldo': Decimal('0')},
        )
        saldo_anterior = _dec(ec.saldo)
        qtd = plano.quantidade
        ec.saldo = saldo_anterior + qtd
        ec.save(update_fields=['saldo'])

        item.estoque_aplicado_em = agora
        item.quantidade_estoque_aplicada = qtd
        item.corrida_estoque = corrida
        item.estoque_corrida = ec
        item.save(
            update_fields=[
                'estoque_aplicado_em',
                'quantidade_estoque_aplicada',
                'corrida_estoque',
                'estoque_corrida',
                'atualizado_em',
            ],
        )

        resultado['itens_aplicados'].append(
            {
                'item_conferencia_id': item.id,
                'produto_id': item.produto_id,
                'corrida': corrida.numero,
                'lote': (item.lote or '').strip(),
                'quantidade': _fmt_qty(qtd),
                'estoque_corrida_id': ec.id,
                'saldo_anterior': _fmt_qty(saldo_anterior),
                'saldo_novo': _fmt_qty(ec.saldo),
            },
        )

    conferencia.estoque_aplicado_em = agora
    conferencia.estoque_aplicado_observacao = (observacao or '').strip()
    if usuario and getattr(usuario, 'is_authenticated', False):
        conferencia.estoque_aplicado_por = usuario
    conferencia.save(
        update_fields=[
            'estoque_aplicado_em',
            'estoque_aplicado_observacao',
            'estoque_aplicado_por',
            'atualizado_em',
        ],
    )

    _atualizar_atendimentos_pos_aplicacao_fisica(conferencia, agora)

    resultado['aplicado'] = True
    return resultado


def _atualizar_atendimentos_pos_aplicacao_fisica(
    conferencia: NFeEntradaConferencia,
    agora,
) -> None:
    atendimento_ids = list(
        AtendimentoEstoqueLinha.objects.filter(conferencia=conferencia)
        .values_list('atendimento_id', flat=True)
        .distinct(),
    )
    for atend_id in atendimento_ids:
        atend = AtendimentoEstoque.objects.select_for_update(of=('self',)).get(pk=atend_id)
        if atend.status != AtendimentoEstoque.Status.ATENDIDO:
            continue
        if atend.estoque_fisico_aplicado:
            continue
        linhas = list(atend.linhas.select_related('item_conferencia').all())
        if not linhas:
            continue
        if all(l.item_conferencia.estoque_aplicado_em for l in linhas):
            atend.estoque_fisico_aplicado = True
            atend.estoque_aplicado_em = agora
            atend.save(update_fields=['estoque_fisico_aplicado', 'estoque_aplicado_em', 'atualizado_em'])
