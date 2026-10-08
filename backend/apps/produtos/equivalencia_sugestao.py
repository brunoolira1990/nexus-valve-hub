"""Motor genérico de sugestão de equivalência NF-e entrada — ERP 4.0.13.7 / 4.0.13.7.1."""

from __future__ import annotations

from decimal import Decimal
from itertools import combinations
from typing import Any, TypedDict

from apps.comercial.models import ItemPedidoCompra
from apps.fiscal.models import ItemNFeEntradaConferencia, NFeEntradaConferencia
from apps.produtos.cnpj_fornecedor import cnpj_apenas_digitos, cnpj_raiz
from apps.produtos.descricao_normalizacao import (
    normalizar_codigo_fornecedor,
    normalizar_descricao_produto,
    similaridade_descricao,
)
from apps.produtos.models_equivalencia import (
    FornecedorComposicaoEquivalencia,
    FornecedorProdutoEquivalencia,
    ProdutoComposicao,
)

TOLERANCIA_VALOR_PADRAO = Decimal('0.05')
TOLERANCIA_VALOR_PERCENTUAL_PADRAO = Decimal('0.5')

AVISO_ESTOQUE_EQUIVALENCIA = (
    'Equivalência confirmada para conferência. '
    'Movimentação de estoque ou montagem real será feita em fase própria.'
)


class SugestaoEquivalenciaDict(TypedDict, total=False):
    tipo: str
    confianca: int
    nivel_confianca: str
    produto_interno_id: int
    produto_interno_codigo: str
    produto_interno_descricao: str
    item_pedido_compra_id: int | None
    quantidade_equivalente: str
    valor_total_agrupado: str
    valor_pedido_referencia: str
    diferenca_valor: str
    diferenca_quantidade: str
    dentro_tolerancia: bool
    itens_nfe_conferencia_ids: list[int]
    itens_nfe: list[dict[str, Any]]
    motivos: list[str]
    regra_id: int | None
    regra_tipo: str | None
    alerta_filial: str | None
    tipo_composicao: str | None


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal('0')


def _nivel_confianca(score: int) -> str:
    if score >= 85:
        return 'alta'
    if score >= 60:
        return 'media'
    return 'baixa'


def _emit_cnpj(conferencia: NFeEntradaConferencia) -> tuple[str, str]:
    nf = conferencia.nf_entrada_historica
    emit = nf.emit_json if isinstance(nf.emit_json, dict) else {}
    cnpj = cnpj_apenas_digitos(str(emit.get('CNPJ') or emit.get('cnpj') or ''))
    if not cnpj and nf.fornecedor_emitente_id:
        cnpj = cnpj_apenas_digitos(nf.fornecedor_emitente.cnpj or '')
    return cnpj, cnpj_raiz(cnpj)


def _item_nf_dados(item_conf: ItemNFeEntradaConferencia) -> dict[str, Any]:
    prod_json = item_conf.item_nfe_historico.prod_json or {}
    return {
        'item_conferencia_id': item_conf.id,
        'item_nfe_historico_id': item_conf.item_nfe_historico_id,
        'n_item': item_conf.item_nfe_historico.n_item,
        'codigo_fornecedor': str(prod_json.get('cProd') or '').strip(),
        'descricao': str(prod_json.get('xProd') or '').strip(),
        'descricao_normalizada': normalizar_descricao_produto(prod_json.get('xProd')),
        'ncm': str(prod_json.get('NCM') or prod_json.get('ncm') or '').strip(),
        'quantidade': str(item_conf.quantidade_nf),
        'valor_total': str(item_conf.valor_total_nf),
        'unidade': item_conf.unidade_nf,
    }


def _valor_item_pedido(item_pc: ItemPedidoCompra) -> Decimal:
    qtd = _dec(item_pc.quantidade_negociada or item_pc.quantidade)
    return (qtd * _dec(item_pc.valor_unitario)).quantize(Decimal('0.01'))


def _codigo_produto_pedido(item_pc: ItemPedidoCompra) -> str:
    snap = item_pc.snapshot_produto if isinstance(item_pc.snapshot_produto, dict) else {}
    if snap.get('codigo_completo'):
        return str(snap['codigo_completo']).strip()
    return item_pc.produto.codigo_completo.strip() if item_pc.produto_id else ''


def _descricao_produto_pedido(item_pc: ItemPedidoCompra) -> str:
    snap = item_pc.snapshot_produto if isinstance(item_pc.snapshot_produto, dict) else {}
    if snap.get('descricao'):
        return str(snap['descricao']).strip()
    return item_pc.produto.descricao.strip() if item_pc.produto_id else ''


def _itens_livres(conferencia: NFeEntradaConferencia) -> list[ItemNFeEntradaConferencia]:
    usados = set(
        conferencia.agrupamentos.filter(status__in=('confirmado', 'sugerido'))
        .values_list('itens__item_nfe_conferencia_id', flat=True),
    )
    return [it for it in conferencia.itens.all() if it.id not in usados]


def _equivalencias_simples_fornecedor(
    fornecedor_id: int | None,
    cnpj_emit: str,
    cnpj_raiz_emit: str,
) -> list[FornecedorProdutoEquivalencia]:
    if not fornecedor_id and not cnpj_raiz_emit:
        return []
    qs = FornecedorProdutoEquivalencia.objects.filter(ativo=True).select_related('produto_interno')
    if fornecedor_id:
        qs = qs.filter(fornecedor_id=fornecedor_id)
    return list(qs)


def _equivalencias_compostas_fornecedor(
    fornecedor_id: int | None,
    cnpj_raiz_emit: str,
) -> list[FornecedorComposicaoEquivalencia]:
    if not fornecedor_id and not cnpj_raiz_emit:
        return []
    qs = (
        FornecedorComposicaoEquivalencia.objects.filter(ativo=True)
        .select_related('produto_interno_final')
        .prefetch_related('itens')
    )
    if fornecedor_id:
        qs = qs.filter(fornecedor_id=fornecedor_id)
    return list(qs)


def _match_regra_composta(
    regra: FornecedorComposicaoEquivalencia,
    itens_conf: list[ItemNFeEntradaConferencia],
) -> tuple[list[ItemNFeEntradaConferencia], int, list[str]] | None:
    """Casamento genérico: itens NF-e ↔ componentes esperados da regra cadastrada."""
    componentes = list(regra.itens.all())
    if not componentes:
        return None

    matched: list[ItemNFeEntradaConferencia] = []
    usados: set[int] = set()
    score = 0
    motivos: list[str] = []

    for comp in componentes:
        melhor: ItemNFeEntradaConferencia | None = None
        melhor_score = 0
        cod_comp = normalizar_codigo_fornecedor(comp.codigo_fornecedor)
        desc_comp = comp.descricao_fornecedor_normalizada or normalizar_descricao_produto(comp.codigo_fornecedor)

        for item in itens_conf:
            if item.id in usados:
                continue
            dados = _item_nf_dados(item)
            s = 0
            cod_nf = normalizar_codigo_fornecedor(dados['codigo_fornecedor'])
            if cod_comp and cod_nf == cod_comp:
                s += comp.peso_match_codigo
            sim = similaridade_descricao(dados['descricao'], desc_comp)
            s += int(sim * comp.peso_match_descricao)
            if comp.ncm_fornecedor and dados['ncm'] and comp.ncm_fornecedor == dados['ncm'][:8]:
                s += comp.peso_match_ncm
            if s > melhor_score:
                melhor_score = s
                melhor = item

        if melhor and melhor_score >= 15:
            matched.append(melhor)
            usados.add(melhor.id)
            score += melhor_score
            motivos.append(f'componente_regra_{comp.id}')

    obrigatorios = sum(1 for c in componentes if c.obrigatorio)
    if len(matched) < obrigatorios:
        return None
    return matched, score, motivos


def _match_composicao_cadastrada(
    produto_final_id: int,
    itens_conf: list[ItemNFeEntradaConferencia],
) -> tuple[list[ItemNFeEntradaConferencia], int, list[str], str | None] | None:
    """Heurística genérica via composição cadastrada do produto final."""
    composicoes = (
        ProdutoComposicao.objects.filter(produto_final_id=produto_final_id, ativo=True)
        .prefetch_related('itens__componente_produto')
        .order_by('-padrao', '-ativo', 'id')
    )

    for comp in composicoes:
        componentes = list(comp.itens.filter(obrigatorio=True))
        if not componentes:
            continue

        matched: list[ItemNFeEntradaConferencia] = []
        usados: set[int] = set()
        score = 0
        motivos: list[str] = []

        for comp_item in componentes:
            prod_comp = comp_item.componente_produto
            melhor: ItemNFeEntradaConferencia | None = None
            melhor_score = 0

            for item in itens_conf:
                if item.id in usados:
                    continue
                dados = _item_nf_dados(item)
                s = 0
                sim = similaridade_descricao(dados['descricao'], prod_comp.descricao)
                s += int(sim * 35)
                cod_nf = normalizar_codigo_fornecedor(dados['codigo_fornecedor'])
                cod_comp = normalizar_codigo_fornecedor(prod_comp.codigo_completo)
                if cod_comp and cod_nf and cod_comp == cod_nf:
                    s += 25
                if s > melhor_score:
                    melhor_score = s
                    melhor = item

            if melhor and melhor_score >= 25:
                matched.append(melhor)
                usados.add(melhor.id)
                score += melhor_score
                motivos.append(f'composicao_item_{comp_item.id}')

        if len(matched) >= len(componentes):
            conf = min(85, score // max(1, len(componentes)) + 25)
            return matched, conf, motivos + ['composicao_cadastrada'], comp.tipo_composicao

    return None


def _heuristica_similaridade_agregada(
    item_pc: ItemPedidoCompra,
    itens_conf: list[ItemNFeEntradaConferencia],
    tol_valor: Decimal,
) -> tuple[list[ItemNFeEntradaConferencia], int, list[str]] | None:
    """Agrupa itens NF cujo valor somado aproxima o pedido e descrições relacionadas."""
    desc_ped = normalizar_descricao_produto(_descricao_produto_pedido(item_pc))
    if not desc_ped or len(itens_conf) < 2:
        return None

    valor_ped = _valor_item_pedido(item_pc)
    melhor: list[ItemNFeEntradaConferencia] | None = None
    melhor_score = 0

    for n in range(2, min(6, len(itens_conf) + 1)):
        for combo in combinations(itens_conf, n):
            valor_combo = sum(_dec(_item_nf_dados(it)['valor_total']) for it in combo)
            if abs(valor_combo - valor_ped) > tol_valor * max(Decimal('1'), Decimal(len(combo))):
                continue
            combined = ' '.join(_item_nf_dados(it)['descricao_normalizada'] for it in combo)
            sim = similaridade_descricao(desc_ped, combined)
            if sim < 0.15:
                continue
            score = int(sim * 60) + 15
            if score > melhor_score:
                melhor_score = score
                melhor = list(combo)

    if melhor and melhor_score >= 35:
        return melhor, melhor_score, ['heuristica_similaridade_agregada']
    return None


def _montar_sugestao_composta(
    *,
    item_pc: ItemPedidoCompra,
    matched: list[ItemNFeEntradaConferencia],
    score: int,
    motivos: list[str],
    regra_id: int | None,
    regra_tipo: str | None,
    tol_valor: Decimal,
    alerta_filial: str | None = None,
    tipo_composicao: str | None = None,
) -> SugestaoEquivalenciaDict:
    valor_nf = sum(_dec(_item_nf_dados(it)['valor_total']) for it in matched)
    valor_ped = _valor_item_pedido(item_pc)
    diff_val = (valor_nf - valor_ped).quantize(Decimal('0.01'))
    qtd_ped = _dec(item_pc.quantidade_negociada or item_pc.quantidade)

    confianca = min(100, score)
    dentro_tol = abs(diff_val) <= tol_valor

    return {
        'tipo': 'equivalencia_composta',
        'confianca': confianca,
        'nivel_confianca': _nivel_confianca(confianca),
        'produto_interno_id': item_pc.produto_id,
        'produto_interno_codigo': _codigo_produto_pedido(item_pc),
        'produto_interno_descricao': _descricao_produto_pedido(item_pc),
        'item_pedido_compra_id': item_pc.id,
        'quantidade_equivalente': str(qtd_ped),
        'valor_total_agrupado': str(valor_nf),
        'valor_pedido_referencia': str(valor_ped),
        'diferenca_valor': str(diff_val),
        'diferenca_quantidade': '0',
        'dentro_tolerancia': dentro_tol,
        'itens_nfe_conferencia_ids': [it.id for it in matched],
        'itens_nfe': [_item_nf_dados(it) for it in matched],
        'motivos': motivos,
        'regra_id': regra_id,
        'regra_tipo': regra_tipo,
        'alerta_filial': alerta_filial,
        'tipo_composicao': tipo_composicao,
    }


def _sugerir_montagem_planejada(
    item_pc: ItemPedidoCompra,
    alerta_filial: str | None,
) -> SugestaoEquivalenciaDict | None:
    """Sugestão informativa quando produto possui composição cadastrada."""
    if not item_pc.produto_id:
        return None
    comp = (
        ProdutoComposicao.objects.filter(produto_final_id=item_pc.produto_id, ativo=True)
        .order_by('-padrao', '-ativo', 'id')
        .first()
    )
    if not comp:
        return None
    return {
        'tipo': 'montagem_planejada',
        'confianca': 55,
        'nivel_confianca': 'baixa',
        'produto_interno_id': item_pc.produto_id,
        'produto_interno_codigo': _codigo_produto_pedido(item_pc),
        'produto_interno_descricao': _descricao_produto_pedido(item_pc),
        'item_pedido_compra_id': item_pc.id,
        'quantidade_equivalente': str(item_pc.quantidade_negociada or item_pc.quantidade),
        'valor_total_agrupado': '0',
        'valor_pedido_referencia': str(_valor_item_pedido(item_pc)),
        'diferenca_valor': '0',
        'diferenca_quantidade': '0',
        'dentro_tolerancia': True,
        'itens_nfe_conferencia_ids': [],
        'itens_nfe': [],
        'motivos': ['composicao_cadastrada_produto'],
        'regra_id': comp.id,
        'regra_tipo': 'composicao',
        'alerta_filial': alerta_filial,
        'tipo_composicao': comp.tipo_composicao,
    }


def sugerir_equivalencias_conferencia(conferencia: NFeEntradaConferencia) -> list[SugestaoEquivalenciaDict]:
    """Gera sugestões genéricas de equivalência simples, composta e montagem."""
    sugestoes: list[SugestaoEquivalenciaDict] = []
    nf = conferencia.nf_entrada_historica
    fornecedor_id = nf.fornecedor_emitente_id
    cnpj_emit, cnpj_raiz_emit = _emit_cnpj(conferencia)

    itens_livres = _itens_livres(conferencia)
    if not itens_livres:
        return sugestoes

    alerta_filial = None
    if conferencia.pedido_compra_id and conferencia.pedido_compra.fornecedor_id:
        pc_cnpj = cnpj_apenas_digitos(conferencia.pedido_compra.fornecedor.cnpj or '')
        if pc_cnpj and cnpj_emit and pc_cnpj != cnpj_emit and cnpj_raiz(pc_cnpj) == cnpj_raiz_emit:
            alerta_filial = 'NF-e emitida por filial do fornecedor. Equivalência pode ser aplicada por raiz CNPJ.'

    for eq in _equivalencias_simples_fornecedor(fornecedor_id, cnpj_emit, cnpj_raiz_emit):
        for item in itens_livres:
            cod = normalizar_codigo_fornecedor(_item_nf_dados(item)['codigo_fornecedor'])
            if eq.codigo_fornecedor and cod == normalizar_codigo_fornecedor(eq.codigo_fornecedor):
                sugestoes.append(
                    {
                        'tipo': 'equivalencia_simples',
                        'confianca': eq.confianca_padrao,
                        'nivel_confianca': _nivel_confianca(eq.confianca_padrao),
                        'produto_interno_id': eq.produto_interno_id,
                        'produto_interno_codigo': eq.produto_interno.codigo_completo,
                        'produto_interno_descricao': eq.produto_interno.descricao,
                        'item_pedido_compra_id': None,
                        'quantidade_equivalente': str(item.quantidade_nf),
                        'valor_total_agrupado': str(item.valor_total_nf),
                        'valor_pedido_referencia': '0',
                        'diferenca_valor': '0',
                        'diferenca_quantidade': '0',
                        'dentro_tolerancia': True,
                        'itens_nfe_conferencia_ids': [item.id],
                        'itens_nfe': [_item_nf_dados(item)],
                        'motivos': ['equivalencia_simples_cadastro'],
                        'regra_id': eq.id,
                        'regra_tipo': 'simples',
                        'alerta_filial': alerta_filial,
                    },
                )

    itens_pedido: list[ItemPedidoCompra] = []
    if conferencia.pedido_compra_id:
        itens_pedido = list(conferencia.pedido_compra.itens.select_related('produto').all())

    regras_compostas = _equivalencias_compostas_fornecedor(fornecedor_id, cnpj_raiz_emit)
    usados_compostos: set[int] = set()

    for item_pc in itens_pedido:
        if not item_pc.produto_id:
            continue
        livres_pc = [it for it in itens_livres if it.id not in usados_compostos]
        tol = TOLERANCIA_VALOR_PADRAO
        melhor: SugestaoEquivalenciaDict | None = None

        for regra in regras_compostas:
            if regra.produto_interno_final_id != item_pc.produto_id:
                continue
            tol = max(tol, _dec(regra.tolerancia_valor_absoluto))
            match = _match_regra_composta(regra, livres_pc)
            if not match:
                continue
            matched, score, motivos = match
            sug = _montar_sugestao_composta(
                item_pc=item_pc,
                matched=matched,
                score=min(100, score + 20),
                motivos=motivos + ['regra_composta_cadastro'],
                regra_id=regra.id,
                regra_tipo='composta',
                tol_valor=tol,
                alerta_filial=alerta_filial,
            )
            if not melhor or sug['confianca'] > melhor['confianca']:
                melhor = sug

        if not melhor:
            comp_match = _match_composicao_cadastrada(item_pc.produto_id, livres_pc)
            if comp_match:
                matched, score, motivos, tipo_comp = comp_match
                melhor = _montar_sugestao_composta(
                    item_pc=item_pc,
                    matched=matched,
                    score=score,
                    motivos=motivos,
                    regra_id=None,
                    regra_tipo='composicao',
                    tol_valor=tol,
                    alerta_filial=alerta_filial,
                    tipo_composicao=tipo_comp,
                )

        if not melhor:
            heur = _heuristica_similaridade_agregada(item_pc, livres_pc, tol)
            if heur:
                matched, score, motivos = heur
                melhor = _montar_sugestao_composta(
                    item_pc=item_pc,
                    matched=matched,
                    score=score,
                    motivos=motivos,
                    regra_id=None,
                    regra_tipo=None,
                    tol_valor=tol,
                    alerta_filial=alerta_filial,
                )

        if melhor:
            sugestoes.append(melhor)
            for iid in melhor.get('itens_nfe_conferencia_ids') or []:
                usados_compostos.add(iid)
        else:
            mont = _sugerir_montagem_planejada(item_pc, alerta_filial)
            if mont:
                sugestoes.append(mont)

    return sorted(sugestoes, key=lambda s: -int(s.get('confianca') or 0))


def montar_resumo_equivalencias_conferencia(conferencia: NFeEntradaConferencia) -> dict[str, Any]:
    """Payload para UI — sugestões + agrupamentos confirmados."""
    agrupamentos = list(
        conferencia.agrupamentos.select_related(
            'produto_interno_resultante',
            'item_pedido_compra',
            'usuario_confirmacao',
        )
        .prefetch_related('itens__item_nfe_conferencia__item_nfe_historico')
        .order_by('-confianca', 'id'),
    )
    sugestoes = sugerir_equivalencias_conferencia(conferencia)

    pedido = conferencia.pedido_compra
    comparacao_pedido_nf = None
    if pedido:
        total_ped = _dec(pedido.valor_total)
        total_nf = sum(_dec(it.valor_total_nf) for it in conferencia.itens.all())
        comparacao_pedido_nf = {
            'valor_produtos_pedido': str(total_ped),
            'valor_produtos_nf': str(total_nf),
            'diferenca_produtos': str((total_nf - total_ped).quantize(Decimal('0.01'))),
            'mensagem': 'Comparação informativa — não recalcula custo automaticamente.',
        }

    return {
        'sugestoes': sugestoes,
        'agrupamentos': [_serializar_agrupamento(a) for a in agrupamentos],
        'comparacao_pedido_nf': comparacao_pedido_nf,
        'aviso_estoque': AVISO_ESTOQUE_EQUIVALENCIA,
    }


def _serializar_agrupamento(agr) -> dict[str, Any]:
    return {
        'id': agr.id,
        'tipo_agrupamento': agr.tipo_agrupamento,
        'status': agr.status,
        'confianca': agr.confianca,
        'produto_interno_id': agr.produto_interno_resultante_id,
        'produto_interno_codigo': agr.produto_interno_resultante.codigo_completo,
        'produto_interno_descricao': agr.produto_interno_resultante.descricao,
        'item_pedido_compra_id': agr.item_pedido_compra_id,
        'quantidade_equivalente': str(agr.quantidade_equivalente),
        'valor_total_agrupado': str(agr.valor_total_agrupado),
        'valor_pedido_referencia': str(agr.valor_pedido_referencia),
        'diferenca_valor': str(agr.diferenca_valor),
        'motivo_confirmacao': agr.motivo_confirmacao,
        'usuario_confirmacao': agr.usuario_confirmacao.username if agr.usuario_confirmacao_id else None,
        'data_confirmacao': agr.data_confirmacao.isoformat() if agr.data_confirmacao else None,
        'itens': [
            {
                'item_nfe_conferencia_id': it.item_nfe_conferencia_id,
                'quantidade_usada': str(it.quantidade_usada),
                'valor_usado': str(it.valor_usado),
            }
            for it in agr.itens.all()
        ],
        'snapshot_rastreabilidade': agr.snapshot_rastreabilidade,
    }
