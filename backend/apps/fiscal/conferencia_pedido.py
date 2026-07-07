"""Vínculo conferência NF-e histórica ↔ item do pedido de compra (Fase 2.1)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict

from apps.comercial.models import ItemPedidoCompra
from apps.fiscal.models import ItemNFeEntradaConferencia, NFeEntradaConferencia
from apps.fiscal.nfe_entrada_data_entrada import MSG_DATA_ENTRADA_OBRIGATORIA
from apps.fiscal.rastreabilidade_conferencia import alertas_splits_parciais, tem_rastreabilidade_item
from apps.regras_fiscais.entrada_fiscal import MSG_SEM_REGRA_FISCAL_ENTRADA

STATUS_ELEGIBILIDADE_APTO = 'APTO'
STATUS_ELEGIBILIDADE_APTO_COM_ALERTA = 'APTO_COM_ALERTA'
STATUS_ELEGIBILIDADE_BLOQUEADO = 'BLOQUEADO'
STATUS_ELEGIBILIDADE_NAO_MOVIMENTA = 'NAO_MOVIMENTA'

LABEL_ELEGIBILIDADE_ESTOQUE: dict[str, str] = {
    STATUS_ELEGIBILIDADE_APTO: 'Apto para estoque',
    STATUS_ELEGIBILIDADE_APTO_COM_ALERTA: 'Apto com alerta',
    STATUS_ELEGIBILIDADE_BLOQUEADO: 'Bloqueado',
    STATUS_ELEGIBILIDADE_NAO_MOVIMENTA: 'Não movimenta estoque',
}


class ElegibilidadeEstoqueDict(TypedDict):
    status: str
    label: str
    mensagens: list[str]
    motivos: list[str]
    movimenta_estoque: bool | None
    exige_certificado_fornecedor: bool
    tem_certificado_fornecedor: bool
    tem_rastreabilidade_tecnica: bool


class ResumoElegibilidadeEstoqueDict(TypedDict):
    aptos: int
    aptos_com_alerta: int
    bloqueados: int
    nao_movimentam: int


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


SCORE_SUGESTAO_PENALIDADE_JA_VINCULADO = -1000
SCORE_SUGESTAO_MINIMO_LISTAGEM = 1
SCORE_SUGESTAO_ALTO_UI = 40


def _norm_unit(value: str) -> str:
    return (value or '').strip().upper()


def _codigo_produto_pedido(item_pc: ItemPedidoCompra) -> str:
    snap = item_pc.snapshot_produto if isinstance(item_pc.snapshot_produto, dict) else {}
    if snap.get('codigo_completo'):
        return str(snap['codigo_completo']).strip()
    prod = item_pc.produto
    return prod.codigo_completo.strip() if prod else ''


def _descricao_produto_pedido(item_pc: ItemPedidoCompra) -> str:
    snap = item_pc.snapshot_produto if isinstance(item_pc.snapshot_produto, dict) else {}
    if snap.get('descricao'):
        return str(snap['descricao']).strip()
    prod = item_pc.produto
    return prod.descricao.strip() if prod else ''


def _descricao_similar(nf_desc: str, pedido_desc: str) -> bool:
    a = nf_desc.upper().strip()
    b = pedido_desc.upper().strip()
    if not a or not b:
        return False
    prefix = a[:32]
    return prefix in b or b in a or a[:16] in b


def _quantidade_proxima(q_nf, q_pedido, *, tolerancia_relativa: Decimal = Decimal('0.01')) -> bool:
    qn = _dec(q_nf)
    qp = _dec(q_pedido)
    if qp == 0:
        return qn == 0
    return abs(qn - qp) <= max(Decimal('0.001'), abs(qp) * tolerancia_relativa)


def _valor_proximo(v_nf, v_pedido, *, tolerancia: Decimal = Decimal('0.05')) -> bool:
    vn = _dec(v_nf)
    vp = _dec(v_pedido)
    return abs(vn - vp) <= tolerancia


def _score_item_pedido_para_linha(
    item_conf: ItemNFeEntradaConferencia,
    item_pc: ItemPedidoCompra,
    *,
    vinculados_outras_linhas: set[int],
) -> tuple[int, list[str]]:
    score = 0
    motivos: list[str] = []

    if item_pc.id in vinculados_outras_linhas:
        score += SCORE_SUGESTAO_PENALIDADE_JA_VINCULADO
        motivos.append('item_pedido_ja_vinculado_outra_linha')

    prod_json = item_conf.item_nfe_historico.prod_json or {}
    codigo_nf = str(prod_json.get('cProd') or '').strip()
    descricao_nf = str(prod_json.get('xProd') or '').strip()
    codigo_pedido = _codigo_produto_pedido(item_pc)
    descricao_pedido = _descricao_produto_pedido(item_pc)

    if item_conf.produto_id and item_pc.produto_id == item_conf.produto_id:
        score += 40
        motivos.append('produto_igual')

    if codigo_nf and codigo_pedido:
        cn = codigo_nf.upper()
        cp = codigo_pedido.upper()
        if cn == cp or cn in cp or cp in cn:
            score += 25
            motivos.append('codigo_compativel')

    if _descricao_similar(descricao_nf, descricao_pedido):
        score += 15
        motivos.append('descricao_similar')

    q_pedido = item_pc.quantidade_negociada or item_pc.quantidade
    if _quantidade_proxima(item_conf.quantidade_nf, q_pedido):
        score += 10
        motivos.append('quantidade_proxima')

    if _norm_unit(item_conf.unidade_nf) and _norm_unit(item_pc.unidade_negociada):
        if _norm_unit(item_conf.unidade_nf) == _norm_unit(item_pc.unidade_negociada):
            score += 8
            motivos.append('unidade_igual')

    if _valor_proximo(item_conf.valor_unitario_nf, item_pc.valor_unitario):
        score += 5
        motivos.append('valor_unitario_proximo')

    return score, motivos


def sugerir_itens_pedido_linha(
    item_conf: ItemNFeEntradaConferencia,
    itens_pedido: list[ItemPedidoCompra],
    *,
    vinculados_outras_linhas: set[int] | None = None,
    limite: int = 3,
) -> list[dict]:
    """Top sugestões de item do pedido para uma linha da conferência (não persiste vínculo)."""
    vinculados = vinculados_outras_linhas or set()
    candidatos: list[dict] = []
    for item_pc in itens_pedido:
        score, motivos = _score_item_pedido_para_linha(
            item_conf,
            item_pc,
            vinculados_outras_linhas=vinculados,
        )
        if score < SCORE_SUGESTAO_MINIMO_LISTAGEM:
            continue
        q_pedido = item_pc.quantidade_negociada or item_pc.quantidade
        candidatos.append(
            {
                'id': item_pc.id,
                'produto_codigo': _codigo_produto_pedido(item_pc),
                'descricao': _descricao_produto_pedido(item_pc),
                'quantidade': float(q_pedido),
                'unidade': _norm_unit(item_pc.unidade_negociada),
                'valor_unitario': float(item_pc.valor_unitario or 0),
                'score': score,
                'motivos': motivos,
            },
        )
    candidatos.sort(key=lambda row: (-row['score'], row['id']))
    return candidatos[:limite]


def build_snapshot_pedido(item_pc: ItemPedidoCompra) -> dict:
    prod = item_pc.produto
    snap_prod = item_pc.snapshot_produto if isinstance(item_pc.snapshot_produto, dict) else {}
    return {
        'item_pedido_compra_id': item_pc.id,
        'pedido_id': item_pc.pedido_id,
        'pedido_numero': item_pc.pedido.numero if item_pc.pedido_id else '',
        'produto_id': item_pc.produto_id,
        'codigo': str(snap_prod.get('codigo_completo') or (prod.codigo_completo if prod else '')),
        'descricao': str(snap_prod.get('descricao') or (prod.descricao if prod else '')),
        'quantidade': str(item_pc.quantidade_negociada or item_pc.quantidade or 0),
        'unidade': (item_pc.unidade_negociada or '').upper(),
        'valor_unitario': str(item_pc.valor_unitario or 0),
        'valor_total_item': str(item_pc.valor_total_item or 0),
    }


def item_pedido_resumo_dict(item_conf: ItemNFeEntradaConferencia) -> dict | None:
    if not item_conf.item_pedido_compra_id:
        return None
    snap = item_conf.snapshot_pedido if isinstance(item_conf.snapshot_pedido, dict) and item_conf.snapshot_pedido else None
    item_pc = item_conf.item_pedido_compra
    if snap:
        return {
            'pedido_numero': snap.get('pedido_numero', ''),
            'produto_id': snap.get('produto_id'),
            'codigo': snap.get('codigo', ''),
            'descricao': snap.get('descricao', ''),
            'quantidade': snap.get('quantidade', ''),
            'unidade': snap.get('unidade', ''),
            'valor_unitario': snap.get('valor_unitario', ''),
        }
    if not item_pc:
        return None
    prod = item_pc.produto
    return {
        'pedido_numero': item_pc.pedido.numero if item_pc.pedido_id else '',
        'produto_id': item_pc.produto_id,
        'codigo': prod.codigo_completo if prod else '',
        'descricao': prod.descricao if prod else '',
        'quantidade': str(item_pc.quantidade_negociada or item_pc.quantidade or 0),
        'unidade': (item_pc.unidade_negociada or '').upper(),
        'valor_unitario': str(item_pc.valor_unitario or 0),
    }


def _soma_quantidade_nf_vinculada_item_pedido(
    conferencia: NFeEntradaConferencia,
    item_pedido_id: int,
) -> Decimal:
    """Soma quantidade_nf das linhas ativas vinculadas ao item do pedido nesta conferência."""
    total = Decimal('0')
    for linha in conferencia.itens.all():
        if linha.status == ItemNFeEntradaConferencia.Status.IGNORADO:
            continue
        if linha.item_pedido_compra_id == item_pedido_id:
            total += _dec(linha.quantidade_nf)
    return total


def _agregar_vinculos_por_item_pedido(
    linhas: list[ItemNFeEntradaConferencia],
) -> dict[int, dict]:
    """Mapa item_pedido_id → quantidade_nf somada e linhas vinculadas (exceto IGNORADO)."""
    agg: dict[int, dict] = {}
    for linha in linhas:
        if linha.status == ItemNFeEntradaConferencia.Status.IGNORADO:
            continue
        pid = linha.item_pedido_compra_id
        if not pid:
            continue
        bucket = agg.setdefault(pid, {'quantidade_nf': Decimal('0'), 'linhas': []})
        bucket['quantidade_nf'] += _dec(linha.quantidade_nf)
        bucket['linhas'].append(
            {
                'id': linha.id,
                'n_item': linha.item_nfe_historico.n_item,
            },
        )
    return agg


def _status_quantitativo_item_pedido(q_pedido: Decimal, q_nf_vinculada: Decimal) -> str:
    if q_nf_vinculada <= 0:
        return 'nao_vinculado'
    if q_nf_vinculada > q_pedido and not _quantidade_proxima(q_nf_vinculada, q_pedido):
        return 'excedente'
    if q_nf_vinculada < q_pedido and not _quantidade_proxima(q_nf_vinculada, q_pedido):
        return 'parcial'
    return 'completo'


def _status_saldo_global_pedido(q_pedido: Decimal, q_total_conferida: Decimal) -> str:
    if q_total_conferida <= 0:
        return 'pendente'
    if q_total_conferida > q_pedido and not _quantidade_proxima(q_total_conferida, q_pedido):
        return 'excedente'
    if _quantidade_proxima(q_total_conferida, q_pedido):
        return 'completo'
    return 'parcial'


def _coletar_vinculos_globais_por_item_pedido(
    pedido_compra_id: int,
    *,
    somente_baixadas: bool = True,
) -> dict[int, dict[int, dict]]:
    """
    item_pedido_id → conferencia_id → {quantidade, nf_numero, nf_serie, conferencia_id}.
    Por padrão considera apenas conferências com baixa de pedido aplicada.
    """
    linhas_qs = ItemNFeEntradaConferencia.objects.filter(
        conferencia__pedido_compra_id=pedido_compra_id,
        item_pedido_compra_id__isnull=False,
    ).exclude(status=ItemNFeEntradaConferencia.Status.IGNORADO)
    if somente_baixadas:
        linhas_qs = linhas_qs.filter(conferencia__pedido_baixa_aplicado_em__isnull=False)
    linhas_qs = linhas_qs.select_related('conferencia__nf_entrada_historica')
    por_item: dict[int, dict[int, dict]] = {}
    for linha in linhas_qs:
        pid = linha.item_pedido_compra_id
        cid = linha.conferencia_id
        nf = linha.conferencia.nf_entrada_historica
        bucket_conf = por_item.setdefault(pid, {}).setdefault(
            cid,
            {
                'conferencia_id': cid,
                'nf_numero': nf.numero if nf else '',
                'nf_serie': nf.serie if nf else '',
                'quantidade': Decimal('0'),
            },
        )
        bucket_conf['quantidade'] += _dec(linha.quantidade_pedido_baixada or linha.quantidade_nf)
    return por_item


def montar_saldo_pedido_global_conferencia(
    conferencia: NFeEntradaConferencia,
    itens_pedido: list[ItemPedidoCompra],
    *,
    linhas_atual: list[ItemNFeEntradaConferencia] | None = None,
) -> list[dict]:
    """Saldo acumulado por item do pedido em todas as conferências vinculadas ao mesmo pedido."""
    if not conferencia.pedido_compra_id:
        return []

    linhas_atual = linhas_atual if linhas_atual is not None else list(conferencia.itens.all())
    agg_atual = _agregar_vinculos_por_item_pedido(linhas_atual)
    por_item_global = _coletar_vinculos_globais_por_item_pedido(conferencia.pedido_compra_id)
    conferencia_atual_id = conferencia.id

    saldo_global: list[dict] = []
    for item_pc in itens_pedido:
        q_pedido = _dec(item_pc.quantidade_negociada or item_pc.quantidade)
        vinculo_atual = agg_atual.get(item_pc.id, {'quantidade_nf': Decimal('0')})
        q_nf_atual = vinculo_atual['quantidade_nf']

        conferencias_map = por_item_global.get(item_pc.id, {})
        q_total = Decimal('0')
        conferencias_relacionadas: list[dict] = []
        for _cid, meta in sorted(conferencias_map.items(), key=lambda x: (x[1]['nf_numero'], x[0])):
            q_conf = meta['quantidade']
            q_total += q_conf
            conferencias_relacionadas.append(
                {
                    'conferencia_id': meta['conferencia_id'],
                    'nf_numero': meta['nf_numero'],
                    'nf_serie': meta['nf_serie'],
                    'quantidade': float(q_conf),
                    'atual': meta['conferencia_id'] == conferencia_atual_id,
                },
            )

        q_outras = q_total - q_nf_atual
        if q_outras < 0:
            q_outras = Decimal('0')
        saldo_pedido = q_pedido - q_total
        status = _status_saldo_global_pedido(q_pedido, q_total)

        saldo_global.append(
            {
                'item_pedido_id': item_pc.id,
                'produto_codigo': _codigo_produto_pedido(item_pc),
                'descricao': _descricao_produto_pedido(item_pc),
                'quantidade_pedido': float(q_pedido),
                'quantidade_nf_atual': float(q_nf_atual),
                'quantidade_outras_nfs': float(q_outras),
                'quantidade_total_conferida': float(q_total),
                'saldo_pedido': float(saldo_pedido),
                'status_saldo': status,
                'conferencias_relacionadas': conferencias_relacionadas,
            },
        )
    return saldo_global


def _alertas_quantitativos_item_pedido(
    *,
    status: str,
    linhas_vinculadas: list[dict],
) -> list[str]:
    alertas: list[str] = []
    if len(linhas_vinculadas) > 1:
        alertas.append('item_pedido_duplicado_na_nf')
    if status == 'parcial':
        alertas.append('quantidade_nf_menor_que_pedido')
    elif status == 'excedente':
        alertas.append('quantidade_nf_maior_que_pedido')
    return alertas


def montar_resumo_quantitativo_pedido_conferencia(
    linhas: list[ItemNFeEntradaConferencia],
    itens_pedido: list[ItemPedidoCompra],
) -> list[dict]:
    """Resumo por item do pedido na conferência atual (somente leitura)."""
    agg = _agregar_vinculos_por_item_pedido(linhas)
    resumo: list[dict] = []
    for item_pc in itens_pedido:
        q_pedido = _dec(item_pc.quantidade_negociada or item_pc.quantidade)
        vinculo = agg.get(item_pc.id, {'quantidade_nf': Decimal('0'), 'linhas': []})
        q_nf = vinculo['quantidade_nf']
        saldo = q_pedido - q_nf
        linhas_vinculadas = vinculo['linhas']
        status = _status_quantitativo_item_pedido(q_pedido, q_nf)
        resumo.append(
            {
                'item_pedido_id': item_pc.id,
                'produto_codigo': _codigo_produto_pedido(item_pc),
                'descricao': _descricao_produto_pedido(item_pc),
                'quantidade_pedido': float(q_pedido),
                'quantidade_nf_vinculada': float(q_nf),
                'saldo_na_nf': float(saldo),
                'status_quantitativo': status,
                'linhas_vinculadas': linhas_vinculadas,
                'alertas': _alertas_quantitativos_item_pedido(
                    status=status,
                    linhas_vinculadas=linhas_vinculadas,
                ),
            },
        )
    return resumo


def calcular_divergencias_item_conferencia(
    item_conf: ItemNFeEntradaConferencia,
    conferencia: NFeEntradaConferencia,
) -> tuple[list[str], list[str]]:
    divergencias: list[str] = []
    alertas: list[str] = []

    if conferencia.pedido_compra_id and item_conf.item_pedido_compra_id:
        item_pc = item_conf.item_pedido_compra
        if item_pc:
            if item_conf.produto_id and item_pc.produto_id != item_conf.produto_id:
                divergencias.append('produto_diferente_pedido')
            if (item_pc.unidade_negociada or '').upper() != (item_conf.unidade_nf or '').upper():
                divergencias.append('unidade_diferente')
            q_pedido = _dec(item_pc.quantidade_negociada or item_pc.quantidade)
            soma_nf = _soma_quantidade_nf_vinculada_item_pedido(conferencia, item_pc.id)
            if not _quantidade_proxima(soma_nf, q_pedido):
                divergencias.append('quantidade_diferente')
            if _dec(item_pc.valor_unitario) != _dec(item_conf.valor_unitario_nf):
                divergencias.append('preco_diferente')

    if item_conf.produto_id:
        ncm_nf = ((item_conf.item_nfe_historico.prod_json or {}).get('NCM') or '').strip()
        ncm_produto = item_conf.produto.get_ncm_efetivo_codigo() if item_conf.produto_id else ''
        if ncm_nf and ncm_produto and ncm_nf != ncm_produto:
            divergencias.append('ncm_divergente_nf_produto')
            alertas.append('NCM da NF-e difere do NCM efetivo do produto. Confira antes de preparar estoque.')

    return divergencias, alertas


def calcular_status_operacional_item_conferencia(item_conf: ItemNFeEntradaConferencia) -> str:
    """Status operacional da linha (exceto IGNORADO definido manualmente)."""
    if item_conf.status == ItemNFeEntradaConferencia.Status.IGNORADO:
        return item_conf.status
    if not item_conf.produto_id:
        return ItemNFeEntradaConferencia.Status.PENDENTE_PRODUTO
    if item_conf.divergencias:
        return ItemNFeEntradaConferencia.Status.DIVERGENTE
    if item_conf.item_pedido_compra_id:
        return ItemNFeEntradaConferencia.Status.CONFERIDO
    return ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO


def validar_preparar_estoque_conferencia(
    conferencia: NFeEntradaConferencia,
    itens: list[ItemNFeEntradaConferencia],
) -> tuple[list[str], bool]:
    """Pendências que impedem preparar estoque (pedido de compra é opcional)."""
    pendencias: list[str] = []
    statuses_ok = {
        ItemNFeEntradaConferencia.Status.CONFERIDO,
        ItemNFeEntradaConferencia.Status.PRODUTO_VINCULADO,
        ItemNFeEntradaConferencia.Status.IGNORADO,
    }
    if conferencia.divergencias_aceitas:
        statuses_ok.add(ItemNFeEntradaConferencia.Status.DIVERGENTE)

    if not conferencia.data_entrada:
        pendencias.insert(0, MSG_DATA_ENTRADA_OBRIGATORIA)

    faltam_produto: list[int] = []
    for it in itens:
        n_item = it.item_nfe_historico.n_item
        if it.status == ItemNFeEntradaConferencia.Status.IGNORADO:
            if not (it.motivo_ignorado or '').strip():
                pendencias.append(f'Item {n_item}: motivo de ignorado obrigatório.')
            continue
        if not it.produto_id:
            faltam_produto.append(n_item)
            continue
        if it.status not in statuses_ok:
            pendencias.append(
                f'Item {n_item}: salve a conferência para recalcular o status antes de preparar.',
            )

    if faltam_produto:
        pendencias.insert(
            0,
            'Vincule o produto cadastrado nos itens antes de preparar.',
        )

    has_div = any(bool(i.divergencias) for i in itens if i.status != ItemNFeEntradaConferencia.Status.IGNORADO)
    if has_div and not conferencia.divergencias_aceitas:
        pendencias.append('Existem divergências pendentes sem aceite.')

    from apps.regras_fiscais.entrada_fiscal import validar_bloqueio_fiscal_preparar_conferencia
    from apps.regras_fiscais.regras_fiscais_minimas import validar_regra_fiscal_entrada_para_uso

    uso_entrada = validar_regra_fiscal_entrada_para_uso()
    bloqueio_config_entrada = False
    if not uso_entrada['valida']:
        bloqueio_config_entrada = True
        pendencias.insert(0, uso_entrada['bloqueios'][0])
        if len(uso_entrada['bloqueios']) > 1:
            pendencias.insert(1, uso_entrada['bloqueios'][1])

    bloqueios_fiscais = validar_bloqueio_fiscal_preparar_conferencia(conferencia, itens)
    if bloqueios_fiscais:
        pendencias.append('Itens bloqueados por regra fiscal de entrada (severidade BLOQUEIO):')
        pendencias.extend(bloqueios_fiscais)

    return pendencias, bool(bloqueios_fiscais) or bloqueio_config_entrada


def carregar_certificados_fornecedor_por_item_conferencia(
    item_conferencia_ids: list[int],
) -> dict[int, dict[str, bool]]:
    """Mapa item_conferencia_id → {registrado, rascunho} (CF ativo, não cancelado)."""
    if not item_conferencia_ids:
        return {}
    from apps.qualidade.models import CertificadoFornecedorEntrada, ItemCertificadoFornecedorEntrada

    resultado: dict[int, dict[str, bool]] = {
        iid: {'registrado': False, 'rascunho': False} for iid in item_conferencia_ids
    }
    qs = ItemCertificadoFornecedorEntrada.objects.filter(
        item_conferencia_id__in=item_conferencia_ids,
        ativo=True,
    ).select_related('certificado_fornecedor')
    for item_cf in qs:
        ic_id = item_cf.item_conferencia_id
        if not ic_id or ic_id not in resultado:
            continue
        status = (item_cf.certificado_fornecedor.status or '').strip().lower()
        if status == CertificadoFornecedorEntrada.Status.CANCELADO:
            continue
        if status == CertificadoFornecedorEntrada.Status.REGISTRADO:
            resultado[ic_id]['registrado'] = True
        elif status == CertificadoFornecedorEntrada.Status.RASCUNHO:
            resultado[ic_id]['rascunho'] = True
    return resultado


def _montar_elegibilidade_estoque(
    status: str,
    *,
    mensagens: list[str],
    motivos: list[str],
    movimenta_estoque: bool | None,
    exige_certificado_fornecedor: bool,
    tem_certificado_fornecedor: bool,
    tem_rastreabilidade_tecnica: bool,
) -> ElegibilidadeEstoqueDict:
    return {
        'status': status,
        'label': LABEL_ELEGIBILIDADE_ESTOQUE.get(status, status),
        'mensagens': mensagens,
        'motivos': motivos,
        'movimenta_estoque': movimenta_estoque,
        'exige_certificado_fornecedor': exige_certificado_fornecedor,
        'tem_certificado_fornecedor': tem_certificado_fornecedor,
        'tem_rastreabilidade_tecnica': tem_rastreabilidade_tecnica,
    }


def avaliar_elegibilidade_estoque_item_conferencia(
    item_conf: ItemNFeEntradaConferencia,
    *,
    resultado_fiscal: dict[str, Any],
    divergencias_aceitas: bool,
    certificado_fornecedor_info: dict[str, bool] | None = None,
) -> ElegibilidadeEstoqueDict:
    """
    Checklist read-only de elegibilidade para futura aplicação de estoque (Fase 3.5).
    Não altera estoque nem bloqueia preparar além da Fase 3.4.
    """
    cert_info = certificado_fornecedor_info or {}
    tem_cf_registrado = bool(cert_info.get('registrado'))
    tem_cf_rascunho = bool(cert_info.get('rascunho'))
    movimenta = resultado_fiscal.get('movimenta_estoque')
    exige_cf = bool(resultado_fiscal.get('exige_certificado_fornecedor'))
    tem_rastreabilidade = tem_rastreabilidade_item(item_conf)

    if item_conf.status == ItemNFeEntradaConferencia.Status.IGNORADO:
        return _montar_elegibilidade_estoque(
            STATUS_ELEGIBILIDADE_NAO_MOVIMENTA,
            mensagens=['Linha ignorada na conferência.'],
            motivos=['linha_ignorada'],
            movimenta_estoque=movimenta,
            exige_certificado_fornecedor=exige_cf,
            tem_certificado_fornecedor=tem_cf_registrado,
            tem_rastreabilidade_tecnica=tem_rastreabilidade,
        )

    if movimenta is False:
        return _montar_elegibilidade_estoque(
            STATUS_ELEGIBILIDADE_NAO_MOVIMENTA,
            mensagens=['Regra fiscal indica que este item não movimenta estoque.'],
            motivos=['nao_movimenta_estoque'],
            movimenta_estoque=False,
            exige_certificado_fornecedor=exige_cf,
            tem_certificado_fornecedor=tem_cf_registrado,
            tem_rastreabilidade_tecnica=tem_rastreabilidade,
        )

    mensagens: list[str] = []
    motivos: list[str] = []
    bloqueado = False

    if not item_conf.produto_id:
        mensagens.append('Vincule o produto cadastrado antes de aplicar estoque.')
        motivos.append('sem_produto')
        bloqueado = True

    if (resultado_fiscal.get('status') or '').upper() == 'BLOQUEADO':
        mensagens.append('Item bloqueado por regra fiscal.')
        motivos.append('fiscal_bloqueio')
        bloqueado = True

    if bool(item_conf.divergencias) and not divergencias_aceitas:
        mensagens.append('Existem divergências operacionais não aceitas.')
        motivos.append('divergencias_operacionais')
        bloqueado = True

    if bloqueado:
        return _montar_elegibilidade_estoque(
            STATUS_ELEGIBILIDADE_BLOQUEADO,
            mensagens=mensagens,
            motivos=motivos,
            movimenta_estoque=movimenta,
            exige_certificado_fornecedor=exige_cf,
            tem_certificado_fornecedor=tem_cf_registrado,
            tem_rastreabilidade_tecnica=tem_rastreabilidade,
        )

    if exige_cf:
        if tem_cf_registrado:
            pass
        elif tem_cf_rascunho:
            mensagens.append('Certificado fornecedor em rascunho; finalize o registro para rastreabilidade completa.')
            motivos.append('certificado_fornecedor_rascunho')
        else:
            mensagens.append(
                'Regra fiscal exige certificado fornecedor, mas nenhum certificado foi vinculado/rastreado para este item.',
            )
            motivos.append('certificado_fornecedor_ausente')

    if not tem_rastreabilidade:
        mensagens.append(
            'Item sem corrida/lote informado. A rastreabilidade técnica pode ficar incompleta.',
        )
        motivos.append('sem_corrida_lote')

    for alerta_split in alertas_splits_parciais(item_conf):
        if alerta_split not in mensagens:
            mensagens.append(alerta_split)
        if 'split_sem_corrida_lote' not in motivos:
            motivos.append('split_sem_corrida_lote')

    fiscal_status = (resultado_fiscal.get('status') or '').upper()
    if fiscal_status == 'SEM_REGRA':
        msg = (resultado_fiscal.get('mensagens') or [MSG_SEM_REGRA_FISCAL_ENTRADA])[0]
        if msg not in mensagens:
            mensagens.append(msg)
        motivos.append('sem_regra_fiscal')
    elif fiscal_status == 'ALERTA':
        motivos.append('fiscal_alerta')
        for msg in resultado_fiscal.get('mensagens') or []:
            texto = (msg or '').strip()
            if texto and texto not in mensagens:
                mensagens.append(texto)

    if mensagens:
        return _montar_elegibilidade_estoque(
            STATUS_ELEGIBILIDADE_APTO_COM_ALERTA,
            mensagens=mensagens,
            motivos=motivos,
            movimenta_estoque=movimenta if movimenta is not None else True,
            exige_certificado_fornecedor=exige_cf,
            tem_certificado_fornecedor=tem_cf_registrado,
            tem_rastreabilidade_tecnica=tem_rastreabilidade,
        )

    return _montar_elegibilidade_estoque(
        STATUS_ELEGIBILIDADE_APTO,
        mensagens=[],
        motivos=[],
        movimenta_estoque=movimenta if movimenta is not None else True,
        exige_certificado_fornecedor=exige_cf,
        tem_certificado_fornecedor=tem_cf_registrado,
        tem_rastreabilidade_tecnica=tem_rastreabilidade,
    )


def montar_resumo_elegibilidade_estoque(
    elegibilidades: list[ElegibilidadeEstoqueDict],
) -> ResumoElegibilidadeEstoqueDict:
    resumo: ResumoElegibilidadeEstoqueDict = {
        'aptos': 0,
        'aptos_com_alerta': 0,
        'bloqueados': 0,
        'nao_movimentam': 0,
    }
    for row in elegibilidades:
        status = (row.get('status') or '').upper()
        if status == STATUS_ELEGIBILIDADE_APTO:
            resumo['aptos'] += 1
        elif status == STATUS_ELEGIBILIDADE_APTO_COM_ALERTA:
            resumo['aptos_com_alerta'] += 1
        elif status == STATUS_ELEGIBILIDADE_BLOQUEADO:
            resumo['bloqueados'] += 1
        elif status == STATUS_ELEGIBILIDADE_NAO_MOVIMENTA:
            resumo['nao_movimentam'] += 1
    return resumo


def aplicar_pos_save_item_conferencia(
    item_conf: ItemNFeEntradaConferencia,
    conferencia: NFeEntradaConferencia,
) -> ItemNFeEntradaConferencia:
    """Recalcula estoque (se produto), divergências e status operacional da linha."""
    alertas: list[str] = []

    if item_conf.produto_id:
        produto = item_conf.produto
        unidade_destino = (
            produto.get_unidade_estoque_efetiva() or produto.unidade or item_conf.unidade_nf or 'UN'
        ).upper()
        item_conf.unidade_estoque_calculada = unidade_destino

        from apps.fiscal.rastreabilidade_conferencia import item_usa_equivalencia_entrada

        if item_usa_equivalencia_entrada(item_conf):
            equivs = list(item_conf.equivalencias.order_by('ordem', 'id'))
            peso_total = sum(Decimal(str(e.peso_kg or 0)) for e in equivs)
            metros_total = sum(Decimal(str(e.metros or 0)) for e in equivs)
            barras_total = sum(Decimal(str(e.barras or 0)) for e in equivs)
            item_conf.peso_total_kg = peso_total
            item_conf.metros_total = metros_total
            item_conf.barras_total = barras_total
            item_conf.toneladas_total = (
                (peso_total / Decimal('1000')).quantize(Decimal('0.001')) if peso_total else Decimal('0')
            )
            if unidade_destino in ('KG', 'TON'):
                item_conf.quantidade_estoque_calculada = peso_total
            elif unidade_destino == 'M':
                item_conf.quantidade_estoque_calculada = metros_total
            elif unidade_destino == 'BR':
                item_conf.quantidade_estoque_calculada = barras_total
            else:
                item_conf.quantidade_estoque_calculada = barras_total or metros_total or peso_total
        else:
            try:
                from apps.produtos.conversao_medidas import converter_quantidade_produto

                res = converter_quantidade_produto(
                    produto=produto,
                    quantidade=item_conf.quantidade_nf,
                    unidade_origem=item_conf.unidade_nf,
                    unidade_destino=unidade_destino,
                )
                item_conf.quantidade_estoque_calculada = res.quantidade_destino
                item_conf.peso_total_kg = res.peso_kg or Decimal('0')
                item_conf.metros_total = res.metros or Decimal('0')
                item_conf.barras_total = res.barras or Decimal('0')
                item_conf.toneladas_total = (
                    (item_conf.peso_total_kg / Decimal('1000')).quantize(Decimal('0.001'))
                    if item_conf.peso_total_kg
                    else Decimal('0')
                )
            except Exception as exc:  # noqa: BLE001
                alertas.append(str(exc))
                if not item_conf.unidade_estoque_calculada:
                    item_conf.unidade_estoque_calculada = unidade_destino

    divergencias, div_alertas = calcular_divergencias_item_conferencia(item_conf, conferencia)
    alertas.extend(div_alertas)
    item_conf.alertas = list(dict.fromkeys(alertas))
    item_conf.divergencias = list(dict.fromkeys(divergencias))

    if item_conf.status != item_conf.Status.IGNORADO:
        item_conf.status = calcular_status_operacional_item_conferencia(item_conf)

    item_conf.save()

    if item_conf.item_pedido_compra_id and conferencia.pedido_compra_id:
        _recalcular_divergencias_linhas_mesmo_item_pedido(
            conferencia,
            item_pedido_id=item_conf.item_pedido_compra_id,
            exceto_linha_id=item_conf.id,
        )

    if item_conf.produto_id:
        from apps.fiscal.correlacao_produto_fornecedor import persistir_correlacao_produto_fornecedor_conferencia

        persistir_correlacao_produto_fornecedor_conferencia(item_conf, conferencia)

    return item_conf


def _recalcular_divergencias_linhas_mesmo_item_pedido(
    conferencia: NFeEntradaConferencia,
    *,
    item_pedido_id: int,
    exceto_linha_id: int,
) -> None:
    """Atualiza divergências/status das outras linhas vinculadas ao mesmo item do pedido (split NF)."""
    irmas = conferencia.itens.filter(item_pedido_compra_id=item_pedido_id).exclude(pk=exceto_linha_id)
    for linha in irmas:
        if linha.status == ItemNFeEntradaConferencia.Status.IGNORADO:
            continue
        divergencias, div_alertas = calcular_divergencias_item_conferencia(linha, conferencia)
        alertas = list(linha.alertas or [])
        for msg in div_alertas:
            if msg not in alertas:
                alertas.append(msg)
        linha.alertas = list(dict.fromkeys(alertas))
        linha.divergencias = list(dict.fromkeys(divergencias))
        if linha.status != ItemNFeEntradaConferencia.Status.IGNORADO:
            linha.status = calcular_status_operacional_item_conferencia(linha)
        linha.save(update_fields=['divergencias', 'alertas', 'status', 'atualizado_em'])


def limpar_vinculos_pedido_invalidos(conferencia: NFeEntradaConferencia) -> int:
    """Remove item_pedido_compra de linhas que não pertencem ao pedido do cabeçalho."""
    qs = conferencia.itens.filter(item_pedido_compra__isnull=False)
    if conferencia.pedido_compra_id:
        qs = qs.exclude(item_pedido_compra__pedido_id=conferencia.pedido_compra_id)
    updated = qs.update(item_pedido_compra=None, snapshot_pedido={})
    return updated


def _linha_item_pedido_resumo(item_pc: ItemPedidoCompra) -> dict:
    return {
        'id': item_pc.id,
        'produto_codigo': _codigo_produto_pedido(item_pc),
        'descricao': _descricao_produto_pedido(item_pc),
        'quantidade': float(item_pc.quantidade_negociada or item_pc.quantidade or 0),
        'unidade': _norm_unit(item_pc.unidade_negociada),
        'valor_unitario': float(item_pc.valor_unitario or 0),
    }


def _linha_nf_extra_resumo(item_conf: ItemNFeEntradaConferencia) -> dict:
    prod_json = item_conf.item_nfe_historico.prod_json or {}
    return {
        'id': item_conf.id,
        'n_item': item_conf.item_nfe_historico.n_item,
        'codigo_fornecedor': str(prod_json.get('cProd') or '').strip(),
        'descricao_fornecedor': str(prod_json.get('xProd') or '').strip(),
        'quantidade': float(item_conf.quantidade_nf or 0),
        'unidade': _norm_unit(item_conf.unidade_nf),
        'valor_unitario': float(item_conf.valor_unitario_nf or 0),
    }


def montar_resumo_pedido_conferencia(
    conferencia: NFeEntradaConferencia,
    itens_pedido: list[ItemPedidoCompra] | None = None,
) -> dict:
    """Comparação somente leitura Pedido de Compra × linhas da conferência (NF)."""
    linhas = list(conferencia.itens.all())

    if not conferencia.pedido_compra_id:
        return {
            'pedido_selecionado': False,
            'mensagem': (
                'Sem pedido de compra vinculado. A conferência seguirá sem comparação Pedido × NF.'
            ),
            'totais': {
                'itens_pedido': 0,
                'itens_nf': len(linhas),
                'vinculados': 0,
                'faltantes': 0,
                'extras': 0,
                'itens_parciais': 0,
                'itens_excedentes': 0,
                'itens_completos': 0,
                'itens_duplicados_na_nf': 0,
                'itens_pendentes_global': 0,
                'itens_parciais_global': 0,
                'itens_completos_global': 0,
                'itens_excedentes_global': 0,
            },
            'itens_pedido_sem_nf': [],
            'itens_nf_sem_pedido': [],
            'resumo_quantitativo': [],
            'saldo_pedido_global': [],
        }

    if itens_pedido is None:
        itens_pedido = list(
            ItemPedidoCompra.objects.filter(pedido_id=conferencia.pedido_compra_id).select_related('produto'),
        )

    vinculados_pedido_ids = {
        linha.item_pedido_compra_id for linha in linhas if linha.item_pedido_compra_id
    }
    vinculados = sum(1 for linha in linhas if linha.item_pedido_compra_id)

    itens_pedido_sem_nf = [
        _linha_item_pedido_resumo(item_pc)
        for item_pc in itens_pedido
        if item_pc.id not in vinculados_pedido_ids
    ]

    itens_nf_sem_pedido = [
        _linha_nf_extra_resumo(linha)
        for linha in linhas
        if not linha.item_pedido_compra_id and linha.status != ItemNFeEntradaConferencia.Status.IGNORADO
    ]

    resumo_quantitativo = montar_resumo_quantitativo_pedido_conferencia(linhas, itens_pedido)
    itens_parciais = sum(1 for row in resumo_quantitativo if row['status_quantitativo'] == 'parcial')
    itens_excedentes = sum(1 for row in resumo_quantitativo if row['status_quantitativo'] == 'excedente')
    itens_completos = sum(1 for row in resumo_quantitativo if row['status_quantitativo'] == 'completo')
    itens_duplicados_na_nf = sum(
        1 for row in resumo_quantitativo if 'item_pedido_duplicado_na_nf' in row['alertas']
    )

    saldo_pedido_global = montar_saldo_pedido_global_conferencia(
        conferencia,
        itens_pedido,
        linhas_atual=linhas,
    )
    itens_pendentes_global = sum(1 for row in saldo_pedido_global if row['status_saldo'] == 'pendente')
    itens_parciais_global = sum(1 for row in saldo_pedido_global if row['status_saldo'] == 'parcial')
    itens_completos_global = sum(1 for row in saldo_pedido_global if row['status_saldo'] == 'completo')
    itens_excedentes_global = sum(1 for row in saldo_pedido_global if row['status_saldo'] == 'excedente')

    return {
        'pedido_selecionado': True,
        'mensagem': '',
        'totais': {
            'itens_pedido': len(itens_pedido),
            'itens_nf': len(linhas),
            'vinculados': vinculados,
            'faltantes': len(itens_pedido_sem_nf),
            'extras': len(itens_nf_sem_pedido),
            'itens_parciais': itens_parciais,
            'itens_excedentes': itens_excedentes,
            'itens_completos': itens_completos,
            'itens_duplicados_na_nf': itens_duplicados_na_nf,
            'itens_pendentes_global': itens_pendentes_global,
            'itens_parciais_global': itens_parciais_global,
            'itens_completos_global': itens_completos_global,
            'itens_excedentes_global': itens_excedentes_global,
        },
        'itens_pedido_sem_nf': itens_pedido_sem_nf,
        'itens_nf_sem_pedido': itens_nf_sem_pedido,
        'resumo_quantitativo': resumo_quantitativo,
        'saldo_pedido_global': saldo_pedido_global,
    }
