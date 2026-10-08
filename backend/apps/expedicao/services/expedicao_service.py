"""Serviços Expedição/Logística — controle manual, sem efeitos em estoque/financeiro/fiscal."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.expedicao.models import Expedicao, StatusExpedicao, TipoOperacaoExpedicao
from apps.fiscal.models import NFeSaida


class ExpedicaoErro(ValueError):
    pass


_STATUS_TERMINAIS = frozenset(
    {
        StatusExpedicao.ENTREGUE_CLIENTE,
        StatusExpedicao.CANCELADO,
    },
)


def _dec_opcional(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    s = str(v).strip().replace(',', '.')
    if not s or s.lower() in {'none', 'null', 'nan', '-'}:
        return None
    try:
        d = Decimal(s)
    except Exception as exc:
        raise ExpedicaoErro(f'Valor numérico inválido: {v!r}') from exc
    if d < 0:
        raise ExpedicaoErro('Pesos não podem ser negativos.')
    return d


def _int_opcional(v: Any, *, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    s = str(v).strip()
    if not s:
        return default
    try:
        i = int(s)
    except (TypeError, ValueError) as exc:
        raise ExpedicaoErro(f'Valor inteiro inválido: {v!r}') from exc
    if i < 0:
        raise ExpedicaoErro('Volumes não podem ser negativos.')
    return i


def gerar_codigo_expedicao(*, quando: date | None = None) -> str:
    ref = quando or timezone.localdate()
    prefixo = f'EXP-{ref.strftime("%Y%m%d")}-'
    ultimo = (
        Expedicao.objects.filter(codigo__startswith=prefixo)
        .order_by('-codigo')
        .values_list('codigo', flat=True)
        .first()
    )
    seq = 1
    if ultimo:
        try:
            seq = int(str(ultimo).split('-')[-1]) + 1
        except (TypeError, ValueError):
            seq = Expedicao.objects.filter(codigo__startswith=prefixo).count() + 1
    return f'{prefixo}{seq:04d}'


_FK_FIELDS = frozenset(
    {
        'cliente',
        'fornecedor',
        'transportadora',
        'pedido_venda',
        'pedido_compra',
        'faturamento',
        'nfe_saida',
        'alocacao_atendimento',
        'nfe_entrada',
        'cte_entrada',
    },
)

_SKIP_PAYLOAD_FIELDS = frozenset(
    {
        'codigo',
        'id',
        'criado_por',
        'atualizado_por',
        'criado_em',
        'atualizado_em',
    },
)


def _pk_opcional(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            pk = int(s)
        except ValueError:
            return None
        return pk if pk > 0 else None
    try:
        pk = int(v)
    except (TypeError, ValueError):
        return None
    return pk if pk > 0 else None


def _payload_para_campos(payload: dict[str, Any]) -> dict[str, Any]:
    """Mapeia FKs recebidas como PK (`cliente: 1`) para `cliente_id`."""
    campos: dict[str, Any] = {}
    for k, v in payload.items():
        if k in _SKIP_PAYLOAD_FIELDS:
            continue
        base = k[:-3] if k.endswith('_id') else k
        if base in _FK_FIELDS:
            campos[f'{base}_id'] = _pk_opcional(v)
            continue
        if hasattr(Expedicao, k):
            campos[k] = v
    return campos


def _aplicar_campos(expedicao: Expedicao, payload: dict[str, Any]) -> None:
    for k, v in _payload_para_campos(payload).items():
        setattr(expedicao, k, v)


def _tem_vinculo_operacional(dados: dict[str, Any]) -> bool:
    chaves = (
        'cliente',
        'cliente_id',
        'fornecedor',
        'fornecedor_id',
        'pedido_venda',
        'pedido_venda_id',
        'pedido_compra',
        'pedido_compra_id',
        'faturamento',
        'faturamento_id',
        'nfe_saida',
        'nfe_saida_id',
        'alocacao_atendimento',
        'alocacao_atendimento_id',
        'nfe_entrada',
        'nfe_entrada_id',
        'cte_entrada',
        'cte_entrada_id',
    )
    for k in chaves:
        if dados.get(k):
            return True
    return False


def validar_minimo_expedicao(dados: dict[str, Any]) -> None:
    tipo = str(dados.get('tipo_operacao') or '').strip()
    if not tipo:
        raise ExpedicaoErro('Informe o tipo de operação.')
    if tipo not in TipoOperacaoExpedicao.values:
        raise ExpedicaoErro('Tipo de operação inválido.')
    status = str(dados.get('status') or StatusExpedicao.RASCUNHO).strip()
    if status not in StatusExpedicao.values:
        raise ExpedicaoErro('Status inválido.')
    if not _tem_vinculo_operacional(dados):
        raise ExpedicaoErro(
            'Informe ao menos cliente, fornecedor ou um vínculo operacional (pedido, NF-e, faturamento, etc.).',
        )


def _nfe_autorizada(nfe: NFeSaida) -> bool:
    return bool(
        nfe.efeitos_autorizacao_aplicados_em
        or nfe.autorizada_em
        or nfe.xml_autorizado
        or nfe.protocolo_autorizacao
        or nfe.status_emissao_sefaz in {'AUTORIZADA_PRODUCAO', 'AUTORIZADA_HOMOLOGACAO'}
    )


def sincronizar_numeracao_nfe(expedicao: Expedicao) -> None:
    if not expedicao.nfe_saida_id:
        return
    nfe = NFeSaida.objects.select_for_update().get(pk=expedicao.nfe_saida_id)
    atual = (nfe.numeracao_volumes or '').strip()
    if _nfe_autorizada(nfe):
        # NF-e transmitida/autorizada é imutável: a Expedição somente mantém o vínculo.
        # O código EXP é operacional e não deve ser comparado nem gravado em numeracao_volumes.
        return
    if atual != expedicao.codigo:
        nfe.numeracao_volumes = expedicao.codigo
        nfe.save(update_fields=['numeracao_volumes'])


def _normalizar_payload(dados: dict[str, Any]) -> dict[str, Any]:
    out = dict(dados)
    if 'volumes' in out:
        out['volumes'] = _int_opcional(out.get('volumes'))
    for campo in ('peso_bruto', 'peso_liquido'):
        if campo in out:
            out[campo] = _dec_opcional(out.get(campo))
    return out


@transaction.atomic
def criar_expedicao(dados: dict[str, Any], *, usuario) -> Expedicao:
    payload = _normalizar_payload(dict(dados))
    validar_minimo_expedicao(payload)
    codigo = str(payload.pop('codigo', '') or '').strip() or gerar_codigo_expedicao()
    if Expedicao.objects.filter(codigo=codigo).exists():
        raise ExpedicaoErro(f'Código {codigo} já existe.')
    campos = _payload_para_campos(payload)
    exp = Expedicao.objects.create(
        codigo=codigo,
        criado_por=usuario,
        atualizado_por=usuario,
        **campos,
    )
    sincronizar_numeracao_nfe(exp)
    return exp


@transaction.atomic
def atualizar_expedicao(expedicao: Expedicao, dados: dict[str, Any], *, usuario) -> Expedicao:
    if expedicao.status == StatusExpedicao.CANCELADO:
        raise ExpedicaoErro('Expedição cancelada não pode ser editada.')
    payload = _normalizar_payload(dict(dados))
    merged: dict[str, Any] = {
        'tipo_operacao': payload.get('tipo_operacao', expedicao.tipo_operacao),
        'status': payload.get('status', expedicao.status),
        'cliente_id': payload.get('cliente_id', payload.get('cliente', expedicao.cliente_id)),
        'fornecedor_id': payload.get('fornecedor_id', payload.get('fornecedor', expedicao.fornecedor_id)),
        'pedido_venda_id': payload.get('pedido_venda_id', payload.get('pedido_venda', expedicao.pedido_venda_id)),
        'pedido_compra_id': payload.get('pedido_compra_id', payload.get('pedido_compra', expedicao.pedido_compra_id)),
        'faturamento_id': payload.get('faturamento_id', payload.get('faturamento', expedicao.faturamento_id)),
        'nfe_saida_id': payload.get('nfe_saida_id', payload.get('nfe_saida', expedicao.nfe_saida_id)),
        'alocacao_atendimento_id': payload.get(
            'alocacao_atendimento_id',
            payload.get('alocacao_atendimento', expedicao.alocacao_atendimento_id),
        ),
        'nfe_entrada_id': payload.get('nfe_entrada_id', payload.get('nfe_entrada', expedicao.nfe_entrada_id)),
        'cte_entrada_id': payload.get('cte_entrada_id', payload.get('cte_entrada', expedicao.cte_entrada_id)),
    }
    validar_minimo_expedicao(merged)
    _aplicar_campos(expedicao, payload)
    expedicao.atualizado_por = usuario
    expedicao.save()
    sincronizar_numeracao_nfe(expedicao)
    return expedicao


@transaction.atomic
def alterar_status_expedicao(
    expedicao: Expedicao,
    *,
    status: str,
    ocorrencia_descricao: str = '',
    usuario,
) -> Expedicao:
    novo = str(status or '').strip()
    if novo not in StatusExpedicao.values:
        raise ExpedicaoErro('Status inválido.')
    if expedicao.status == StatusExpedicao.CANCELADO:
        raise ExpedicaoErro('Expedição cancelada não pode ter status alterado.')
    expedicao.status = novo
    if novo == StatusExpedicao.OCORRENCIA and ocorrencia_descricao:
        expedicao.ocorrencia_descricao = ocorrencia_descricao.strip()
    elif ocorrencia_descricao:
        expedicao.ocorrencia_descricao = ocorrencia_descricao.strip()
    expedicao.atualizado_por = usuario
    expedicao.save(update_fields=['status', 'ocorrencia_descricao', 'atualizado_por', 'atualizado_em'])
    return expedicao


@transaction.atomic
def cancelar_expedicao(expedicao: Expedicao, *, motivo: str = '', usuario=None) -> Expedicao:
    if expedicao.status == StatusExpedicao.CANCELADO:
        return expedicao
    expedicao.status = StatusExpedicao.CANCELADO
    if motivo.strip():
        obs = (expedicao.observacoes or '').strip()
        linha = f'Cancelamento: {motivo.strip()}'
        expedicao.observacoes = f'{obs}\n{linha}'.strip() if obs else linha
    if usuario:
        expedicao.atualizado_por = usuario
    expedicao.save()
    return expedicao


def resumo_expedicoes_por_status() -> dict[str, int]:
    contagem = Expedicao.objects.values('status').annotate(total=Count('id'))
    por_status = {row['status']: row['total'] for row in contagem}
    return {
        'total': sum(por_status.values()),
        'aguardando_separacao': por_status.get(StatusExpedicao.AGUARDANDO_SEPARACAO, 0),
        'aguardando_retirada_fornecedor': por_status.get(StatusExpedicao.AGUARDANDO_RETIRADA_FORNECEDOR, 0),
        'motorista_enviado': por_status.get(StatusExpedicao.MOTORISTA_ENVIADO, 0),
        'em_transito': por_status.get(StatusExpedicao.EM_TRANSITO, 0),
        'entregue_cliente': por_status.get(StatusExpedicao.ENTREGUE_CLIENTE, 0),
        'ocorrencia': por_status.get(StatusExpedicao.OCORRENCIA, 0),
        'cancelado': por_status.get(StatusExpedicao.CANCELADO, 0),
        'por_status': por_status,
    }
