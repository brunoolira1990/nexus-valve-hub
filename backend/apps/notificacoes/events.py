from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib

from django.db.models import QuerySet
from django.utils import timezone

from apps.comercial.models import Proposta
from apps.crm.models import Atividade
from apps.financeiro.models import TituloFinanceiro
from apps.financeiro.status import CENTAVO, calcular_status_titulo
from apps.fiscal.atendimento_estoque import montar_saldo_consolidado_produto
from apps.fiscal.central_dfe.service import (
    FiltrosCentralDfe,
    DocumentoCentralDfe,
    coletar_documentos_central_dfe,
)
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


def notificar_falha_captura_dfe(empresa_id: int, resultado: dict):
    """Avisa o setor Fiscal quando a captura não consegue consultar a SEFAZ."""
    erros = [str(item).strip() for item in (resultado.get('erros') or []) if str(item).strip()]
    if not erros:
        return []

    from apps.cadastros.models import Empresa

    empresa = Empresa.objects.filter(pk=empresa_id).only('id', 'razao_social').first()
    if empresa is None:
        return []

    detalhe = '; '.join(erros)[:900]
    assinatura = hashlib.sha256(detalhe.encode('utf-8')).hexdigest()[:24]
    tipos = ', '.join(str(item) for item in (resultado.get('tipos_processados') or [])) or 'NFE/CTE'
    chave = f'fiscal:dfe:falha:{empresa_id}:{tipos}:{assinatura}'
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.FISCAL,
        tipo=Notificacao.Tipo.FALHA_CAPTURA_FISCAL,
        titulo='Falha na captura de documentos fiscais',
        mensagem=(
            f'A consulta de {tipos} da empresa {empresa.razao_social or empresa.pk} não foi concluída. '
            f'Detalhes: {detalhe}'
        )[:1800],
        destinatarios=usuarios_destinatarios(modulo=Notificacao.Modulo.FISCAL),
        url_destino='/central-dfe',
        prioridade=Notificacao.Prioridade.CRITICA,
        objeto_tipo='fiscal.captura_dfe',
        objeto_id=empresa_id,
        chave_idempotencia=chave,
    )


def notificar_pendencia_captura_dfe(empresa_id: int, resultado: dict):
    """Avisa quando a SEFAZ informa NSU pendente ou interrupção por limite/consumo."""
    if not (
        resultado.get('ainda_tem_nsu_pendente')
        or resultado.get('parou_por_limite_lotes')
        or resultado.get('bloqueado_consumo_indevido')
    ):
        return []

    from apps.cadastros.models import Empresa

    empresa = Empresa.objects.filter(pk=empresa_id).only('id', 'razao_social').first()
    if empresa is None:
        return []

    avisos = [str(item).strip() for item in (resultado.get('avisos') or []) if str(item).strip()]
    motivo = '; '.join(avisos)[:900] or 'Ainda existem documentos fiscais pendentes de processamento.'
    nsu = resultado.get('nsu_por_tipo') or {}
    assinatura = hashlib.sha256(repr(sorted(nsu.items())).encode('utf-8')).hexdigest()[:24]
    chave = f'fiscal:dfe:pendencia:{empresa_id}:{assinatura}'
    prioridade = (
        Notificacao.Prioridade.CRITICA
        if resultado.get('bloqueado_consumo_indevido')
        else Notificacao.Prioridade.ALTA
    )
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.FISCAL,
        tipo=Notificacao.Tipo.PENDENCIA_FISCAL,
        titulo='Documentos fiscais aguardando captura',
        mensagem=(
            f'A empresa {empresa.razao_social or empresa.pk} ainda possui documentos pendentes na SEFAZ. '
            f'{motivo}'
        )[:1800],
        destinatarios=usuarios_destinatarios(modulo=Notificacao.Modulo.FISCAL),
        url_destino='/central-dfe',
        prioridade=prioridade,
        objeto_tipo='fiscal.captura_dfe',
        objeto_id=empresa_id,
        chave_idempotencia=chave,
    )


def notificar_documento_central_dfe(documento: DocumentoCentralDfe):
    """Cria alerta para documento fiscal pendente, sem executar efeito fiscal."""
    destinatarios = usuarios_destinatarios(modulo=Notificacao.Modulo.FISCAL)
    if not destinatarios or not documento.chave_acesso:
        return []

    tipo_label = documento.tipo_label or documento.tipo_documento
    emitente = documento.emitente_nome or 'emitente não identificado'
    numero = documento.numero or 'sem número'
    serie = f' série {documento.serie}' if documento.serie else ''
    status = documento.status_entrada_label or 'Pendente de análise'
    estado = documento.estado_consolidado_label
    complemento = f' Estado: {estado}.' if estado else ''
    prioridade = Notificacao.Prioridade.ALTA
    if documento.estado_consolidado in {'DIVERGENTE', 'CANCELADO', 'ERRO'}:
        prioridade = Notificacao.Prioridade.CRITICA

    chave = ':'.join(
        [
            'fiscal:dfe',
            str(documento.empresa_id or 0),
            documento.tipo_documento,
            documento.chave_acesso,
            documento.status_entrada or 'SEM_STATUS',
            documento.estado_consolidado or 'SEM_ESTADO',
        ],
    )
    return notificar_destinatarios(
        modulo=Notificacao.Modulo.FISCAL,
        tipo=Notificacao.Tipo.DOCUMENTO_FISCAL,
        titulo=f'{tipo_label} aguardando análise',
        mensagem=(
            f'{tipo_label} emitido por {emitente}, número {numero}{serie}. '
            f'Status: {status}.{complemento}'
        ),
        destinatarios=destinatarios,
        url_destino=documento.detalhe_rota or '/central-dfe',
        prioridade=prioridade,
        objeto_tipo=f'fiscal.{documento.tipo_documento.lower()}',
        objeto_id=documento.chave_acesso,
        chave_idempotencia=chave,
    )


def notificar_documentos_central_dfe(empresa_id: int) -> int:
    """Varre somente a fila pendente da Central DFe e notifica cada documento uma vez por estado."""
    from apps.cadastros.models import Empresa

    empresa = Empresa.objects.filter(pk=empresa_id).first()
    if empresa is None:
        return 0
    filtros = FiltrosCentralDfe(empresa_id=empresa.pk, incluir_tratados=False, ordering='-data_importacao')
    documentos = coletar_documentos_central_dfe(filtros, empresa=empresa)
    return sum(len(notificar_documento_central_dfe(documento)) for documento in documentos)


def gerar_notificacoes_pendentes(*, agora: datetime | None = None) -> dict[str, int]:
    """Varre pendências determinísticas; adequado para execução periódica externa."""
    agora = agora or timezone.now()
    criadas = {
        'atividades': 0,
        'titulos': 0,
        'estoque': 0,
        'fiscal': 0,
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

    from apps.cadastros.models import Empresa

    for empresa_id in Empresa.objects.values_list('id', flat=True).iterator():
        criadas['fiscal'] += notificar_documentos_central_dfe(empresa_id)

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
