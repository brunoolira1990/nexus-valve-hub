"""NF-e Saída 3.5 — payload unificado de conferência pré-emissão."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.core.ordenacao_itens import listar_itens_por_inclusao
from apps.fiscal.models import ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_bloqueio import (
    dados_complementares_editaveis,
    itens_comerciais_editaveis,
    origem_comercial_travada,
    pode_atualizar_impostos_nfe,
)
from apps.fiscal.nfe_saida_reforma_calculo import diagnosticar_reforma_calculo
from apps.fiscal.snapshot_fiscal_helpers import (
    cfop_from_snapshot_fiscal,
    get_cofins_snapshot,
    get_icms_snapshot,
    get_ipi_snapshot,
    get_ncm_snapshot,
    get_pis_snapshot,
    get_reforma_tributaria_snapshot,
    montar_reforma_item_exibicao,
    reforma_configurada_no_snapshot,
    status_reforma_item,
)
from apps.regras_fiscais.reforma_tributaria_config import normalizar_percentual_reforma
from apps.fiscal.nfe_saida_conferencia_diagnostico import (
    alertas_fiscal_gerais,
    alertas_fiscal_item,
    diagnostico_reforma_item,
)
from apps.fiscal.nfe_saida_prontidao import montar_payload_prontidao, pode_validar_conferencia
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.nfe_emissao.numeracao import NFeNumeracaoError, obter_config_numeracao


def _dec(v) -> Decimal:
    if v is None or v == '':
        return Decimal('0')
    s = str(v).strip()
    if ',' in s:
        return normalizar_percentual_reforma(v)
    try:
        return Decimal(s)
    except Exception:
        return normalizar_percentual_reforma(v)


def _fmt_dec(v: Decimal, places: int = 2) -> str:
    q = Decimal('0.001') if places == 3 else Decimal('0.01')
    return str(v.quantize(q))


def _text(val) -> str:
    return (str(val) if val is not None else '').strip()


def _origem_label(nf: NFeSaida) -> str:
    if nf.faturamento_pedido_venda_id:
        return 'FATURAMENTO'
    if nf.pedido_venda_id:
        return 'PEDIDO'
    return 'MANUAL'


def _descricao_item(item: ItemNFeSaida) -> str:
    snap = item.snapshot_produto or {}
    if snap.get('descricao'):
        return str(snap['descricao'])
    if item.produto_id:
        return item.produto.descricao
    return ''


def _unidade_item(item: ItemNFeSaida) -> str:
    snap_c = item.snapshot_comercial or {}
    return _text(snap_c.get('unidade_negociada') or (item.snapshot_produto or {}).get('unidade') or 'PC')


def _pedido_cliente_efetivo_item(nf: NFeSaida, item: ItemNFeSaida) -> tuple[str, str]:
    num = _text(item.pedido_cliente_numero) or _text(nf.pedido_cliente_numero)
    linha = _text(item.pedido_cliente_item)
    return num, linha


def _montar_item_conferencia(nf: NFeSaida, item: ItemNFeSaida, idx: int) -> dict[str, Any]:
    snap_f = item.snapshot_fiscal or {}
    snap_c = item.snapshot_comercial or {}
    qtd = _dec(item.quantidade)
    v_unit = _dec(item.valor)
    v_prod = qtd * v_unit
    desconto = _dec(snap_c.get('desconto'))
    v_total = v_prod - desconto
    reforma_raw = get_reforma_tributaria_snapshot(snap_f)
    reforma = montar_reforma_item_exibicao(reforma_raw, valor_produto=v_prod)
    fiscal_icms = get_icms_snapshot(snap_f)
    fiscal_ipi = get_ipi_snapshot(snap_f)
    fiscal_pis = get_pis_snapshot(snap_f)
    fiscal_cofins = get_cofins_snapshot(snap_f)
    fiscal_atual = {
        'ncm': get_ncm_snapshot(snap_f) or _text((item.snapshot_produto or {}).get('ncm')),
        'icms': fiscal_icms,
        'ipi': fiscal_ipi,
        'pis': fiscal_pis,
        'cofins': fiscal_cofins,
        'origem_regra': _text(snap_f.get('origem_regra_fiscal_saida')),
        'snapshot_fiscal': snap_f,
    }
    pc_num, pc_item = _pedido_cliente_efetivo_item(nf, item)
    return {
        'n_item': idx,
        'item_id': item.pk,
        'produto_id': item.produto_id,
        'produto_codigo': _text((item.snapshot_produto or {}).get('codigo_completo') or (item.snapshot_produto or {}).get('codigo')),
        'descricao': _descricao_item(item),
        'ncm': get_ncm_snapshot(snap_f) or _text((item.snapshot_produto or {}).get('ncm')),
        'cfop': cfop_from_snapshot_fiscal(snap_f),
        'unidade': _unidade_item(item),
        'quantidade': _fmt_dec(qtd, 3),
        'valor_unitario': _fmt_dec(v_unit),
        'desconto': _fmt_dec(desconto),
        'valor_total': _fmt_dec(v_total),
        'corrida_numero': item.corrida.numero if item.corrida_id else '',
        'pedido_cliente_numero': pc_num,
        'pedido_cliente_item': pc_item,
        'pedido_cliente_numero_editavel': item.pedido_cliente_numero,
        'pedido_cliente_item_editavel': item.pedido_cliente_item,
        'observacao_item': item.observacao_item,
        'informacao_adicional_item': item.informacao_adicional_item,
        'status_fiscal': 'COM_SNAPSHOT' if snap_f else 'SEM_SNAPSHOT',
        'status_reforma': status_reforma_item(reforma_raw),
        'comercial': {
            'codigo': _text((item.snapshot_produto or {}).get('codigo_completo')),
            'descricao': _descricao_item(item),
            'unidade': _unidade_item(item),
            'quantidade': _fmt_dec(qtd, 3),
            'valor_unitario': _fmt_dec(v_unit),
            'desconto': _fmt_dec(desconto),
            'valor_total': _fmt_dec(v_total),
            'corrida': item.corrida.numero if item.corrida_id else '',
            'item_faturamento_id': item.item_faturamento_pedido_id,
            'snapshot_comercial': snap_c,
        },
        'fiscal_atual': fiscal_atual,
        'fiscal_alertas': alertas_fiscal_item(snap_f, fiscal_atual),
        'reforma_tributaria': reforma,
        'reforma_configurada': reforma_configurada_no_snapshot(snap_f),
        'reforma_diagnostico': (
            diagnosticar_reforma_calculo(reforma_raw, valor_produto=v_prod)
            or diagnostico_reforma_item(nf, item, snap_f, reforma_raw)
        ),
    }


def _somar_totais_fiscais(itens: list[dict]) -> dict[str, str]:
    tot_icms = tot_ipi = tot_pis = tot_cofins = tot_cbs = tot_ibs_uf = tot_ibs_mun = Decimal('0')
    for row in itens:
        fa = row.get('fiscal_atual') or {}
        fr = row.get('reforma_tributaria') or {}
        tot_icms += _dec((fa.get('icms') or {}).get('valor'))
        tot_ipi += _dec((fa.get('ipi') or {}).get('valor'))
        tot_pis += _dec((fa.get('pis') or {}).get('valor'))
        tot_cofins += _dec((fa.get('cofins') or {}).get('valor'))
        tot_cbs += _dec(fr.get('valor_cbs'))
        tot_ibs_uf += _dec(fr.get('valor_ibs_estadual'))
        tot_ibs_mun += _dec(fr.get('valor_ibs_municipal'))
    return {
        'valor_icms': _fmt_dec(tot_icms),
        'valor_ipi': _fmt_dec(tot_ipi),
        'valor_pis': _fmt_dec(tot_pis),
        'valor_cofins': _fmt_dec(tot_cofins),
        'valor_cbs': _fmt_dec(tot_cbs),
        'valor_ibs_estadual': _fmt_dec(tot_ibs_uf),
        'valor_ibs_municipal': _fmt_dec(tot_ibs_mun),
        'total_ibs_cbs': _fmt_dec(tot_cbs + tot_ibs_uf + tot_ibs_mun),
        'total_tributos_atuais': _fmt_dec(tot_icms + tot_ipi + tot_pis + tot_cofins),
    }


def _resumo_reforma_geral(itens: list[dict]) -> dict[str, Any]:
    com = sum(1 for i in itens if i.get('reforma_configurada'))
    sem_cst = sum(
        1
        for i in itens
        if i.get('reforma_configurada') and not _text((i.get('reforma_tributaria') or {}).get('cst_ibs_cbs'))
    )
    sem_class = sum(
        1
        for i in itens
        if i.get('reforma_configurada')
        and not _text((i.get('reforma_tributaria') or {}).get('classificacao_tributaria'))
    )
    status = 'NAO_CONFIGURADA'
    if com:
        if sem_cst or sem_class:
            status = 'PENDENTE'
        elif any(i.get('status_reforma') == 'ATENCAO' for i in itens):
            status = 'ATENCAO'
        elif any(i.get('status_reforma') == 'SEM_CALCULO' for i in itens):
            status = 'ATENCAO'
        elif all(i.get('status_reforma') == 'OK' for i in itens if i.get('reforma_configurada')):
            status = 'OK'
        else:
            status = 'ATENCAO'
    return {
        'status': status,
        'itens_com_reforma': com,
        'itens_sem_reforma': len(itens) - com,
        'itens_sem_cst': sem_cst,
        'itens_sem_classificacao': sem_class,
    }


_STATUS_EMISSAO_RETRY = frozenset(
    {
        NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO,
        NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
        NFeSaida.StatusEmissaoSefaz.NUMERACAO_RESERVADA,
        NFeSaida.StatusEmissaoSefaz.XML_GERADO,
        NFeSaida.StatusEmissaoSefaz.XML_ASSINADO,
        NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
        'LOTE_PROCESSADO_SEM_PROTOCOLO',
        'AGUARDANDO_PROCESSAMENTO',
    },
)


def _emissao_homolog_iniciada_sem_status(nf: NFeSaida) -> bool:
    """Emissão registrada no histórico, mas sem status SEFAZ persistido (timeout/interrupção)."""
    if (nf.status_emissao_sefaz or '').strip():
        return False
    from apps.fiscal.models import NFeSaidaEvento

    return NFeSaidaEvento.objects.filter(
        nfe_saida=nf,
        tipo_evento=NFeSaidaEvento.TipoEvento.EMISSAO_HOMOLOGACAO_INICIADA,
    ).exists()


def _montar_permissoes_emissao_homolog(
    nf: NFeSaida,
    checklist: dict[str, Any] | None,
    *,
    itens_count: int,
) -> dict[str, Any]:
    from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import (
        MSG_AMBIENTE_NAO_DEFINIDO,
        ambiente_emissao_nfe_definido,
    )

    ambiente_prod = nf.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO
    ambiente_definido = ambiente_emissao_nfe_definido(nf)
    pronta = nf.status_conferencia == NFeSaida.StatusConferencia.PRONTA_PARA_EMISSAO
    nao_autorizada = nf.status_emissao_sefaz != NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
    pode_tentar = pronta and nao_autorizada and not ambiente_prod and ambiente_definido
    checklist_ok = bool((checklist or {}).get('pode_emitir'))
    # modo abertura não inclui checklist — marcar pronta já validou na hora
    if not checklist_ok and checklist is None and pronta and nf.conferencia_marcada_pronta_em:
        checklist_ok = True
    pront_payload = montar_payload_prontidao(nf, validacao=checklist)
    emissao_orfa = _emissao_homolog_iniciada_sem_status(nf)
    retry_sefaz = (nf.status_emissao_sefaz or '') in _STATUS_EMISSAO_RETRY or emissao_orfa
    pode_emitir = pode_tentar and (checklist_ok or retry_sefaz)
    motivo = ''
    if not ambiente_definido:
        motivo = MSG_AMBIENTE_NAO_DEFINIDO
    elif emissao_orfa and pode_tentar:
        motivo = (
            'Emissão em homologação foi iniciada, mas não houve retorno SEFAZ registrado. '
            'Tente emitir novamente.'
        )
    elif pode_tentar and not pode_emitir:
        motivo = 'Resolva as pendências na aba Validação antes de emitir em homologação.'
    elif not pronta:
        motivo = 'Marque a NF-e como pronta para emissão na conferência.'
    elif ambiente_prod:
        motivo = 'NF-e configurada para produção SEFAZ. Use o fluxo de emissão em produção.'
    elif not nao_autorizada:
        motivo = 'NF-e já autorizada em homologação.'

    pode_marcar = pront_payload['pode_marcar_pronta'] and nao_autorizada
    motivo_marcar = ''
    if not ambiente_definido:
        pode_marcar = False
        motivo_marcar = MSG_AMBIENTE_NAO_DEFINIDO
    elif pode_marcar and ambiente_prod:
        from apps.fiscal.nfe_emissao.validacao_producao import montar_validacao_preparacao_producao

        prep = montar_validacao_preparacao_producao(nf)
        if not prep.get('pronta'):
            pode_marcar = False
            pends = prep.get('pendencias') or []
            motivo_marcar = (
                pends[0].get('mensagem') if pends else 'Checklist produção pendente.'
            )
    elif not pode_marcar:
        motivo_marcar = 'Resolva as pendências bloqueantes antes de marcar pronta.'

    return {
        'origem_comercial_travada': origem_comercial_travada(nf),
        'itens_comerciais_editaveis': itens_comerciais_editaveis(nf),
        'dados_complementares_editaveis': dados_complementares_editaveis(nf),
        'fiscal_editavel': itens_comerciais_editaveis(nf) and not origem_comercial_travada(nf),
        'pode_atualizar_impostos': pode_atualizar_impostos_nfe(nf, itens_count=itens_count),
        'pode_validar_conferencia': pode_validar_conferencia(nf) and nao_autorizada,
        'pode_marcar_pronta': pode_marcar,
        'motivo_marcar_pronta_bloqueado': motivo_marcar,
        'ambiente_emissao_definido': ambiente_definido,
        'pode_tentar_emitir_homologacao': pode_tentar,
        'pode_emitir_homologacao': pode_emitir,
        'motivo_emitir_homologacao_bloqueado': motivo,
    }


def _ultimo_evento_erro_transmissao(nf: NFeSaida) -> dict[str, Any]:
    from apps.fiscal.models import NFeSaidaEvento

    evt = (
        NFeSaidaEvento.objects.filter(
            nfe_saida=nf,
            tipo_evento=NFeSaidaEvento.TipoEvento.ERRO_TRANSMISSAO_SEFAZ,
        )
        .order_by('-pk')
        .first()
    )
    if not evt:
        return {}
    resumo = evt.resumo if isinstance(evt.resumo, dict) else {}
    return {
        'etapa_falha': resumo.get('etapa') or '',
        'mensagem_erro': evt.observacao or resumo.get('erro') or '',
    }


def _numeracao_cadastro_resumo(empresa_pk: int, ambiente: str) -> dict[str, Any] | None:
    try:
        cfg = obter_config_numeracao(empresa_pk, ambiente=ambiente)
        return {
            'modelo_documento': cfg.modelo_documento,
            'serie': cfg.serie,
            'proximo_numero': cfg.proximo_numero,
        }
    except NFeNumeracaoError:
        return None


def _montar_emissao_sefaz_payload(nf: NFeSaida) -> dict[str, Any]:
    ambiente = (nf.ambiente_emissao or '').strip()
    numeracao_homolog = None
    numeracao_producao = None
    try:
        empresa = resolver_empresa_emitente_nfe(nf)
        if ambiente == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
            numeracao_homolog = _numeracao_cadastro_resumo(empresa.pk, 'homologacao')
        elif ambiente == NFeSaida.AmbienteEmissao.PRODUCAO:
            numeracao_producao = _numeracao_cadastro_resumo(empresa.pk, 'producao')
    except (NFeNumeracaoError, ValueError):
        numeracao_homolog = None
        numeracao_producao = None

    emissao_orfa = _emissao_homolog_iniciada_sem_status(nf)
    return {
        'ambiente_emissao': nf.ambiente_emissao,
        'status_conferencia': nf.status_conferencia or '',
        'serie_nfe': nf.serie_nfe,
        'numero_nfe': nf.numero_nfe,
        'chave_acesso': nf.chave_acesso,
        'status_emissao_sefaz': nf.status_emissao_sefaz,
        'emissao_iniciada_pendente': emissao_orfa,
        'mensagem_emissao_pendente': (
            'Emissão em homologação foi iniciada, mas ainda não há status SEFAZ registrado. '
            'Aguarde ou use «Tentar emitir novamente em homologação».'
            if emissao_orfa
            else ''
        ),
        'protocolo_autorizacao': nf.protocolo_autorizacao,
        'cstat_autorizacao': nf.cstat_autorizacao,
        'motivo_autorizacao': nf.motivo_autorizacao,
        'autorizada_em': nf.autorizada_em.isoformat() if nf.autorizada_em else None,
        'tem_xml_assinado': bool((nf.xml_assinado or '').strip()),
        'tem_xml_autorizado': bool((nf.xml_autorizado or '').strip()),
        'tem_xml_nfe_gerado': bool((nf.xml_nfe_gerado or '').strip()),
        'tem_xml_envio_lote': bool((nf.xml_envio_lote or '').strip()),
        'tem_xml_retorno': bool((nf.xml_retorno or nf.xml_retorno_lote or '').strip()),
        'numeracao_homologacao': numeracao_homolog,
        'numeracao_producao': numeracao_producao,
        'lote': {
            'cstat': nf.cstat_lote or '',
            'xmotivo': nf.xmotivo_lote or '',
            'recibo': nf.recibo_lote or '',
        },
        'nfe': {
            'cstat': nf.cstat_autorizacao or '',
            'xmotivo': nf.motivo_autorizacao or '',
            'protocolo': nf.protocolo_autorizacao or '',
            'dh_recbto': nf.autorizada_em.isoformat() if nf.autorizada_em else '',
        },
        **_ultimo_evento_erro_transmissao(nf),
        **_correcao_serie_homologacao_payload(nf),
        'autorizada_homologacao': nf.status_emissao_sefaz
        == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        'mensagem_status_homologacao': (
            'NF-e autorizada em homologação pela SEFAZ. Documento sem valor fiscal de produção.'
            if nf.status_emissao_sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO
            else ''
        ),
    }


def _correcao_serie_homologacao_payload(nf: NFeSaida) -> dict[str, Any]:
    from apps.fiscal.nfe_emissao.corrigir_serie_homologacao import pode_corrigir_serie_homologacao

    pode, motivo = pode_corrigir_serie_homologacao(nf)
    return {
        'pode_corrigir_serie_homologacao': pode,
        'motivo_corrigir_serie_bloqueado': motivo if not pode else '',
        'cstat_serie_invalida': (nf.cstat_autorizacao or '') == '266',
    }


def _resumo_operacional_nfe(nf: NFeSaida) -> dict[str, Any]:
    from apps.comercial.services.resumo_atendimento_operacional import (
        obter_resumo_atendimento_operacional,
    )

    return obter_resumo_atendimento_operacional(nf, contexto='nfe_saida')


def _montar_indicadores_fiscais_conferencia(nf: NFeSaida) -> dict[str, Any]:
    from apps.fiscal.nfe_operacao_fiscal_indicadores import IND_PRES_OPCOES, montar_indicadores_fiscais_payload

    payload = montar_indicadores_fiscais_payload(nf)
    payload['ind_pres_opcoes'] = [{'valor': k, 'label': v} for k, v in IND_PRES_OPCOES.items()]
    return payload


def _montar_higienizacao_xml_conferencia(nf: NFeSaida) -> dict[str, Any]:
    from apps.fiscal.nfe_xml_higienizacao import montar_resumo_higienizacao_xml

    return montar_resumo_higienizacao_xml(nf, None)


def montar_conferencia_nfe_saida(
    nf: NFeSaida,
    *,
    modo: str = 'abertura',
    validacao: dict[str, Any] | None = None,
    incluir_checklist: bool | None = None,
    incluir_resumo_operacional: bool = True,
    usuario=None,
) -> dict[str, Any]:
    """
    Monta payload da conferência NF-e.

    modo='abertura' (padrão): leve — sem checklist completo nem validação pesada.
    modo='completo': inclui checklist (reutiliza `validacao` quando informada).
    """
    from apps.fiscal.nfe_perf import medir_nfe_perf
    from apps.fiscal.nfe_saida_prontidao import montar_payload_prontidao
    from apps.fiscal.validacao_nfe_saida import (
        MODO_VALIDACAO_COMPLETO,
        MODO_VALIDACAO_LEVE,
        validar_nfe_saida_para_emissao,
    )

    modo_norm = (modo or 'abertura').strip().lower()
    abertura = modo_norm == 'abertura'
    if incluir_checklist is None:
        incluir_checklist = not abertura

    with medir_nfe_perf('montar_conferencia', nfe_id=nf.pk, modo=modo_norm) as perf:
        nf = (
            NFeSaida.objects.select_related(
                'cliente',
                'transportadora',
                'pedido_venda',
                'pedido_venda__empresa_emitente',
                'faturamento_pedido_venda',
            )
            .prefetch_related('itens__produto', 'itens__corrida', 'itens__item_faturamento_pedido')
            .get(pk=nf.pk)
        )
        perf.marcar('db_ms')
        from apps.fiscal.nfe_emissao.ambiente_emissao_nfe import garantir_ambiente_emissao_nfe_saida

        nf = garantir_ambiente_emissao_nfe_saida(nf)
        itens_rows = [
            _montar_item_conferencia(nf, item, idx)
            for idx, item in enumerate(listar_itens_por_inclusao(nf.itens.all()), start=1)
        ]
        totais_fiscais = _somar_totais_fiscais(itens_rows)
        soma_produtos = sum((_dec(i['valor_total']) for i in itens_rows), Decimal('0'))
        pedido = nf.pedido_venda
        empresa = pedido.empresa_emitente if pedido and pedido.empresa_emitente_id else None

        checklist: dict[str, Any] | None = None
        val = validacao
        if incluir_checklist:
            if val is None:
                val = validar_nfe_saida_para_emissao(
                    nf,
                    modo=MODO_VALIDACAO_LEVE if abertura else MODO_VALIDACAO_COMPLETO,
                )
            checklist = val
        perf.marcar('checklist_ms')

        resumo_operacional = _resumo_operacional_nfe(nf) if incluir_resumo_operacional else None
        perf.marcar('resumo_ms')

        from apps.fiscal.nfe_saida_apresentacao import montar_apresentacao_nfe_saida

        prontidao = montar_payload_prontidao(nf, validacao=val if incluir_checklist else None)
        permissoes = _montar_permissoes_emissao_homolog(
            nf,
            checklist,
            itens_count=len(itens_rows),
        )
        from apps.fiscal.nfe_emissao.conferencia_producao import (
            montar_emissao_producao_conferencia,
            montar_permissoes_emissao_producao,
        )

        perm_prod = montar_permissoes_emissao_producao(nf, usuario=usuario)
        permissoes.update(perm_prod)

        payload: dict[str, Any] = {
            'nfe': {
                'id': nf.pk,
                'numero': nf.numero,
                'status': nf.status,
                'data': nf.data.isoformat(),
                'valor_total': float(nf.valor_total),
                'cliente_id': nf.cliente_id,
                'cliente_nome': nf.cliente.razao_social,
                'pedido_venda_id': nf.pedido_venda_id,
                'pedido_venda_numero': pedido.numero if pedido else '',
                'faturamento_pedido_venda_id': nf.faturamento_pedido_venda_id,
                'origem': _origem_label(nf),
                'modo_atendimento_estoque': nf.modo_atendimento_estoque,
                'observacao_origem': nf.observacao_origem,
                'pedido_cliente_numero': nf.pedido_cliente_numero,
                'pedido_cliente_observacao': nf.pedido_cliente_observacao,
                'cliente_informacoes_complementares_nfe': (
                    (nf.cliente.informacoes_complementares_nfe or '').strip() if nf.cliente_id else ''
                ),
                'empresa_emitente_nome': empresa.razao_social if empresa else '',
                'empresa_emitente_id': pedido.empresa_emitente_id if pedido else None,
                'natureza_operacao': 'Venda de mercadoria',
                'tipo_operacao': 'SAIDA',
                'finalidade_emissao': 'NORMAL',
            },
            'itens': itens_rows,
            'totais_comerciais': {
                'total_produtos': _fmt_dec(soma_produtos),
                'frete': _fmt_dec(nf.valor_frete),
                'total_nf': _fmt_dec(nf.valor_total),
                'divergencia_itens_nf': abs(soma_produtos - _dec(nf.valor_total)) > Decimal('0.02'),
            },
            'fiscal_atual': {
                'por_item': [
                    {
                        'item_id': i['item_id'],
                        'descricao': i['descricao'],
                        'ncm': i['ncm'],
                        'cfop': i['cfop'],
                        'fiscal': i['fiscal_atual'],
                        'alertas': i.get('fiscal_alertas') or [],
                    }
                    for i in itens_rows
                ],
                'totais': totais_fiscais,
                'alertas_gerais': alertas_fiscal_gerais(totais_fiscais),
            },
            'reforma_tributaria': {
                'resumo': _resumo_reforma_geral(itens_rows),
                'totais': {
                    'valor_cbs': totais_fiscais['valor_cbs'],
                    'valor_ibs_estadual': totais_fiscais['valor_ibs_estadual'],
                    'valor_ibs_municipal': totais_fiscais['valor_ibs_municipal'],
                    'total_ibs_cbs': totais_fiscais['total_ibs_cbs'],
                },
                'itens': [
                    {
                        'item_id': i['item_id'],
                        'descricao': i['descricao'],
                        'status': i['status_reforma'],
                        'dados': i['reforma_tributaria'],
                        'reforma_configurada': i.get('reforma_configurada'),
                        'diagnostico': i.get('reforma_diagnostico') or '',
                    }
                    for i in itens_rows
                ],
            },
            'transporte': {
                'transportadora_id': nf.transportadora_id,
                'transportadora_nome': nf.transportadora.razao_social if nf.transportadora_id else '',
                'transportadora_cnpj': nf.transportadora.cnpj if nf.transportadora_id else '',
                'modalidade_frete': nf.modalidade_frete or '9',
                'valor_frete': float(nf.valor_frete),
                'quantidade_volumes': nf.quantidade_volumes,
                'peso_bruto': float(nf.peso_bruto),
                'peso_liquido': float(nf.peso_liquido),
                'especie_volumes': nf.especie_volumes,
                'marca_volumes': nf.marca_volumes,
                'numeracao_volumes': nf.numeracao_volumes,
                'placa_veiculo': nf.placa_veiculo,
                'uf_veiculo': nf.uf_veiculo,
            },
            'observacoes': {
                'observacoes_nfe': nf.observacoes_nfe,
                'informacoes_adicionais': nf.informacoes_adicionais,
                'informacoes_fisco': nf.informacoes_fisco,
                'observacoes_internas': nf.observacoes_internas,
                'observacao_origem': nf.observacao_origem,
            },
            'checklist': checklist,
            'checklist_desatualizado': abertura and not incluir_checklist,
            'prontidao': prontidao,
            'permissoes': permissoes,
            'emissao_sefaz': _montar_emissao_sefaz_payload(nf),
            'emissao_producao': montar_emissao_producao_conferencia(nf, usuario=usuario),
            'apresentacao': montar_apresentacao_nfe_saida(nf),
            'modo_carregamento': modo_norm,
            'indicadores_fiscais': _montar_indicadores_fiscais_conferencia(nf),
            'higienizacao_xml': _montar_higienizacao_xml_conferencia(nf),
        }
        if resumo_operacional is not None:
            payload['nfe']['resumo_atendimento_operacional'] = resumo_operacional
        from apps.fiscal.nfe_emissao.cancelamento_dados import montar_resumo_cancelamento_nfe_saida
        from apps.fiscal.nfe_saida_financeiro import montar_flags_financeiro_nfe

        payload['financeiro'] = montar_flags_financeiro_nfe(nf)
        payload['cancelamento'] = montar_resumo_cancelamento_nfe_saida(nf)
        return payload