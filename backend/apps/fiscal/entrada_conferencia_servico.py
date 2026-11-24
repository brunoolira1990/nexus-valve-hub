"""Entrada operacional de NF-e histórica: leitura e registro explícito da chegada."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.fiscal.auditoria_entrada import registrar_conferencia_nfe
from apps.fiscal.models import NFeEntradaConferencia, NFeEntradaHistoricaImportada


def obter_conferencia(nf: NFeEntradaHistoricaImportada) -> NFeEntradaConferencia | None:
    return NFeEntradaConferencia.objects.filter(nf_entrada_historica_id=nf.pk).first()


def pode_registrar_chegada(conf: NFeEntradaConferencia | None) -> tuple[bool, str | None]:
    if conf is None:
        return True, None
    if conf.chegada_em is not None:
        return False, 'CHEGADA_JA_REGISTRADA'
    if (
        conf.status != NFeEntradaConferencia.Status.PENDENTE
        or conf.preparado_em is not None
        or conf.estoque_aplicado_em is not None
    ):
        return False, 'CHEGADA_NAO_REGISTRAVEL_PARA_CONFERENCIA_ANTIGA'
    return True, None


def completar_itens_faltantes(conf: NFeEntradaConferencia) -> None:
    for item_nf in conf.nf_entrada_historica.itens.all():
        prod = item_nf.prod_json or {}
        conf.itens.get_or_create(
            item_nfe_historico=item_nf,
            defaults={
                'unidade_nf': (prod.get('uCom') or prod.get('uTrib') or '').upper(),
                'quantidade_nf': Decimal(str(prod.get('qCom') or prod.get('qTrib') or 0)),
                'valor_unitario_nf': Decimal(str(prod.get('vUnCom') or prod.get('vUnTrib') or 0)),
                'valor_total_nf': Decimal(str(prod.get('vProd') or 0)),
            },
        )


@transaction.atomic
def iniciar_chegada(
    nf: NFeEntradaHistoricaImportada,
    usuario,
    local: str = '',
    observacao: str = '',
    pedido_compra_id: int | None = None,
    finalidade_entrada: str | None = None,
) -> NFeEntradaConferencia:
    nf = NFeEntradaHistoricaImportada.objects.select_for_update().get(pk=nf.pk)
    conf = obter_conferencia(nf)
    if conf is not None:
        conf = NFeEntradaConferencia.objects.select_for_update().get(pk=conf.pk)
    permitido, _ = pode_registrar_chegada(conf)
    if conf is not None and not permitido:
        return conf

    if conf is None:
        conf = NFeEntradaConferencia.objects.create(nf_entrada_historica=nf)
    completar_itens_faltantes(conf)

    conf.chegada_em = timezone.now()
    campos = ['chegada_em']
    if conf.recebido_por_id is None:
        conf.recebido_por = usuario
        campos.append('recebido_por')
    if conf.local_recebimento != local:
        conf.local_recebimento = local
        campos.append('local_recebimento')
    if conf.observacao_chegada != observacao:
        conf.observacao_chegada = observacao
        campos.append('observacao_chegada')
    if pedido_compra_id is not None and conf.pedido_compra_id != pedido_compra_id:
        conf.pedido_compra_id = pedido_compra_id
        campos.append('pedido_compra')
    if finalidade_entrada is not None and conf.finalidade_entrada != finalidade_entrada:
        conf.finalidade_entrada = finalidade_entrada
        campos.append('finalidade_entrada')
    conf.save(update_fields=[*campos, 'atualizado_em'])

    registrar_conferencia_nfe(
        entidade=conf,
        usuario=usuario,
        acao='chegada_iniciada',
        detalhes={
            'nfe_entrada_historica_id': nf.pk,
            'conferencia_id': conf.pk,
            'chegada_em': conf.chegada_em,
            'recebido_por_id': conf.recebido_por_id,
            'local_recebimento': conf.local_recebimento,
            'observacao_chegada': conf.observacao_chegada,
            'finalidade_entrada': conf.finalidade_entrada,
            'pedido_compra_id': conf.pedido_compra_id,
        },
    )
    return conf
