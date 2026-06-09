"""Fase Saída 3.9 — homologação assistida de proposta com cenário fiscal de saída."""

from __future__ import annotations

from typing import Any, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.comercial.models import HomologacaoFiscalPropostaEvento, ItemProposta, PedidoVenda, Proposta
from apps.regras_fiscais.cenario_fiscal_saida import NOME_CENARIO_PADRAO_SAIDA
from apps.regras_fiscais.models import CenarioFiscalSaida
from apps.regras_fiscais.saida_fiscal import (
    _contexto_fiscal_de_item_proposta,
    comparar_regra_fiscal_saida_legado_cenario,
    find_regra_fiscal_saida_com_fallback,
    mensagem_origem_fiscal_saida,
    resolve_usar_cenario_fiscal_para_proposta,
)


class ItemHomologacaoFiscalDict(TypedDict):
    item_id: int
    produto_codigo: str
    produto_descricao: str
    ncm: str
    origem_oficial: str
    comparativo_status: str
    divergencias: list[dict[str, Any]]
    legado: dict[str, Any]
    cenario: dict[str, Any]
    regra_fiscal_saida_id: int | None
    regra_fiscal_legada_id: int | None
    mensagem_regra_fiscal_saida: str
    deduzir_icms_base_pis: bool
    deduzir_icms_base_cofins: bool
    tem_reforma_configurada: bool
    tem_recomendacoes_nfe: bool
    ignorado_sem_contexto: bool


class ResumoHomologacaoFiscalDict(TypedDict):
    total_itens: int
    iguais: int
    divergentes: int
    cenario_nao_encontrado: int
    legado_nao_encontrado: int
    ambos_nao_encontrados: int
    itens_ignorados_sem_contexto: int
    itens_com_deducao_icms_base_pis_cofins: int
    itens_com_reforma_configurada: int
    itens_com_recomendacoes_nfe: int


class UltimoEventoHomologacaoDict(TypedDict):
    id: int
    tipo_evento: str
    status_resultante: str
    criado_em: str
    criado_por_nome: str


class HomologacaoFiscalPropostaDict(TypedDict):
    status: str
    observacao: str
    homologacao_fiscal_em: str | None
    usar_cenario_fiscal_saida: bool
    cenario_fiscal_saida_id: int | None
    resumo: ResumoHomologacaoFiscalDict
    itens: list[ItemHomologacaoFiscalDict]
    total_eventos_homologacao: int
    ultimo_evento_homologacao: UltimoEventoHomologacaoDict | None


class HistoricoHomologacaoFiscalDict(TypedDict):
    proposta_id: int
    eventos: list[dict[str, Any]]


def proposta_permite_alterar_calculo_homologacao(proposta: Proposta) -> tuple[bool, str]:
    if PedidoVenda.objects.filter(proposta_id=proposta.pk).exists():
        return False, 'Proposta já convertida em pedido de venda; homologação que altera cálculo não é permitida.'
    status = (proposta.status or '').strip().lower()
    if status in ('rejeitada', 'cancelada', 'cancelado'):
        return False, f'Proposta com status «{proposta.status}» não permite alteração de cálculo fiscal.'
    return True, ''


def _cenario_id_proposta(proposta: Proposta, cenario_id: int | None = None) -> int | None:
    if cenario_id:
        return cenario_id
    return proposta.cenario_fiscal_saida_id


def _item_payload_para_recalc(item: ItemProposta) -> dict[str, Any]:
    return {
        'produto_id': item.produto_id,
        'descricao_avulsa': item.descricao_avulsa,
        'ncm_avulso': item.ncm_avulso,
        'quantidade': item.quantidade,
        'unidade_negociada': item.unidade_negociada,
        'quantidade_negociada': item.quantidade_negociada,
        'valor_unitario': item.valor_unitario,
        'preco_por_unidade_negociada': item.preco_por_unidade_negociada,
        'desconto': item.desconto,
        'custo_utilizado': item.custo_utilizado,
        'frete': item.frete,
        'despesas': item.despesas,
        'ipi_entrada_percentual': item.ipi_entrada_percentual,
        'ipi_custo': item.ipi_custo,
        'st_custo': item.st_custo,
        'outros_impostos_custo': item.outros_impostos_custo,
        'irpj_estimado_percentual': item.irpj_estimado_percentual,
        'csll_estimada_percentual': item.csll_estimada_percentual,
        'comissao_percentual': item.comissao_percentual,
        'frete_saida': item.frete_saida,
        'outras_despesas_saida': item.outras_despesas_saida,
        'modo_preco': item.modo_preco,
        'preco_final': item.preco_final,
    }


def recalcular_itens_fiscais_proposta(proposta: Proposta) -> None:
    from apps.comercial.serializers import ItemPropostaSerializer, recalcular_proposta

    incoming = {
        'usar_cenario_fiscal_saida': proposta.usar_cenario_fiscal_saida,
        'cenario_fiscal_saida_id': proposta.cenario_fiscal_saida_id,
        'empresa_emitente_id': proposta.empresa_emitente_id,
        'cliente_id': proposta.cliente_id,
        'uf_destino_avulso': proposta.uf_destino_avulso,
        'operacao_fiscal': proposta.operacao_fiscal,
    }
    ctx = {'proposta_incoming': incoming}
    for item in proposta.itens.select_related('produto').all():
        ser = ItemPropostaSerializer(
            item,
            data=_item_payload_para_recalc(item),
            partial=True,
            context=ctx,
        )
        ser.is_valid(raise_exception=True)
        ser.save()
    recalcular_proposta(proposta)


def _origem_oficial_item(proposta: Proposta, ctx: dict[str, Any]) -> dict[str, Any]:
    cid = _cenario_id_proposta(proposta)
    usar = resolve_usar_cenario_fiscal_para_proposta(proposta)
    return find_regra_fiscal_saida_com_fallback(
        ctx['ncm'],
        ctx['uf_origem'],
        ctx['uf_destino'],
        'Saída',
        produto_id=ctx.get('produto_id'),
        usar_cenario=usar,
        cenario_id=cid,
    )


def _montar_item_homologacao(item: ItemProposta, proposta: Proposta) -> ItemHomologacaoFiscalDict:
    ctx = _contexto_fiscal_de_item_proposta(item)
    prod = item.produto
    codigo = ''
    descricao = (item.descricao_avulsa or '').strip()
    if prod is not None:
        codigo = (prod.codigo_completo or '').strip()
        descricao = (prod.descricao or descricao).strip()

    if ctx is None:
        return {
            'item_id': item.pk,
            'produto_codigo': codigo,
            'produto_descricao': descricao,
            'ncm': '',
            'origem_oficial': 'NAO_ENCONTRADA',
            'comparativo_status': 'AMBOS_NAO_ENCONTRADOS',
            'divergencias': [],
            'legado': {},
            'cenario': {},
            'regra_fiscal_saida_id': None,
            'regra_fiscal_legada_id': None,
            'mensagem_regra_fiscal_saida': mensagem_origem_fiscal_saida('NAO_ENCONTRADA'),
            'deduzir_icms_base_pis': False,
            'deduzir_icms_base_cofins': False,
            'tem_reforma_configurada': False,
            'tem_recomendacoes_nfe': False,
            'ignorado_sem_contexto': True,
        }

    cid = _cenario_id_proposta(proposta)
    if cid:
        ctx['cenario_id'] = cid

    cmp = comparar_regra_fiscal_saida_legado_cenario(**ctx)
    busca = _origem_oficial_item(proposta, ctx)

    return {
        'item_id': item.pk,
        'produto_codigo': codigo,
        'produto_descricao': descricao,
        'ncm': ctx['ncm'],
        'origem_oficial': busca['origem'],
        'comparativo_status': cmp['status'],
        'divergencias': cmp['divergencias'],
        'legado': cmp['legado'],
        'cenario': cmp['cenario'],
        'regra_fiscal_saida_id': busca.get('regra_id'),
        'regra_fiscal_legada_id': busca.get('regra_legada_id'),
        'mensagem_regra_fiscal_saida': mensagem_origem_fiscal_saida(busca['origem']),
        'deduzir_icms_base_pis': bool(busca.get('deduzir_icms_base_pis')),
        'deduzir_icms_base_cofins': bool(busca.get('deduzir_icms_base_cofins')),
        'tem_reforma_configurada': bool(busca.get('tem_reforma_configurada')),
        'tem_recomendacoes_nfe': bool(busca.get('tem_recomendacoes_nfe')),
        'ignorado_sem_contexto': False,
    }


def _montar_resumo_homologacao(itens: list[ItemHomologacaoFiscalDict]) -> ResumoHomologacaoFiscalDict:
    analisaveis = [i for i in itens if not i['ignorado_sem_contexto']]
    iguais = sum(1 for i in analisaveis if i['comparativo_status'] == 'IGUAL')
    divergentes = sum(1 for i in analisaveis if i['comparativo_status'] == 'DIVERGENTE')
    cenario_nao = sum(1 for i in analisaveis if i['comparativo_status'] == 'CENARIO_NAO_ENCONTRADO')
    legado_nao = sum(1 for i in analisaveis if i['comparativo_status'] == 'LEGADO_NAO_ENCONTRADO')
    ambos_nao = sum(1 for i in analisaveis if i['comparativo_status'] == 'AMBOS_NAO_ENCONTRADOS')
    deducao = sum(
        1
        for i in analisaveis
        if i['deduzir_icms_base_pis'] or i['deduzir_icms_base_cofins']
    )
    reforma = sum(1 for i in analisaveis if i['tem_reforma_configurada'])
    recom = sum(1 for i in analisaveis if i['tem_recomendacoes_nfe'])
    ignorados = sum(1 for i in itens if i['ignorado_sem_contexto'])
    return {
        'total_itens': len(itens),
        'iguais': iguais,
        'divergentes': divergentes,
        'cenario_nao_encontrado': cenario_nao,
        'legado_nao_encontrado': legado_nao,
        'ambos_nao_encontrados': ambos_nao,
        'itens_ignorados_sem_contexto': ignorados,
        'itens_com_deducao_icms_base_pis_cofins': deducao,
        'itens_com_reforma_configurada': reforma,
        'itens_com_recomendacoes_nfe': recom,
    }


def _nome_cenario_snapshot(proposta: Proposta) -> str:
    if proposta.cenario_fiscal_saida_id and proposta.cenario_fiscal_saida:
        return (proposta.cenario_fiscal_saida.nome or '').strip()
    if proposta.usar_cenario_fiscal_saida:
        return NOME_CENARIO_PADRAO_SAIDA
    return ''


def _nome_usuario(usuario) -> str:
    if usuario is None:
        return ''
    if not getattr(usuario, 'is_authenticated', False):
        return ''
    nome = (getattr(usuario, 'get_full_name', lambda: '')() or '').strip()
    return nome or (getattr(usuario, 'username', '') or '').strip()


def _meta_eventos_homologacao(proposta: Proposta) -> tuple[int, UltimoEventoHomologacaoDict | None]:
    qs = HomologacaoFiscalPropostaEvento.objects.filter(proposta_id=proposta.pk).select_related('criado_por')
    total = qs.count()
    ultimo = qs.first()
    if ultimo is None:
        return total, None
    return total, {
        'id': ultimo.pk,
        'tipo_evento': ultimo.tipo_evento,
        'status_resultante': ultimo.status_resultante,
        'criado_em': ultimo.criado_em.isoformat(),
        'criado_por_nome': _nome_usuario(ultimo.criado_por),
    }


def registrar_evento_homologacao_fiscal(
    proposta: Proposta,
    tipo_evento: str,
    *,
    usuario=None,
    observacao: str = '',
    resumo: dict[str, Any] | None = None,
    itens: list[dict[str, Any]] | None = None,
    payload: HomologacaoFiscalPropostaDict | None = None,
) -> HomologacaoFiscalPropostaEvento:
    """Persiste snapshot de auditoria; não altera estado vigente da proposta."""
    if payload is not None:
        resumo = payload.get('resumo')
        itens = payload.get('itens')
        status_resultante = payload['status']
        usar_cenario = bool(payload['usar_cenario_fiscal_saida'])
        cenario_id = payload.get('cenario_fiscal_saida_id')
    else:
        status_resultante = proposta.homologacao_fiscal_status
        usar_cenario = bool(proposta.usar_cenario_fiscal_saida)
        cenario_id = proposta.cenario_fiscal_saida_id

    proposta.refresh_from_db()
    if proposta.cenario_fiscal_saida_id:
        proposta = Proposta.objects.select_related('cenario_fiscal_saida').get(pk=proposta.pk)

    nome_cenario = _nome_cenario_snapshot(proposta)
    if not nome_cenario and cenario_id:
        row = CenarioFiscalSaida.objects.filter(pk=cenario_id).values_list('nome', flat=True).first()
        nome_cenario = (row or '').strip()

    return HomologacaoFiscalPropostaEvento.objects.create(
        proposta_id=proposta.pk,
        tipo_evento=tipo_evento,
        status_resultante=status_resultante,
        usar_cenario_fiscal_saida=usar_cenario,
        cenario_fiscal_saida_id=cenario_id,
        cenario_fiscal_saida_nome=nome_cenario,
        resumo=resumo,
        itens=itens,
        observacao=(observacao or '').strip(),
        criado_por=usuario if getattr(usuario, 'is_authenticated', False) else None,
    )


def montar_homologacao_fiscal_proposta(proposta: Proposta) -> HomologacaoFiscalPropostaDict:
    itens_qs = proposta.itens.select_related('produto', 'proposta__cliente', 'proposta__empresa_emitente')
    itens_rows = [_montar_item_homologacao(item, proposta) for item in itens_qs]
    resumo = _montar_resumo_homologacao(itens_rows)
    em = proposta.homologacao_fiscal_em
    total_evt, ultimo_evt = _meta_eventos_homologacao(proposta)
    return {
        'status': proposta.homologacao_fiscal_status,
        'observacao': proposta.homologacao_fiscal_observacao or '',
        'homologacao_fiscal_em': em.isoformat() if em else None,
        'usar_cenario_fiscal_saida': bool(proposta.usar_cenario_fiscal_saida),
        'cenario_fiscal_saida_id': proposta.cenario_fiscal_saida_id,
        'resumo': resumo,
        'itens': itens_rows,
        'total_eventos_homologacao': total_evt,
        'ultimo_evento_homologacao': ultimo_evt,
    }


def listar_historico_homologacao_fiscal(proposta: Proposta) -> HistoricoHomologacaoFiscalDict:
    from apps.comercial.serializers import HomologacaoFiscalPropostaEventoSerializer

    eventos = (
        HomologacaoFiscalPropostaEvento.objects.filter(proposta_id=proposta.pk)
        .select_related('criado_por', 'cenario_fiscal_saida')
        .order_by('-criado_em', '-id')
    )
    ser = HomologacaoFiscalPropostaEventoSerializer(eventos, many=True)
    return {'proposta_id': proposta.pk, 'eventos': ser.data}


def _persistir_homologacao(
    proposta: Proposta,
    *,
    status: str,
    observacao: str | None = None,
    resumo: dict[str, Any] | None = None,
    usar_cenario: bool | None = None,
    cenario_id: int | None = None,
    recalcular: bool = False,
) -> HomologacaoFiscalPropostaDict:
    update_fields = ['homologacao_fiscal_status', 'homologacao_fiscal_em', 'homologacao_fiscal_observacao']
    proposta.homologacao_fiscal_status = status
    proposta.homologacao_fiscal_em = timezone.now()
    if observacao is not None:
        proposta.homologacao_fiscal_observacao = (observacao or '').strip()
        update_fields.append('homologacao_fiscal_observacao')
    if usar_cenario is not None:
        proposta.usar_cenario_fiscal_saida = usar_cenario
        update_fields.append('usar_cenario_fiscal_saida')
    if cenario_id is not None:
        proposta.cenario_fiscal_saida_id = cenario_id
        update_fields.append('cenario_fiscal_saida')
    if recalcular:
        recalcular_itens_fiscais_proposta(proposta)
    payload = montar_homologacao_fiscal_proposta(proposta)
    proposta.homologacao_fiscal_resumo = payload['resumo']
    update_fields.append('homologacao_fiscal_resumo')
    proposta.save(update_fields=list(dict.fromkeys(update_fields)))
    return payload


def _registrar_apos_acao(
    proposta: Proposta,
    tipo_evento: str,
    payload: HomologacaoFiscalPropostaDict,
    *,
    usuario=None,
    observacao: str = '',
) -> None:
    registrar_evento_homologacao_fiscal(
        proposta,
        tipo_evento,
        usuario=usuario,
        observacao=observacao,
        payload=payload,
    )


@transaction.atomic
def iniciar_homologacao_cenario_fiscal(
    proposta: Proposta,
    *,
    cenario_fiscal_saida_id: int | None = None,
    observacao: str = '',
    usuario=None,
) -> HomologacaoFiscalPropostaDict:
    ok, msg = proposta_permite_alterar_calculo_homologacao(proposta)
    if not ok:
        raise ValueError(msg)

    if cenario_fiscal_saida_id:
        if not CenarioFiscalSaida.objects.filter(pk=cenario_fiscal_saida_id, ativo=True).exists():
            raise ValueError('Cenário fiscal de saída inválido ou inativo.')

    cenario_antes = proposta.cenario_fiscal_saida_id
    cid = cenario_fiscal_saida_id or proposta.cenario_fiscal_saida_id
    payload = _persistir_homologacao(
        proposta,
        status=Proposta.HomologacaoFiscalStatus.EM_ANALISE,
        observacao=observacao,
        usar_cenario=True,
        cenario_id=cid,
        recalcular=True,
    )
    _registrar_apos_acao(
        proposta,
        HomologacaoFiscalPropostaEvento.TipoEvento.INICIADA,
        payload,
        usuario=usuario,
        observacao=observacao,
    )
    if cid and cid != cenario_antes:
        _registrar_apos_acao(
            proposta,
            HomologacaoFiscalPropostaEvento.TipoEvento.ALTEROU_CENARIO,
            payload,
            usuario=usuario,
            observacao=observacao or f'Cenário fiscal id={cid}',
        )
    payload['total_eventos_homologacao'], payload['ultimo_evento_homologacao'] = _meta_eventos_homologacao(proposta)
    return payload


@transaction.atomic
def recalcular_homologacao_cenario_fiscal(proposta: Proposta, *, usuario=None) -> HomologacaoFiscalPropostaDict:
    if proposta.homologacao_fiscal_status != Proposta.HomologacaoFiscalStatus.EM_ANALISE:
        raise ValueError('Homologação fiscal não está em análise.')
    ok, msg = proposta_permite_alterar_calculo_homologacao(proposta)
    if not ok:
        raise ValueError(msg)
    if not proposta.usar_cenario_fiscal_saida:
        proposta.usar_cenario_fiscal_saida = True
        proposta.save(update_fields=['usar_cenario_fiscal_saida'])
    payload = _persistir_homologacao(
        proposta,
        status=Proposta.HomologacaoFiscalStatus.EM_ANALISE,
        recalcular=True,
    )
    _registrar_apos_acao(
        proposta,
        HomologacaoFiscalPropostaEvento.TipoEvento.RECALCULADA,
        payload,
        usuario=usuario,
    )
    payload['total_eventos_homologacao'], payload['ultimo_evento_homologacao'] = _meta_eventos_homologacao(proposta)
    return payload


@transaction.atomic
def aprovar_homologacao_cenario_fiscal(
    proposta: Proposta,
    *,
    observacao: str = '',
    usuario=None,
) -> HomologacaoFiscalPropostaDict:
    if proposta.homologacao_fiscal_status not in (
        Proposta.HomologacaoFiscalStatus.EM_ANALISE,
        Proposta.HomologacaoFiscalStatus.REPROVADA,
    ):
        raise ValueError('Homologação fiscal deve estar em análise para aprovação.')
    payload = _persistir_homologacao(
        proposta,
        status=Proposta.HomologacaoFiscalStatus.APROVADA,
        observacao=observacao,
        usar_cenario=True,
        recalcular=False,
    )
    _registrar_apos_acao(
        proposta,
        HomologacaoFiscalPropostaEvento.TipoEvento.APROVADA,
        payload,
        usuario=usuario,
        observacao=observacao,
    )
    payload['total_eventos_homologacao'], payload['ultimo_evento_homologacao'] = _meta_eventos_homologacao(proposta)
    return payload


@transaction.atomic
def reprovar_homologacao_cenario_fiscal(
    proposta: Proposta,
    *,
    observacao: str = '',
    usuario=None,
) -> HomologacaoFiscalPropostaDict:
    ok, msg = proposta_permite_alterar_calculo_homologacao(proposta)
    if not ok:
        raise ValueError(msg)
    payload = _persistir_homologacao(
        proposta,
        status=Proposta.HomologacaoFiscalStatus.REPROVADA,
        observacao=observacao,
        usar_cenario=False,
        recalcular=True,
    )
    _registrar_apos_acao(
        proposta,
        HomologacaoFiscalPropostaEvento.TipoEvento.REPROVADA,
        payload,
        usuario=usuario,
        observacao=observacao,
    )
    payload['total_eventos_homologacao'], payload['ultimo_evento_homologacao'] = _meta_eventos_homologacao(proposta)
    return payload


@transaction.atomic
def voltar_legado_homologacao_cenario_fiscal(
    proposta: Proposta,
    *,
    observacao: str = '',
    usuario=None,
) -> HomologacaoFiscalPropostaDict:
    ok, msg = proposta_permite_alterar_calculo_homologacao(proposta)
    if not ok:
        raise ValueError(msg)
    payload = _persistir_homologacao(
        proposta,
        status=Proposta.HomologacaoFiscalStatus.VOLTOU_LEGADO,
        observacao=observacao,
        usar_cenario=False,
        recalcular=True,
    )
    _registrar_apos_acao(
        proposta,
        HomologacaoFiscalPropostaEvento.TipoEvento.VOLTOU_LEGADO,
        payload,
        usuario=usuario,
        observacao=observacao,
    )
    payload['total_eventos_homologacao'], payload['ultimo_evento_homologacao'] = _meta_eventos_homologacao(proposta)
    return payload


def homologar_proposta_cenario_fiscal(
    proposta: Proposta,
    *,
    usuario=None,
    cenario_id: int | None = None,
) -> HomologacaoFiscalPropostaDict:
    """Gera comparativo/resumo sem alterar a proposta (somente leitura)."""
    del usuario
    if cenario_id and cenario_id != proposta.cenario_fiscal_saida_id:
        proposta = Proposta.objects.get(pk=proposta.pk)
    return montar_homologacao_fiscal_proposta(proposta)
