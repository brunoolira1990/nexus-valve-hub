from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from apps.comercial.models import Proposta
from apps.crm.models import Atividade
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.status import CENTAVO, calcular_status_titulo
from apps.fiscal.atendimento_estoque import montar_saldo_consolidado_produto
from apps.produtos.models import Produto

from .models import Notificacao
from .service import notificar_destinatarios, usuarios_destinatarios


STATUS_PROPOSTA_ENCERRADOS = frozenset(
    {
        'CANCELADA',
        'CANCELADO',
        'PERDIDA',
        'PERDIDO',
        'FECHADA',
        'FECHADO',
        'CONVERTIDA',
        'CONVERTIDO',
        'PEDIDO_GERADO',
    }
)


def _destinatarios_responsavel(responsavel, modulo: str):
    usuario = getattr(responsavel, 'usuario', None) if responsavel is not None else None
    if usuario is not None and getattr(usuario, 'is_active', False):
        return [usuario]
    return usuarios_destinatarios(modulo=modulo)


def notificar_atividade_vencida(atividade: Atividade, *, agora: datetime | None = None):
    agora = agora or timezone.now()
    if (
        atividade.status != Atividade.Status.PENDENTE
        or not atividade.agendada_para
        or atividade.agendada_para >= agora
    ):
        return []

    contexto = atividade.lead or atividade.oportunidade
    contexto_nome = getattr(contexto, 'nome', None) or getattr(contexto, 'titulo', None) or 'registro comercial'
    responsavel = getattr(atividade, 'responsavel', None)
    chave = f'crm:atividade-vencida:{atividade.pk}:{atividade.agendada_para.isoformat()}'
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.CRM,
        tipo=Notificacao.Tipo.ATIVIDADE_VENCIDA,
        titulo='Atividade CRM vencida',
        mensagem=f'A atividade "{atividade.titulo}" de {contexto_nome} está vencida.',
        destinatarios=_destinatarios_responsavel(responsavel, Notificacao.Modulo.CRM),
        url_destino='/crm/atividades',
        prioridade=Notificacao.Prioridade.ALTA,
        objeto_tipo='crm.atividade',
        objeto_id=atividade.pk,
        chave_idempotencia=chave,
    )


def notificar_titulo_vencido(titulo: TituloFinanceiro, *, hoje=None):
    hoje = hoje or timezone.localdate()
    status_calculado = calcular_status_titulo(
        tipo=titulo.tipo,
        valor_original=titulo.valor_original,
        valor_aberto=titulo.valor_aberto,
        valor_baixado=titulo.valor_baixado,
        data_vencimento=titulo.data_vencimento,
        cancelado=titulo.cancelado,
        hoje=hoje,
    )
    if status_calculado != TituloFinanceiro.Status.VENCIDO:
        return []

    responsavel = getattr(titulo, 'criado_por', None)
    destino = [responsavel] if responsavel is not None and getattr(responsavel, 'is_active', False) else usuarios_destinatarios(
        modulo=Notificacao.Modulo.FINANCEIRO,
    )
    chave = f'financeiro:titulo-vencido:{titulo.pk}:{hoje.isoformat()}'
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.FINANCEIRO,
        tipo=Notificacao.Tipo.TITULO_VENCIDO,
        titulo='Título financeiro vencido',
        mensagem=f'O título {titulo.numero} está vencido e possui saldo em aberto.',
        destinatarios=destino,
        url_destino='/financeiro/contas-pagar' if titulo.tipo == TituloFinanceiro.Tipo.PAGAR else '/financeiro/contas-receber',
        prioridade=Notificacao.Prioridade.CRITICA if titulo.tipo == TituloFinanceiro.Tipo.PAGAR else Notificacao.Prioridade.ALTA,
        objeto_tipo='financeiro.titulo',
        objeto_id=titulo.pk,
        chave_idempotencia=chave,
    )


def notificar_estoque_minimo(produto: Produto, *, saldo_disponivel: Decimal):
    estoque_minimo = Decimal(str(produto.estoque_minimo or 0))
    if estoque_minimo <= 0 or saldo_disponivel >= estoque_minimo:
        return []

    hoje = timezone.localdate()
    chave = f'estoque:abaixo-minimo:{produto.pk}:{hoje.isoformat()}'
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.ESTOQUE,
        tipo=Notificacao.Tipo.ESTOQUE_MINIMO,
        titulo='Estoque abaixo do mínimo',
        mensagem=f'O produto {produto.codigo_completo or produto.descricao} está abaixo do estoque mínimo configurado.',
        destinatarios=usuarios_destinatarios(modulo=Notificacao.Modulo.ESTOQUE),
        url_destino='/estoque',
        prioridade=Notificacao.Prioridade.ALTA,
        objeto_tipo='produtos.produto',
        objeto_id=produto.pk,
        chave_idempotencia=chave,
    )


def notificar_proposta_aguardando_acao(proposta: Proposta):
    status = (proposta.status or '').strip().upper()
    if status in STATUS_PROPOSTA_ENCERRADOS:
        return []

    vendedor = getattr(proposta, 'vendedor_ref', None)
    destino = _destinatarios_responsavel(
        getattr(vendedor, 'colaborador', None) if vendedor is not None else None,
        Notificacao.Modulo.COMERCIAL,
    )
    usuario_vendedor = getattr(vendedor, 'usuario', None) if vendedor is not None else None
    if usuario_vendedor is not None and getattr(usuario_vendedor, 'is_active', False):
        destino = [usuario_vendedor]

    chave = f'comercial:proposta-acao:{proposta.pk}:{status or "SEM_STATUS"}'
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.COMERCIAL,
        tipo=Notificacao.Tipo.PROPOSTA_ACAO,
        titulo='Proposta aguardando ação',
        mensagem=f'A proposta {proposta.numero} está disponível para acompanhamento comercial.',
        destinatarios=destino,
        url_destino='/propostas',
        prioridade=Notificacao.Prioridade.NORMAL,
        objeto_tipo='comercial.proposta',
        objeto_id=proposta.pk,
        chave_idempotencia=chave,
    )


def gerar_notificacoes_pendentes(*, agora: datetime | None = None) -> dict[str, int]:
    """Varre pendências determinísticas; adequado para execução periódica externa."""
    agora = agora or timezone.now()
    criadas = {
        'atividades': 0,
        'titulos': 0,
        'estoque': 0,
    }

    atividades = Atividade.objects.select_related('lead', 'oportunidade', 'responsavel__usuario').filter(
        status=Atividade.Status.PENDENTE,
        agendada_para__lt=agora,
    )
    for atividade in atividades.iterator():
        criadas['atividades'] += len(notificar_atividade_vencida(atividade, agora=agora))

    titulos = TituloFinanceiro.objects.select_related('criado_por').filter(
        cancelado=False,
        data_vencimento__lt=agora.date(),
        valor_aberto__gt=CENTAVO,
    )
    for titulo in titulos.iterator():
        criadas['titulos'] += len(notificar_titulo_vencido(titulo, hoje=agora.date()))

    produtos = Produto.objects.filter(estoque_minimo__gt=0).only(
        'id',
        'codigo_completo',
        'descricao',
        'estoque_minimo',
    )
    for produto in produtos.iterator():
        saldo = montar_saldo_consolidado_produto(produto)
        saldo_disponivel = Decimal(str(saldo.get('saldo_disponivel') or 0))
        criadas['estoque'] += len(notificar_estoque_minimo(produto, saldo_disponivel=saldo_disponivel))

    return criadas
