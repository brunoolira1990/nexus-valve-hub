from __future__ import annotations

from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.cadastros.models import Colaborador

from .models import Notificacao


AREA_FLAG = {
    Notificacao.Modulo.COMERCIAL: 'eh_vendedor',
    Notificacao.Modulo.FISCAL: 'eh_responsavel_fiscal',
    Notificacao.Modulo.FINANCEIRO: 'eh_responsavel_financeiro',
    Notificacao.Modulo.ESTOQUE: 'eh_responsavel_estoque',
    Notificacao.Modulo.QUALIDADE: 'eh_responsavel_qualidade',
    Notificacao.Modulo.COMPRAS: 'eh_comprador',
    Notificacao.Modulo.CRM: 'eh_vendedor',
}


def _usuario_ativo(usuario) -> bool:
    return bool(usuario and getattr(usuario, 'is_active', True))


def usuarios_destinatarios(*, modulo: str, colaborador: Colaborador | None = None):
    """Retorna usuários ativos elegíveis para um evento do módulo informado.

    Um responsável explícito recebe a notificação individualmente. Sem responsável,
    usa a flag de área dos colaboradores vinculados e inclui staff/superusers como
    contingência operacional para que o evento não desapareça sem destinatário.
    """
    User = get_user_model()

    if colaborador is not None:
        usuario = getattr(colaborador, 'usuario', None)
        if _usuario_ativo(usuario):
            return User.objects.filter(pk=usuario.pk, is_active=True)

    flag = AREA_FLAG.get(modulo)
    qs = User.objects.filter(is_active=True)
    if flag:
        qs = qs.filter(
            Q(colaborador_vinculado__ativo=True, **{f'colaborador_vinculado__{flag}': True})
            | Q(is_staff=True)
            | Q(is_superuser=True)
        )
    else:
        qs = qs.filter(Q(is_staff=True) | Q(is_superuser=True))
    return qs.distinct()


def criar_notificacao(
    *,
    destinatario,
    modulo: str,
    tipo: str,
    titulo: str,
    mensagem: str,
    url_destino: str = '',
    prioridade: str = Notificacao.Prioridade.NORMAL,
    objeto_tipo: str = '',
    objeto_id: str | int | None = None,
    chave_idempotencia: str = '',
) -> tuple[Notificacao | None, bool]:
    """Cria uma notificação sem duplicar o mesmo evento para o mesmo usuário."""
    if not _usuario_ativo(destinatario):
        return None, False

    defaults = {
        'modulo': modulo,
        'tipo': tipo,
        'prioridade': prioridade,
        'titulo': titulo,
        'mensagem': mensagem,
        'url_destino': url_destino or '',
        'objeto_tipo': objeto_tipo or '',
        'objeto_id': '' if objeto_id is None else str(objeto_id),
    }

    if not chave_idempotencia:
        return Notificacao.objects.create(
            destinatario=destinatario,
            chave_idempotencia='',
            **defaults,
        ), True

    try:
        with transaction.atomic():
            notificacao, criada = Notificacao.objects.get_or_create(
                destinatario=destinatario,
                chave_idempotencia=chave_idempotencia,
                defaults=defaults,
            )
    except IntegrityError:
        notificacao = Notificacao.objects.get(
            destinatario=destinatario,
            chave_idempotencia=chave_idempotencia,
        )
        criada = False
    return notificacao, criada


def notificar_destinatarios(
    *,
    modulo: str,
    tipo: str,
    titulo: str,
    mensagem: str,
    destinatarios: Iterable,
    url_destino: str = '',
    prioridade: str = Notificacao.Prioridade.NORMAL,
    objeto_tipo: str = '',
    objeto_id: str | int | None = None,
    chave_idempotencia: str = '',
) -> list[Notificacao]:
    """Cria a mesma notificação para vários usuários, retornando apenas criações."""
    criadas = []
    for destinatario in destinatarios:
        chave_usuario = f'{chave_idempotencia}:user:{destinatario.pk}' if chave_idempotencia else ''
        notificacao, criada = criar_notificacao(
            destinatario=destinatario,
            modulo=modulo,
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            url_destino=url_destino,
            prioridade=prioridade,
            objeto_tipo=objeto_tipo,
            objeto_id=objeto_id,
            chave_idempotencia=chave_usuario,
        )
        if criada and notificacao is not None:
            criadas.append(notificacao)
    return criadas


def marcar_como_lida(notificacao: Notificacao) -> Notificacao:
    if not notificacao.lida:
        notificacao.lida = True
        notificacao.lida_em = timezone.now()
        notificacao.save(update_fields=['lida', 'lida_em'])
    return notificacao


def arquivar(notificacao: Notificacao) -> Notificacao:
    if not notificacao.arquivada:
        notificacao.arquivada = True
        notificacao.arquivada_em = timezone.now()
        notificacao.save(update_fields=['arquivada', 'arquivada_em'])
    return notificacao
