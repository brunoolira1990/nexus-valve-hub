from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .models import (
    ItemNFeEntradaConferencia,
    ItemNFeEntradaConferenciaCorridaSplit,
    ItemNFeSaida,
)


def _parse_date(raw: str | None, field_name: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ValidationError({field_name: f'{field_name} deve estar no formato AAAA-MM-DD.'}) from None


def _decimal_text(value: Decimal) -> str:
    return f'{value:.3f}'


def _movement_timestamp(value: datetime | None, fallback_date: date | None) -> datetime:
    if value is not None:
        return value
    return datetime.combine(fallback_date or date.min, datetime.min.time())


def _corrida_data(*, corrida_obj=None, estoque_corrida=None) -> tuple[int | None, str]:
    if estoque_corrida is not None:
        corrida = getattr(estoque_corrida, 'corrida', None)
        if corrida is not None:
            return corrida.id, corrida.numero
    if corrida_obj is not None:
        return corrida_obj.id, corrida_obj.numero
    return None, ''


def _base_evento(
    *,
    evento_id: str,
    natureza: str,
    quantidade: Decimal,
    movimento_em: datetime | None,
    data_documento: date | None,
    produto,
    corrida_id: int | None,
    corrida_numero: str,
    documento: str,
    documento_id: int | None,
    origem: str,
    observacao: str = '',
) -> dict:
    sinal = quantidade if natureza in {'ENTRADA', 'ESTORNO'} else -quantidade
    return {
        'id': evento_id,
        'natureza': natureza,
        'natureza_label': {
            'ENTRADA': 'Entrada física',
            'SAIDA': 'Saída física',
            'ESTORNO': 'Estorno de saída',
        }[natureza],
        'quantidade': _decimal_text(quantidade),
        'quantidade_assinada': _decimal_text(sinal),
        'movimento_em': movimento_em.isoformat() if movimento_em else None,
        'data': (movimento_em.date() if movimento_em else data_documento).isoformat()
        if (movimento_em or data_documento)
        else None,
        'produto_id': produto.id,
        'codigo': produto.codigo_completo or produto.codigo or '',
        'descricao': produto.descricao,
        'unidade': (produto.get_unidade_estoque_efetiva() or produto.unidade or 'UN').upper(),
        'corrida_id': corrida_id,
        'corrida': corrida_numero,
        'documento': documento,
        'documento_id': documento_id,
        'origem': origem,
        'observacao': observacao,
    }


def _eventos_entrada() -> list[dict]:
    eventos: list[dict] = []
    splits = (
        ItemNFeEntradaConferenciaCorridaSplit.objects.filter(
            quantidade_aplicada__gt=0,
            estoque_corrida__isnull=False,
            item_conferencia__estoque_aplicado_em__isnull=False,
            item_conferencia__produto__isnull=False,
        )
        .select_related(
            'item_conferencia__produto',
            'item_conferencia__conferencia__nf_entrada_historica',
            'item_conferencia__item_nfe_historico__nf',
            'estoque_corrida__corrida',
            'corrida_estoque',
        )
        .order_by('item_conferencia__estoque_aplicado_em', 'id')
    )
    for split in splits:
        item = split.item_conferencia
        nf = item.item_nfe_historico.nf
        corrida_id, corrida_numero = _corrida_data(
            corrida_obj=split.corrida_estoque,
            estoque_corrida=split.estoque_corrida,
        )
        movimento_em = item.estoque_aplicado_em
        eventos.append(
            _base_evento(
                evento_id=f'entrada-split-{split.id}',
                natureza='ENTRADA',
                quantidade=split.quantidade_aplicada,
                movimento_em=movimento_em,
                data_documento=nf.dh_emissao.date(),
                produto=item.produto,
                corrida_id=corrida_id,
                corrida_numero=corrida_numero or split.corrida or split.lote,
                documento=f'NF-e entrada {nf.numero}',
                documento_id=nf.id,
                origem='CONFERENCIA_NFE_ENTRADA',
                observacao=f'Lote {split.lote}' if split.lote else '',
            )
        )

    legacy_items = (
        ItemNFeEntradaConferencia.objects.filter(
            estoque_aplicado_em__isnull=False,
            quantidade_estoque_aplicada__gt=0,
            estoque_corrida__isnull=False,
            produto__isnull=False,
            corridas_split__isnull=True,
        )
        .select_related(
            'produto',
            'item_nfe_historico__nf',
            'estoque_corrida__corrida',
            'corrida_estoque',
        )
        .order_by('estoque_aplicado_em', 'id')
    )
    for item in legacy_items:
        nf = item.item_nfe_historico.nf
        corrida_id, corrida_numero = _corrida_data(
            corrida_obj=item.corrida_estoque,
            estoque_corrida=item.estoque_corrida,
        )
        eventos.append(
            _base_evento(
                evento_id=f'entrada-item-{item.id}',
                natureza='ENTRADA',
                quantidade=item.quantidade_estoque_aplicada,
                movimento_em=item.estoque_aplicado_em,
                data_documento=nf.dh_emissao.date(),
                produto=item.produto,
                corrida_id=corrida_id,
                corrida_numero=corrida_numero or item.corrida or item.lote,
                documento=f'NF-e entrada {nf.numero}',
                documento_id=nf.id,
                origem='CONFERENCIA_NFE_ENTRADA_LEGADA',
                observacao=f'Lote {item.lote}' if item.lote else '',
            )
        )
    return eventos


def _eventos_saida() -> list[dict]:
    eventos: list[dict] = []
    itens = (
        ItemNFeSaida.objects.filter(
            nf__efeitos_autorizacao_aplicados_em__isnull=False,
            nf__modo_atendimento_estoque='IMEDIATO',
            quantidade__gt=0,
            corrida__isnull=False,
        )
        .select_related('nf', 'produto', 'corrida')
        .order_by('nf__efeitos_autorizacao_aplicados_em', 'id')
    )
    for item in itens:
        nf = item.nf
        autorizacao_em = nf.efeitos_autorizacao_aplicados_em
        eventos.append(
            _base_evento(
                evento_id=f'saida-item-{item.id}',
                natureza='SAIDA',
                quantidade=item.quantidade,
                movimento_em=autorizacao_em,
                data_documento=nf.data,
                produto=item.produto,
                corrida_id=item.corrida_id,
                corrida_numero=item.corrida.numero,
                documento=f'NF-e saída {nf.numero}',
                documento_id=nf.id,
                origem='NFE_SAIDA_AUTORIZADA',
            )
        )
        if nf.efeitos_cancelamento_aplicados_em:
            eventos.append(
                _base_evento(
                    evento_id=f'estorno-item-{item.id}',
                    natureza='ESTORNO',
                    quantidade=item.quantidade,
                    movimento_em=nf.efeitos_cancelamento_aplicados_em,
                    data_documento=nf.data,
                    produto=item.produto,
                    corrida_id=item.corrida_id,
                    corrida_numero=item.corrida.numero,
                    documento=f'NF-e saída {nf.numero} — cancelamento',
                    documento_id=nf.id,
                    origem='NFE_SAIDA_CANCELAMENTO',
                    observacao=nf.motivo_cancelamento or '',
                )
            )
    return eventos


def _apply_filters(events: list[dict], query_params) -> list[dict]:
    produto_id = query_params.get('produto_id')
    if produto_id:
        try:
            produto_id_int = int(produto_id)
        except (TypeError, ValueError):
            raise ValidationError({'produto_id': 'produto_id inválido.'}) from None
        events = [event for event in events if event['produto_id'] == produto_id_int]

    corrida_id = query_params.get('corrida_id')
    if corrida_id:
        try:
            corrida_id_int = int(corrida_id)
        except (TypeError, ValueError):
            raise ValidationError({'corrida_id': 'corrida_id inválido.'}) from None
        events = [event for event in events if event['corrida_id'] == corrida_id_int]

    for key in ('codigo', 'descricao', 'corrida'):
        value = (query_params.get(key) or '').strip().lower()
        if value:
            events = [event for event in events if value in str(event.get(key) or '').lower()]

    search = (query_params.get('search') or '').strip().lower()
    if search:
        fields = ('codigo', 'descricao', 'corrida', 'documento', 'origem')
        events = [
            event
            for event in events
            if any(search in str(event.get(field) or '').lower() for field in fields)
        ]

    natureza = (query_params.get('natureza') or '').strip().upper()
    if natureza:
        allowed = {'ENTRADA', 'SAIDA', 'ESTORNO'}
        if natureza not in allowed:
            raise ValidationError({'natureza': 'natureza inválida.'})
        events = [event for event in events if event['natureza'] == natureza]

    inicio = _parse_date(query_params.get('data_inicio'), 'data_inicio')
    fim = _parse_date(query_params.get('data_fim'), 'data_fim')
    if inicio and fim and inicio > fim:
        raise ValidationError({'data_inicio': 'data_inicio não pode ser posterior a data_fim.'})
    if inicio:
        events = [event for event in events if event['data'] and event['data'] >= inicio.isoformat()]
    if fim:
        events = [event for event in events if event['data'] and event['data'] <= fim.isoformat()]
    return events


def build_kardex_payload(query_params) -> tuple[list[dict], dict]:
    events = _apply_filters(_eventos_entrada() + _eventos_saida(), query_params)
    events.sort(key=lambda event: (event['movimento_em'] or '', event['id']))
    saldo = Decimal('0')
    entrada = Decimal('0')
    saida = Decimal('0')
    estorno = Decimal('0')
    for event in events:
        signed = Decimal(event['quantidade_assinada'])
        saldo += signed
        event['saldo_acumulado'] = _decimal_text(saldo)
        quantity = Decimal(event['quantidade'])
        if event['natureza'] == 'ENTRADA':
            entrada += quantity
        elif event['natureza'] == 'SAIDA':
            saida += quantity
        else:
            estorno += quantity
    return events, {
        'entradas': _decimal_text(entrada),
        'saidas': _decimal_text(saida),
        'estornos': _decimal_text(estorno),
        'saldo_final': _decimal_text(saldo),
        'quantidade_eventos': len(events),
    }
