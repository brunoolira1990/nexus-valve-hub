"""NF-e Saída 2 — validação fiscal/operacional antes da emissão (sem SEFAZ, estoque ou financeiro)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from apps.fiscal.models import AtendimentoEstoque, ItemNFeSaida, NFeSaida
from apps.fiscal.nfe_saida_from_faturamento import STATUS_NFE_RASCUNHO

TOLERANCIA_VALOR = Decimal('0.02')

TIPO_PENDENCIA = 'PENDENCIA'
TIPO_ALERTA = 'ALERTA'
TIPO_INFO = 'INFO'

STATUS_PRONTA = 'PRONTA'
STATUS_COM_PENDENCIAS = 'COM_PENDENCIAS'
STATUS_COM_ALERTAS = 'COM_ALERTAS'
STATUS_BLOQUEADA = 'BLOQUEADA'

STATUS_EMITIDA = frozenset({'EMITIDA', 'EMITIDO', 'AUTORIZADA_INTERNA', 'AUTORIZADA'})
STATUS_CANCELADA = frozenset({
    'CANCELADA',
    'CANCELADO',
    'CANCELADA_INTERNA',
    'CANCELADA_HOMOLOGACAO',
    'CANCELADA_PRODUCAO',
})


class ItemValidacao(TypedDict, total=False):
    tipo: str
    codigo: str
    grupo: str
    mensagem: str
    item_id: int | None


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _norm_status(status: str | None) -> str:
    return (status or '').strip().upper()


def _digits(val: str | None) -> str:
    return ''.join(c for c in str(val or '') if c.isdigit())


def _text(val: str | None) -> str:
    return (val or '').strip()


def _grupos_vazios() -> dict[str, list[ItemValidacao]]:
    return {
        'cliente': [],
        'emitente': [],
        'itens': [],
        'fiscal': [],
        'valores': [],
        'estoque': [],
        'transporte': [],
        'origem': [],
        'reforma_tributaria': [],
        'pedido_cliente': [],
        'totais': [],
    }


def _add(
    grupos: dict[str, list[ItemValidacao]],
    *,
    tipo: str,
    codigo: str,
    grupo: str,
    mensagem: str,
    item_id: int | None = None,
) -> None:
    entry: ItemValidacao = {
        'tipo': tipo,
        'codigo': codigo,
        'grupo': grupo,
        'mensagem': mensagem,
    }
    if item_id is not None:
        entry['item_id'] = item_id
    grupos.setdefault(grupo, []).append(entry)


def _ncm_item(item: ItemNFeSaida) -> str:
    snap_f = item.snapshot_fiscal or {}
    snap_p = item.snapshot_produto or {}
    ncm = _text(snap_f.get('ncm') or snap_p.get('ncm_codigo_snapshot'))
    if ncm:
        return ncm
    prod = item.produto
    if prod:
        ncm_obj = prod.get_ncm_efetivo()
        if ncm_obj:
            return _text(getattr(ncm_obj, 'codigo', ''))
        return _text(getattr(prod, 'ncm', ''))
    return ''


def _cfop_item(item: ItemNFeSaida) -> str:
    from apps.fiscal.snapshot_fiscal_helpers import cfop_from_snapshot_fiscal

    return cfop_from_snapshot_fiscal(item.snapshot_fiscal)


def _unidade_item(item: ItemNFeSaida) -> str:
    snap_f = item.snapshot_fiscal or {}
    snap_p = item.snapshot_produto or {}
    snap_c = item.snapshot_comercial or {}
    u = _text(
        snap_f.get('unidade_negociada')
        or snap_c.get('unidade_negociada')
        or snap_p.get('unidade_snapshot'),
    )
    if u:
        return u
    return _text(getattr(item.produto, 'unidade', '')) if item.produto_id else ''


def _descricao_item(item: ItemNFeSaida) -> str:
    snap_p = item.snapshot_produto or {}
    desc = _text(snap_p.get('descricao_produto_snapshot'))
    if desc:
        return desc
    return _text(item.produto.descricao) if item.produto_id else ''


def _valor_linha_item(item: ItemNFeSaida) -> Decimal:
    snap_c = item.snapshot_comercial or {}
    if snap_c.get('valor_total') not in (None, ''):
        return _dec(snap_c['valor_total'])
    qtd = _dec(item.quantidade)
    unit = _dec(item.valor)
    desconto = _dec(snap_c.get('desconto', 0))
    return qtd * unit - desconto


def _impostos_negativos(snapshot_fiscal: dict) -> list[str]:
    campos = (
        'icms_saida_percentual',
        'ipi_saida_percentual',
        'pis_saida_percentual',
        'cofins_saida_percentual',
        'fcp_percentual',
    )
    neg: list[str] = []
    for key in campos:
        if key not in snapshot_fiscal:
            continue
        try:
            if _dec(snapshot_fiscal[key]) < 0:
                neg.append(key)
        except Exception:
            continue
    return neg


def _nf_autorizada_com_xml_historico(nf: NFeSaida) -> bool:
    """NF-e com XML autorizado da SEFAZ — não regenerar/validar serialização retroativa."""
    if _text(getattr(nf, 'xml_autorizado', '')):
        return True
    sefaz_st = (nf.status_emissao_sefaz or '').strip()
    return sefaz_st == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO or _norm_status(nf.status) in STATUS_EMITIDA


def _montar_resultado(
    nf: NFeSaida,
    grupos: dict[str, list[ItemValidacao]],
    *,
    status_prontidao: str,
    pode_emitir: bool,
    mensagens: list[str],
) -> dict[str, Any]:
    total_pendencias = sum(
        1 for g in grupos.values() for it in g if it.get('tipo') == TIPO_PENDENCIA
    )
    total_alertas = sum(1 for g in grupos.values() for it in g if it.get('tipo') == TIPO_ALERTA)
    return {
        'nfe_saida_id': nf.pk,
        'numero': nf.numero,
        'status': nf.status,
        'status_prontidao': status_prontidao,
        'pode_emitir': pode_emitir,
        'total_pendencias': total_pendencias,
        'total_alertas': total_alertas,
        'grupos': grupos,
        'mensagens': mensagens,
    }


ModoValidacaoNFe = str  # 'completo' | 'leve'

MODO_VALIDACAO_COMPLETO = 'completo'
MODO_VALIDACAO_LEVE = 'leve'


def validar_nfe_saida_para_emissao(
    nfe_saida: NFeSaida,
    *,
    modo: ModoValidacaoNFe = MODO_VALIDACAO_COMPLETO,
    incluir_higienizacao_xml: bool = True,
) -> dict[str, Any]:
    """
    Valida NF-e Saída para futura emissão. Não altera banco, estoque, financeiro nem SEFAZ.

    modo='leve': checklist operacional rápido (sem ViaCEP remoto nem montagem XML Reforma).
    modo='completo': validação pré-transmissão com checagens pesadas.
    """
    modo_leve = (modo or MODO_VALIDACAO_COMPLETO).strip().lower() == MODO_VALIDACAO_LEVE
    consultar_cep = not modo_leve
    validar_reforma_xml = not modo_leve
    nf = nfe_saida
    grupos = _grupos_vazios()
    st = _norm_status(nf.status)
    sefaz_st = (nf.status_emissao_sefaz or '').strip()

    if sefaz_st == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO or st == 'AUTORIZADA_HOMOLOGACAO':
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='NFE_AUTORIZADA_HOMOLOG',
            grupo='origem',
            mensagem='NF-e autorizada em homologação. Esta autorização não possui valor fiscal de produção.',
        )
        return _montar_resultado(
            nf,
            grupos,
            status_prontidao=STATUS_BLOQUEADA,
            pode_emitir=False,
            mensagens=[
                'NF-e autorizada em homologação. Esta autorização não possui valor fiscal de produção.',
            ],
        )

    if st in STATUS_CANCELADA:
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='NFE_CANCELADA',
            grupo='origem',
            mensagem='NF-e cancelada. Consulta de dados e documentos locais apenas — sem emissão ou reenvio.',
        )
        return _montar_resultado(
            nf,
            grupos,
            status_prontidao=STATUS_BLOQUEADA,
            pode_emitir=False,
            mensagens=['NF-e cancelada. Visualização e consulta de documentos locais apenas.'],
        )

    if st in STATUS_EMITIDA:
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='NFE_JA_EMITIDA',
            grupo='origem',
            mensagem='NF-e já consta como emitida no sistema.',
        )
        return _montar_resultado(
            nf,
            grupos,
            status_prontidao=STATUS_BLOQUEADA,
            pode_emitir=False,
            mensagens=['NF-e já emitida; validação de emissão não se aplica.'],
        )

    if st and st != STATUS_NFE_RASCUNHO:
        _add(
            grupos,
            tipo=TIPO_ALERTA,
            codigo='STATUS_LEGADO',
            grupo='origem',
            mensagem=f'Status «{nf.status}» é legado; confirme se a nota ainda é rascunho antes de emitir.',
        )

    if st != STATUS_NFE_RASCUNHO and st not in STATUS_EMITIDA and st not in STATUS_CANCELADA:
        pass
    elif st == STATUS_NFE_RASCUNHO:
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='NFE_RASCUNHO',
            grupo='origem',
            mensagem='NF-e em rascunho — validação preparatória para emissão futura.',
        )

    # --- Cliente ---
    if not nf.cliente_id:
        _add(
            grupos,
            tipo=TIPO_PENDENCIA,
            codigo='CLIENTE_NAO_INFORMADO',
            grupo='cliente',
            mensagem='Cliente não informado na NF-e.',
        )
    else:
        cli = nf.cliente
        if not _text(cli.razao_social):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='CLIENTE_SEM_RAZAO_SOCIAL',
                grupo='cliente',
                mensagem='Cliente sem razão social.',
            )
        if not _digits(cli.cnpj):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='CLIENTE_SEM_DOCUMENTO',
                grupo='cliente',
                mensagem='Cliente sem CNPJ/CPF informado.',
            )
        if not _text(cli.uf):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='CLIENTE_SEM_UF',
                grupo='cliente',
                mensagem='Cliente sem UF de destino.',
            )
        if not _text(cli.cidade):
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='CLIENTE_SEM_CIDADE',
                grupo='cliente',
                mensagem='Cliente sem cidade informada.',
            )
        if not _text(cli.logradouro):
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='CLIENTE_SEM_ENDERECO',
                grupo='cliente',
                mensagem='Cliente sem logradouro informado.',
            )
        if not _text(cli.ie):
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='CLIENTE_SEM_IE',
                grupo='cliente',
                mensagem='Cliente sem inscrição estadual (IE); confira contribuinte ICMS.',
            )
        from apps.fiscal.nfe_destinatario_fiscal import resolver_perfil_destinatario_nf

        perfil_cli = resolver_perfil_destinatario_nf(nf)
        for inc in perfil_cli.inconsistencias:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='CLIENTE_CADASTRO_FISCAL_INCONSISTENTE',
                grupo='cliente',
                mensagem=inc,
            )
        if getattr(cli, 'bloqueado', False):
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='CLIENTE_BLOQUEADO',
                grupo='cliente',
                mensagem='Cliente está bloqueado no cadastro.',
            )
        if hasattr(cli, 'ativo') and not cli.ativo:
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='CLIENTE_INATIVO',
                grupo='cliente',
                mensagem='Cliente inativo no cadastro.',
            )

        from apps.cadastros.endereco_fiscal import validar_endereco_fiscal

        endereco_fiscal = validar_endereco_fiscal(cli, consultar_cep=consultar_cep, exigir_endereco_completo=True)
        if endereco_fiscal.bloqueio_fiscal:
            msg = (
                endereco_fiscal.alertas[0]
                if endereco_fiscal.alertas
                else (
                    endereco_fiscal.pendencias[0]
                    if endereco_fiscal.pendencias
                    else 'Cliente com endereço fiscal inconsistente.'
                )
            )
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='CLIENTE_ENDERECO_FISCAL_INCONSISTENTE',
                grupo='cliente',
                mensagem=msg,
            )
        elif endereco_fiscal.alertas:
            for aviso in endereco_fiscal.alertas:
                _add(
                    grupos,
                    tipo=TIPO_ALERTA,
                    codigo='CLIENTE_ENDERECO_FISCAL_ALERTA',
                    grupo='cliente',
                    mensagem=aviso,
                )

    # --- Emitente (via pedido) ---
    pedido = nf.pedido_venda
    emp = pedido.empresa_emitente if pedido and pedido.empresa_emitente_id else None
    if not emp:
        _add(
            grupos,
            tipo=TIPO_ALERTA,
            codigo='EMITENTE_NAO_VINCULADO',
            grupo='emitente',
            mensagem='Empresa emitente não identificada (vincule pedido de venda com emitente).',
        )
    else:
        if not _text(emp.razao_social):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='EMITENTE_SEM_RAZAO_SOCIAL',
                grupo='emitente',
                mensagem='Empresa emitente sem razão social.',
            )
        if not _digits(emp.cnpj):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='EMITENTE_SEM_CNPJ',
                grupo='emitente',
                mensagem='Empresa emitente sem CNPJ.',
            )
        if not _text(emp.uf):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='EMITENTE_SEM_UF',
                grupo='emitente',
                mensagem='Empresa emitente sem UF de origem.',
            )
        if not _text(emp.regime_tributario):
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='EMITENTE_SEM_REGIME',
                grupo='emitente',
                mensagem='Empresa emitente sem regime tributário cadastrado.',
            )

    uf_origem = _text(emp.uf) if emp else ''
    uf_destino = ''
    if nf.cliente_id:
        from apps.cadastros.endereco_fiscal import validar_endereco_fiscal

        endereco_cli = validar_endereco_fiscal(nf.cliente, consultar_cep=consultar_cep, exigir_endereco_completo=True)
        if endereco_cli.consistente and not endereco_cli.bloqueio_fiscal:
            uf_destino = endereco_cli.uf_destino or _text(nf.cliente.uf)
        else:
            uf_destino = ''

    # --- Origem faturamento / manual ---
    de_faturamento = bool(nf.faturamento_pedido_venda_id)
    if de_faturamento:
        fat = nf.faturamento_pedido_venda
        if fat is None:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='FATURAMENTO_NAO_ENCONTRADO',
                grupo='origem',
                mensagem='Faturamento vinculado não encontrado.',
            )
        else:
            from apps.comercial.models import FaturamentoPedidoVenda

            fat_st = (fat.status or '').strip().upper()
            if fat_st != FaturamentoPedidoVenda.Status.GERADO_NFE:
                _add(
                    grupos,
                    tipo=TIPO_PENDENCIA,
                    codigo='FATURAMENTO_STATUS_INVALIDO',
                    grupo='origem',
                    mensagem=f'Faturamento com status «{fat.status}»; esperado GERADO_NFE.',
                )
            if fat.nfe_saida_id and fat.nfe_saida_id != nf.pk:
                _add(
                    grupos,
                    tipo=TIPO_PENDENCIA,
                    codigo='FATURAMENTO_NFE_DIVERGENTE',
                    grupo='origem',
                    mensagem='Faturamento aponta para outra NF-e Saída.',
                )
        if not nf.pedido_venda_id:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='PEDIDO_NAO_VINCULADO',
                grupo='origem',
                mensagem='NF-e de faturamento sem pedido de venda vinculado.',
            )
    else:
        _add(
            grupos,
            tipo=TIPO_ALERTA,
            codigo='NFE_ORIGEM_MANUAL',
            grupo='origem',
            mensagem='NF-e criada manualmente; confirme origem comercial e fiscal.',
        )

    # --- Itens ---
    from apps.core.ordenacao_itens import listar_itens_por_inclusao

    itens = listar_itens_por_inclusao(nf.itens.select_related('produto', 'item_faturamento_pedido'))
    if not itens:
        _add(
            grupos,
            tipo=TIPO_PENDENCIA,
            codigo='NFE_SEM_ITENS',
            grupo='itens',
            mensagem='NF-e sem itens.',
        )

    soma_itens = Decimal('0')
    for idx, item in enumerate(itens, start=1):
        rotulo = f'Item {idx}'
        linha_total = _valor_linha_item(item)
        soma_itens += linha_total

        if not item.produto_id:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_SEM_PRODUTO',
                grupo='itens',
                mensagem=f'{rotulo} sem produto vinculado.',
                item_id=item.pk,
            )
        elif not _descricao_item(item):
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_SEM_DESCRICAO',
                grupo='itens',
                mensagem=f'{rotulo} sem descrição.',
                item_id=item.pk,
            )
        elif hasattr(item.produto, 'ativo') and not item.produto.ativo:
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='PRODUTO_INATIVO',
                grupo='itens',
                mensagem=f'{rotulo}: produto inativo no cadastro.',
                item_id=item.pk,
            )

        qtd = _dec(item.quantidade)
        if qtd <= 0:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_QTD_ZERO',
                grupo='itens',
                mensagem=f'{rotulo} com quantidade zero ou negativa.',
                item_id=item.pk,
            )

        if _dec(item.valor) < 0:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_VALOR_UNITARIO_NEGATIVO',
                grupo='itens',
                mensagem=f'{rotulo} com valor unitário negativo.',
                item_id=item.pk,
            )

        if linha_total < 0:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_VALOR_TOTAL_NEGATIVO',
                grupo='valores',
                mensagem=f'{rotulo} com valor total negativo.',
                item_id=item.pk,
            )

        un = _unidade_item(item)
        if not un:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_SEM_UNIDADE',
                grupo='itens',
                mensagem=f'{rotulo} sem unidade informada.',
                item_id=item.pk,
            )

        ncm = _ncm_item(item)
        if not ncm or len(_digits(ncm)) < 8:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_SEM_NCM',
                grupo='fiscal',
                mensagem=f'{rotulo} sem NCM informado.',
                item_id=item.pk,
            )

        cfop = _cfop_item(item)
        if not cfop:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_SEM_CFOP',
                grupo='fiscal',
                mensagem=f'{rotulo} sem CFOP informado.',
                item_id=item.pk,
            )
        elif uf_origem and uf_destino and len(cfop) >= 1:
            esperado_inter = uf_origem != uf_destino
            cfop_inter = cfop.startswith('6')
            cfop_intra = cfop.startswith('5')
            if esperado_inter and cfop_intra:
                _add(
                    grupos,
                    tipo=TIPO_ALERTA,
                    codigo='CFOP_POSSIVEL_INCOMPATIVEL_UF',
                    grupo='fiscal',
                    mensagem=(
                        f'{rotulo}: CFOP {cfop} parece operação interna, '
                        f'mas origem ({uf_origem}) e destino ({uf_destino}) são UFs diferentes.'
                    ),
                    item_id=item.pk,
                )
            elif not esperado_inter and cfop_inter:
                _add(
                    grupos,
                    tipo=TIPO_ALERTA,
                    codigo='CFOP_POSSIVEL_INCOMPATIVEL_UF',
                    grupo='fiscal',
                    mensagem=(
                        f'{rotulo}: CFOP {cfop} parece interestadual, '
                        f'mas origem e destino estão na mesma UF ({uf_origem}).'
                    ),
                    item_id=item.pk,
                )

        snap_f = item.snapshot_fiscal
        if not snap_f:
            tipo_snap = TIPO_PENDENCIA if de_faturamento else TIPO_ALERTA
            _add(
                grupos,
                tipo=tipo_snap,
                codigo='ITEM_SEM_SNAPSHOT_FISCAL',
                grupo='fiscal',
                mensagem=f'{rotulo} sem snapshot fiscal. Revise a origem fiscal antes da emissão.',
                item_id=item.pk,
            )
        else:
            origem = _text(snap_f.get('origem_regra_fiscal_saida'))
            if origem in ('CENARIO_SAIDA', 'LEGADO', 'REGRA_FISCAL_SAIDA'):
                tem_icms = any(
                    snap_f.get(k) not in (None, '')
                    for k in ('icms_saida_percentual', 'cst_icms', 'csosn', 'icms_cst')
                )
                if not tem_icms:
                    _add(
                        grupos,
                        tipo=TIPO_ALERTA,
                        codigo='ITEM_SEM_CST_ICMS_SNAPSHOT',
                        grupo='fiscal',
                        mensagem=f'{rotulo} sem CST/CSOSN ou alíquota ICMS no snapshot fiscal.',
                        item_id=item.pk,
                    )
            neg = _impostos_negativos(snap_f)
            if neg:
                _add(
                    grupos,
                    tipo=TIPO_PENDENCIA,
                    codigo='IMPOSTO_NEGATIVO',
                    grupo='fiscal',
                    mensagem=f'{rotulo} com imposto negativo no snapshot ({", ".join(neg)}).',
                    item_id=item.pk,
                )
            from apps.fiscal.nfe_cbenef_sp import pendencia_cbenef_sp_item

            msg_cbenef = pendencia_cbenef_sp_item(
                snap_f,
                uf_emitente=uf_origem,
                rotulo_item=rotulo,
            )
            if msg_cbenef:
                _add(
                    grupos,
                    tipo=TIPO_PENDENCIA,
                    codigo='CBENEF_SP_CST20_AUSENTE',
                    grupo='fiscal',
                    mensagem=msg_cbenef,
                    item_id=item.pk,
                )
            pendencias_difal = snap_f.get('difal_pendencias') or []
            if pendencias_difal:
                for msg_difal in pendencias_difal:
                    _add(
                        grupos,
                        tipo=TIPO_PENDENCIA,
                        codigo='DIFAL_PARAMETROS_INCOMPLETOS',
                        grupo='fiscal',
                        mensagem=str(msg_difal),
                        item_id=item.pk,
                    )
            from apps.fiscal.nfe_difal_calculo import validar_parametros_difal_regra
            from apps.fiscal.nfe_destinatario_fiscal import resolver_perfil_destinatario_nf
            from apps.regras_fiscais.models import RegraFiscalSaida

            perfil_nf = resolver_perfil_destinatario_nf(nf)
            regra_id = snap_f.get('regra_fiscal_saida_id')
            if (
                regra_id
                and uf_origem
                and uf_destino
                and uf_origem != uf_destino
                and perfil_nf.destinatario_contribuinte
                == RegraFiscalSaida.DestinatarioContribuinte.NAO_CONTRIBUINTE
                and perfil_nf.consumidor_final is True
                and not snap_f.get('difal')
                and not pendencias_difal
            ):
                try:
                    regra_difal = RegraFiscalSaida.objects.get(pk=int(regra_id))
                except (RegraFiscalSaida.DoesNotExist, TypeError, ValueError):
                    regra_difal = None
                if regra_difal and regra_difal.difal_aplicavel:
                    for msg_difal in validar_parametros_difal_regra(
                        regra_difal,
                        uf_destino=uf_destino,
                        nome_item=rotulo,
                    ):
                        _add(
                            grupos,
                            tipo=TIPO_PENDENCIA,
                            codigo='DIFAL_PARAMETROS_INCOMPLETOS',
                            grupo='fiscal',
                            mensagem=msg_difal,
                            item_id=item.pk,
                        )
                    if not validar_parametros_difal_regra(regra_difal, uf_destino=uf_destino):
                        _add(
                            grupos,
                            tipo=TIPO_PENDENCIA,
                            codigo='DIFAL_NAO_CALCULADO',
                            grupo='fiscal',
                            mensagem=(
                                f'{rotulo}: operação interestadual a não contribuinte exige DIFAL '
                                'calculado. Atualize os impostos da NF-e.'
                            ),
                            item_id=item.pk,
                        )
            from apps.fiscal.snapshot_fiscal_helpers import (
                get_reforma_tributaria_snapshot,
                reforma_configurada_no_snapshot,
            )

            if reforma_configurada_no_snapshot(snap_f):
                reforma = get_reforma_tributaria_snapshot(snap_f) or {}
                if not _text(reforma.get('cst_ibs_cbs')):
                    _add(
                        grupos,
                        tipo=TIPO_ALERTA,
                        codigo='REFORMA_SEM_CST_IBS_CBS',
                        grupo='reforma_tributaria',
                        mensagem=f'{rotulo}: reforma configurada sem CST IBS/CBS.',
                        item_id=item.pk,
                    )
                if not _text(reforma.get('classificacao_tributaria')):
                    _add(
                        grupos,
                        tipo=TIPO_ALERTA,
                        codigo='REFORMA_SEM_CLASSIFICACAO',
                        grupo='reforma_tributaria',
                        mensagem=f'{rotulo}: reforma configurada sem classificação tributária.',
                        item_id=item.pk,
                    )
                if not _text(reforma.get('aliquota_cbs')) and not _text(reforma.get('aliquota_ibs_estadual')):
                    _add(
                        grupos,
                        tipo=TIPO_ALERTA,
                        codigo='REFORMA_SEM_ALIQUOTAS',
                        grupo='reforma_tributaria',
                        mensagem=f'{rotulo}: alíquotas CBS/IBS não informadas no snapshot.',
                        item_id=item.pk,
                    )
                else:
                    from apps.fiscal.nfe_saida_reforma_calculo import (
                        reforma_valores_calculados,
                        status_reforma_snapshot,
                        tem_aliquota_reforma_configurada,
                    )

                    if tem_aliquota_reforma_configurada(reforma) and not reforma_valores_calculados(reforma):
                        _add(
                            grupos,
                            tipo=TIPO_ALERTA,
                            codigo='REFORMA_ALIQUOTA_SEM_VALOR',
                            grupo='reforma_tributaria',
                            mensagem=(
                                f'{rotulo}: Reforma Tributária configurada com alíquota, '
                                'mas sem valor calculado para o item.'
                            ),
                            item_id=item.pk,
                        )
                    elif status_reforma_snapshot(reforma) == 'SEM_CALCULO':
                        _add(
                            grupos,
                            tipo=TIPO_INFO,
                            codigo='REFORMA_SEM_CALCULO',
                            grupo='reforma_tributaria',
                            mensagem=f'{rotulo}: Reforma configurada sem alíquotas de cálculo.',
                            item_id=item.pk,
                        )
                    if not _text(reforma.get('formula_base_ibs_cbs')):
                        _add(
                            grupos,
                            tipo=TIPO_ALERTA,
                            codigo='REFORMA_BASE_SEM_FORMULA',
                            grupo='reforma_tributaria',
                            mensagem=f'{rotulo}: base IBS/CBS sem fórmula registrada no snapshot.',
                            item_id=item.pk,
                        )
                    st_base = _text(reforma.get('status_base_reforma'))
                    fonte_base = _text(reforma.get('fonte_regra_base_ibs_cbs')) or 'pendente'
                    if st_base == 'pendente_confirmacao' or fonte_base == 'pendente':
                        from apps.fiscal.reforma_tributaria.config import reforma_nfe_config

                        cfg_ref = reforma_nfe_config()
                        tipo_base = TIPO_ALERTA if cfg_ref.get('modo') != 'producao' else TIPO_PENDENCIA
                        _add(
                            grupos,
                            tipo=tipo_base,
                            codigo='REFORMA_BASE_FONTE_PENDENTE',
                            grupo='reforma_tributaria',
                            mensagem=(
                                f'{rotulo}: base IBS/CBS calculada com regra pendente de confirmação '
                                'oficial/contábil. Valide antes de transmitir em produção.'
                            ),
                            item_id=item.pk,
                        )
            elif snap_f.get('reforma_tributaria') or snap_f.get('ibs_cbs'):
                _add(
                    grupos,
                    tipo=TIPO_INFO,
                    codigo='REFORMA_BLOCO_PRESENTE',
                    grupo='reforma_tributaria',
                    mensagem=f'{rotulo}: bloco de reforma presente sem configuração normalizada.',
                    item_id=item.pk,
                )

        if de_faturamento and not item.item_faturamento_pedido_id:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='ITEM_SEM_VINCULO_FATURAMENTO',
                grupo='origem',
                mensagem=f'{rotulo} sem vínculo com item de faturamento.',
                item_id=item.pk,
            )

        esperado = qtd * _dec(item.valor)
        snap_c = item.snapshot_comercial or {}
        if snap_c.get('desconto') not in (None, ''):
            esperado -= _dec(snap_c['desconto'])
        if abs(linha_total - esperado) > TOLERANCIA_VALOR and qtd > 0:
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='ITEM_TOTAL_DIVERGENTE',
                grupo='valores',
                mensagem=(
                    f'{rotulo}: total {linha_total} diverge de quantidade × valor unitário '
                    f'({esperado}), tolerância {TOLERANCIA_VALOR}.'
                ),
                item_id=item.pk,
            )

    # --- Valores NF ---
    total_nf = _dec(nf.valor_total)
    if total_nf <= 0 and itens:
        _add(
            grupos,
            tipo=TIPO_PENDENCIA,
            codigo='NFE_TOTAL_ZERO',
            grupo='valores',
            mensagem='Valor total da NF-e é zero ou negativo.',
        )
    if itens and abs(soma_itens - total_nf) > TOLERANCIA_VALOR:
        _add(
            grupos,
            tipo=TIPO_PENDENCIA,
            codigo='NFE_TOTAL_DIVERGENTE_ITENS',
            grupo='valores',
            mensagem=(
                f'Soma dos itens ({soma_itens}) diverge do total da NF-e ({total_nf}); '
                f'tolerância {TOLERANCIA_VALOR}.'
            ),
        )

    desconto_total = sum(_dec((i.snapshot_comercial or {}).get('desconto', 0)) for i in itens)
    bruto = sum(_dec(i.quantidade) * _dec(i.valor) for i in itens)
    if desconto_total > bruto and bruto > 0:
        _add(
            grupos,
            tipo=TIPO_PENDENCIA,
            codigo='DESCONTO_MAIOR_BRUTO',
            grupo='valores',
            mensagem='Desconto total maior que o valor bruto dos itens.',
        )

    # --- Estoque (somente informativo) ---
    modo = nf.modo_atendimento_estoque or NFeSaida.ModoAtendimentoEstoque.IMEDIATO
    if modo == NFeSaida.ModoAtendimentoEstoque.IMEDIATO:
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='ESTOQUE_VALIDACAO_FUTURA',
            grupo='estoque',
            mensagem=(
                'Modo IMEDIATO: validação de estoque/corrida será aplicada na etapa de emissão/baixa.'
            ),
        )
        _add(
            grupos,
            tipo=TIPO_ALERTA,
            codigo='ESTOQUE_EMISSAO_FUTURA',
            grupo='estoque',
            mensagem='Emissão futura poderá exigir estoque/corrida conforme regra atual do sistema.',
        )
    else:
        _add(
            grupos,
            tipo=TIPO_ALERTA,
            codigo='ESTOQUE_ANTECIPADO_FUTURO',
            grupo='estoque',
            mensagem=(
                'Modo ANTECIPADO: emissão futura poderá gerar compromisso/AtendimentoEstoque '
                'em etapa posterior.'
            ),
        )
    _add(
        grupos,
        tipo=TIPO_INFO,
        codigo='ESTOQUE_NAO_MOVIMENTADO',
        grupo='estoque',
        mensagem='Esta validação não movimenta estoque nem cria AtendimentoEstoque.',
    )

    # --- Transporte ---
    from apps.fiscal.nfe_transporte_validacao import validar_coerencia_transporte_nfe

    for chk in validar_coerencia_transporte_nfe(nf):
        _add(
            grupos,
            tipo=chk['tipo'],
            codigo=chk['codigo'],
            grupo='transporte',
            mensagem=chk['mensagem'],
        )
    if nf.faturamento_pedido_venda_id or nf.pedido_venda_id:
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='ORIGEM_COMERCIAL_TRAVADA',
            grupo='origem',
            mensagem='NF-e originada de pedido/faturamento: origem comercial e itens travados.',
        )

    # --- Pedido do cliente ---
    if not _text(nf.pedido_cliente_numero):
        _add(
            grupos,
            tipo=TIPO_INFO,
            codigo='PEDIDO_CLIENTE_NAO_INFORMADO',
            grupo='pedido_cliente',
            mensagem='Pedido do cliente (OC) não informado — alerta informativo.',
        )

    # --- Reforma Tributária no XML (snapshot calculado → grupos IBSCBS) ---
    from apps.fiscal.nfe_saida_reforma_calculo import status_reforma_snapshot
    from apps.fiscal.snapshot_fiscal_helpers import get_reforma_tributaria_snapshot

    itens_com_reforma = [
        it
        for it in itens
        if status_reforma_snapshot(get_reforma_tributaria_snapshot(it.snapshot_fiscal)) == 'CALCULADA'
    ]
    if (
        itens_com_reforma
        and not _nf_autorizada_com_xml_historico(nf)
        and validar_reforma_xml
    ):
        from apps.fiscal.reforma_tributaria.validacoes import reforma_deve_serializar_no_xml

        if reforma_deve_serializar_no_xml():
            try:
                from apps.fiscal.nfe_saida_preview import gerar_dados_preview_nfe_saida
                from apps.fiscal.nfe_saida_xml_nfelib import montar_tnfe_oficial, serializar_tnfe

                dados_xml = gerar_dados_preview_nfe_saida(nf, incluir_validacao_emissao=False)
                if not dados_xml.get('bloqueado'):
                    for linha in dados_xml.get('itens') or []:
                        item_id = linha.get('item_id')
                        if item_id:
                            item_db = next((i for i in itens if i.pk == item_id), None)
                            if item_db is not None:
                                linha['snapshot_fiscal'] = item_db.snapshot_fiscal or {}
                    tnfe = montar_tnfe_oficial(dados_xml, nfe_saida=nf)
                    xml_check = serializar_tnfe(tnfe, pretty=False)
                    from apps.fiscal.reforma_tributaria.xml import validar_reforma_serializada_em_xml

                    for chk in validar_reforma_serializada_em_xml(
                        xml_check,
                        itens=dados_xml.get('itens') or [],
                    ):
                        _add(
                            grupos,
                            tipo=chk['tipo'],
                            codigo=chk['codigo'],
                            grupo='reforma_tributaria',
                            mensagem=chk['mensagem'],
                        )
            except Exception as exc:
                _add(
                    grupos,
                    tipo=TIPO_PENDENCIA,
                    codigo='REFORMA_XML_GERACAO_FALHOU',
                    grupo='reforma_tributaria',
                    mensagem=f'Não foi possível validar Reforma no XML: {exc}',
                )

    # --- Higienização XML transmissão (modo completo) ---
    if not modo_leve and incluir_higienizacao_xml:
        from apps.fiscal.nfe_operacao_fiscal_indicadores import montar_indicadores_fiscais_payload
        from apps.fiscal.nfe_xml_higienizacao import validar_higienizacao_xml_transmissao

        ind_payload = montar_indicadores_fiscais_payload(nf)
        if not ind_payload['indicadores_fiscais_confirmados']:
            _add(
                grupos,
                tipo=TIPO_PENDENCIA,
                codigo='INDICADORES_NAO_CONFIRMADOS',
                grupo='higienizacao_xml',
                mensagem='Confirme consumidor final (indFinal) e indicador de presença (indPres) na conferência.',
            )
        elif ind_payload['ind_final'] == '1' and nf.cliente_id and _text(getattr(nf.cliente, 'ie', None)):
            _add(
                grupos,
                tipo=TIPO_ALERTA,
                codigo='INDFINAL_CONSUMIDOR_COM_IE',
                grupo='higienizacao_xml',
                mensagem=(
                    'Destinatário contribuinte com IE informado. '
                    'Confirme se a operação é para consumidor final (indFinal=1).'
                ),
            )

        if nf.chave_acesso and ind_payload['indicadores_fiscais_confirmados']:
            try:
                from apps.fiscal.nfe_xml_transmissao import gerar_xml_transmissao_homologacao

                xml_tx = gerar_xml_transmissao_homologacao(nf).decode('utf-8')
                for chk in validar_higienizacao_xml_transmissao(
                    xml_tx,
                    nfe_saida=nf,
                    chave_esperada=nf.chave_acesso,
                ):
                    _add(
                        grupos,
                        tipo=chk['tipo'],
                        codigo=chk['codigo'],
                        grupo=chk.get('grupo') or 'higienizacao_xml',
                        mensagem=chk['mensagem'],
                    )
            except Exception as exc:
                _add(
                    grupos,
                    tipo=TIPO_PENDENCIA,
                    codigo='XML_TRANSMISSAO_GERACAO_FALHOU',
                    grupo='higienizacao_xml',
                    mensagem=f'Não foi possível gerar/validar XML de transmissão: {exc}',
                )
        elif not nf.chave_acesso:
            _add(
                grupos,
                tipo=TIPO_INFO,
                codigo='XML_TRANSMISSAO_AGUARDA_NUMERACAO',
                grupo='higienizacao_xml',
                mensagem='Reserve a numeração para validar o XML de transmissão completo.',
            )

    # --- Totais ---
    soma_itens = sum(_dec(it.quantidade) * _dec(it.valor) for it in itens)
    if abs(soma_itens - _dec(nf.valor_total)) > TOLERANCIA_VALOR and itens:
        _add(
            grupos,
            tipo=TIPO_ALERTA,
            codigo='TOTAL_NF_DIVERGENTE_ITENS',
            grupo='totais',
            mensagem=(
                f'Total da NF ({nf.valor_total}) diverge da soma dos itens ({soma_itens}), '
                f'tolerância {TOLERANCIA_VALOR}.'
            ),
        )

    total_pendencias = sum(
        1 for g in grupos.values() for it in g if it.get('tipo') == TIPO_PENDENCIA
    )
    total_alertas = sum(1 for g in grupos.values() for it in g if it.get('tipo') == TIPO_ALERTA)

    if total_pendencias > 0:
        status_prontidao = STATUS_COM_PENDENCIAS
        pode_emitir = False
        mensagens = ['Existem pendências antes da emissão.']
    elif total_alertas > 0:
        status_prontidao = STATUS_COM_ALERTAS
        pode_emitir = True
        mensagens = [
            'NF-e sem pendências bloqueantes; revise os alertas antes da emissão futura.',
        ]
    else:
        status_prontidao = STATUS_PRONTA
        pode_emitir = True
        mensagens = [
            'NF-e rascunho sem pendências bloqueantes. A transmissão será implementada em etapa posterior.',
        ]

    return _montar_resultado(
        nf,
        grupos,
        status_prontidao=status_prontidao,
        pode_emitir=pode_emitir,
        mensagens=mensagens,
    )
