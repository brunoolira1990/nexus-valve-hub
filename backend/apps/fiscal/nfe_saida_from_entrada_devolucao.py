"""Gera rascunho de NF-e Saida a partir de conferencia de compra (NFeEntradaConferencia).

Representa a devolucao da mercadoria ao fornecedor. Nao transmite SEFAZ, nao
aplica estoque, nao mexe em XML — apenas cria o rascunho no banco.

Referencia espelho: nfe_entrada_from_saida_devolucao.py (fluxo inverso).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from django.db import transaction
from django.db.models import Sum

from apps.fiscal.models import (
    ItemDevolucaoCompra,
    ItemNFeEntradaConferencia,
    ItemNFeSaida,
    NFeEntradaConferencia,
    NFeSaida,
)
from apps.regras_fiscais.saida_fiscal import buscar_regra_fiscal_saida


MOTIVOS_LABEL = {
    'NAO_CONFORME': 'Devolucao de mercadoria nao conforme',
    'DEFEITO': 'Devolucao de mercadoria com defeito',
    'ERRO_PEDIDO': 'Devolucao por erro de pedido',
    'AVARIA_TRANSPORTE': 'Devolucao por avaria no transporte',
    'OUTRO': '',
}

STATUS_ITEM_DEVOLVIVEL = frozenset({'CONFERIDO', 'PRODUTO_VINCULADO'})
STATUS_CONFERENCIA_PERMITIDO = frozenset({'CONFERIDA', 'PREPARADA'})

_CFOP_DEVOLUCAO_COMPRA_PREFIXO = {
    '1': '5',  # entrada mesma UF -> saida mesma UF
    '2': '6',  # entrada interestadual -> saida interestadual
    '3': '6',  # entrada do exterior -> saida interestadual
}


_CFOP_DEVOLUCAO_MAP = {
    '5102': '5202',
    '6102': '6202',
    '5101': '5201',
    '6101': '6201',
}


class NFeSaidaFromEntradaError(ValueError):
    pass


# --- Helpers -----------------------------------------------------------------


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise NFeSaidaFromEntradaError(f'Valor numerico invalido: {val!r}') from exc


def _cfop_devolucao_saida(*, uf_empresa: str, uf_fornecedor: str) -> str:
    ue = (uf_empresa or '').strip().upper()
    uf = (uf_fornecedor or '').strip().upper()
    if ue and uf and ue == uf:
        return '5202'
    return '6202'


def _cfop_devolucao_from_compra(cfop_compra: str, *, mesma_uf: bool) -> str:
    """Traduz CFOP da NF-e de compra para CFOP de saida de devolucao.

    1102 -> 5202, 2102 -> 6202, 1101 -> 5201, 2101 -> 6201.
    Fallback por UF quando o CFOP nao for reconhecido.
    """
    cfop = (cfop_compra or '').strip()
    if len(cfop) == 4 and cfop[0] in _CFOP_DEVOLUCAO_COMPRA_PREFIXO:
        return _CFOP_DEVOLUCAO_COMPRA_PREFIXO[cfop[0]] + cfop[1:]
    return '5202' if mesma_uf else '6202'


def _traduzir_cfop_devolucao(cfop_venda: str) -> str:
    """Traduz CFOP de venda para devolucao (5102->5202, 6102->6202, etc.)."""
    return _CFOP_DEVOLUCAO_MAP.get((cfop_venda or '').strip(), cfop_venda)


def _saldo_item(item_conf: ItemNFeEntradaConferencia) -> Decimal:
    devolvido = (
        ItemDevolucaoCompra.objects
        .filter(item_conferencia=item_conf)
        .aggregate(total=Sum('quantidade_devolvida'))['total']
        or Decimal('0')
    )
    return _dec(item_conf.quantidade_estoque_calculada) - _dec(devolvido)


def _resolver_quantidades(
    *,
    conferencia: NFeEntradaConferencia,
    itens: list[dict] | None,
) -> list[tuple[ItemNFeEntradaConferencia, Decimal]]:
    if itens:
        selecionados: list[tuple[ItemNFeEntradaConferencia, Decimal]] = []
        ids_vistos: set[int] = set()
        for entrada in itens:
            item_id = entrada.get('item_conferencia_id')
            qtd = _dec(entrada.get('quantidade'))
            if item_id is None:
                raise NFeSaidaFromEntradaError('Item sem "item_conferencia_id".')
            if item_id in ids_vistos:
                raise NFeSaidaFromEntradaError(f'Item {item_id} duplicado.')
            ids_vistos.add(item_id)
            try:
                item_conf = ItemNFeEntradaConferencia.objects.get(pk=item_id)
            except ItemNFeEntradaConferencia.DoesNotExist as exc:
                raise NFeSaidaFromEntradaError(f'Item {item_id} nao existe.') from exc
            if item_conf.conferencia_id != conferencia.pk:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id} nao pertence a conferencia {conferencia.pk}.'
                )
            if item_conf.status not in STATUS_ITEM_DEVOLVIVEL:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id} com status {item_conf.status!r} nao devolvivel.'
                )
            if qtd <= 0:
                raise NFeSaidaFromEntradaError(f'Quantidade invalida item {item_id}: {qtd}.')
            saldo = _saldo_item(item_conf)
            if qtd > saldo:
                raise NFeSaidaFromEntradaError(
                    f'Item {item_id}: qtd solicitada ({qtd}) > saldo ({saldo}).'
                )
            selecionados.append((item_conf, qtd))
        return selecionados

    qs = (
        ItemNFeEntradaConferencia.objects
        .filter(conferencia=conferencia, status__in=STATUS_ITEM_DEVOLVIVEL)
        .order_by('item_nfe_historico__n_item', 'id')
    )
    resultado: list[tuple[ItemNFeEntradaConferencia, Decimal]] = []
    for item_conf in qs:
        saldo = _saldo_item(item_conf)
        if saldo > 0:
            resultado.append((item_conf, saldo))
    return resultado


def _montar_snapshot_fiscal(*, cfop: str) -> dict[str, Any]:
    """Fallback quando nao ha regra fiscal cadastrada."""
    return {
        'cfop': cfop,
        'icms': {'cst': '', 'orig': '0', 'base': None, 'aliquota': None, 'valor': None},
        'pis': {'cst': '', 'base': None, 'aliquota': None, 'valor': None},
        'cofins': {'cst': '', 'base': None, 'aliquota': None, 'valor': None},
    }


def _primeiro_grupo_imposto(bloco: Any) -> dict[str, Any]:
    """Pega o primeiro sub-dict de um bloco tipo {'ICMS10': {...}, 'ICMSST': {...}}."""
    if not isinstance(bloco, dict):
        return {}
    for _k, v in bloco.items():
        if isinstance(v, dict) and v:
            return v
    return {}


def _montar_snapshot_fiscal_via_xml_compra(
    *,
    item_conf: ItemNFeEntradaConferencia,
    empresa,
    fornecedor,
) -> dict[str, Any] | None:
    """Espelha os impostos do XML da NF-e de compra (fonte primaria fiscal).

    Extrai CST e aliquotas direto do imposto_json do fornecedor, traduz o CFOP
    de entrada (prod_json.CFOP) para saida, e devolve um snapshot_fiscal no
    shape compativel com o XML de saida.

    Retorna None quando o item nao tem XML de origem (fallback para regra).
    """
    ih = getattr(item_conf, 'item_nfe_historico', None)
    if ih is None:
        return None

    imposto_json = ih.imposto_json if isinstance(ih.imposto_json, dict) else {}
    prod_json = ih.prod_json if isinstance(ih.prod_json, dict) else {}

    if not imposto_json:
        return None

    icms = _primeiro_grupo_imposto(imposto_json.get('ICMS') or {})
    pis = _primeiro_grupo_imposto(imposto_json.get('PIS') or {})
    cof = _primeiro_grupo_imposto(imposto_json.get('COFINS') or {})
    ipi_blk = imposto_json.get('IPI') if isinstance(imposto_json.get('IPI'), dict) else {}
    # IPI costuma vir em IPITrib (tributado) ou IPINT (nao tributado)
    ipi = _primeiro_grupo_imposto(ipi_blk) if ipi_blk else {}
    if not ipi and isinstance(ipi_blk.get('IPITrib'), dict):
        ipi = ipi_blk['IPITrib']
    if not ipi and isinstance(ipi_blk.get('IPINT'), dict):
        ipi = ipi_blk['IPINT']

    # CFOP: traduz da compra (prod_json.CFOP) para devolucao
    cfop_compra = str(prod_json.get('CFOP') or '').strip()
    uf_emp = (getattr(empresa, 'uf', '') or '').strip().upper()
    uf_forn = (getattr(fornecedor, 'uf', '') or '').strip().upper()
    mesma_uf = bool(uf_emp and uf_forn and uf_emp == uf_forn)
    cfop_dev = _cfop_devolucao_from_compra(cfop_compra, mesma_uf=mesma_uf)

    # Chave da NF-e de compra (para rastreio)
    chave_origem = ''
    try:
        chave_origem = (
            item_conf.conferencia.nf_entrada_historica.chave_acesso or ''
        ).strip()
    except Exception:
        pass

    snapshot: dict[str, Any] = {
        'cfop': cfop_dev,
        'icms': {
            'cst': str(icms.get('CST') or icms.get('CSOSN') or ''),
            'orig': str(icms.get('orig') or '0'),
            'base': None,   # recalculado pelo XML de saida
            'aliquota': icms.get('pICMS'),
            'valor': None,
            'modalidade_bc': str(icms.get('modBC') or ''),
            'reducao_bc': None,
        },
        'pis': {
            'cst': str(pis.get('CST') or ''),
            'base': None,
            'aliquota': pis.get('pPIS'),
            'valor': None,
        },
        'cofins': {
            'cst': str(cof.get('CST') or ''),
            'base': None,
            'aliquota': cof.get('pCOFINS'),
            'valor': None,
        },
        '_meta': {
            'origem': 'xml_compra',
            'chave_nfe_origem': chave_origem,
            'cfop_compra': cfop_compra,
            'item_historico_id': ih.pk,
            'n_item': getattr(ih, 'n_item', None),
        },
    }

    # IPI (opcional — so entra se a compra teve)
    if ipi:
        snapshot['ipi'] = {
            'cst': str(ipi.get('CST') or ''),
            'base': None,
            'aliquota': ipi.get('pIPI'),
            'valor': None,
        }

    return snapshot


def _montar_snapshot_fiscal_via_regra(
    *,
    item_conf: ItemNFeEntradaConferencia,
    produto,
    empresa,
    fornecedor,
    cfop_uf: str,
) -> dict[str, Any]:
    """Busca RegraFiscalSaida VENDA e traduz CFOP para devolucao.

    Cai no fallback por UF quando nao encontra regra cadastrada.
    """
    produto_id = produto.pk if produto is not None else None
    ncm = None
    if isinstance(item_conf.snapshot_produto, dict):
        ncm = item_conf.snapshot_produto.get('ncm')
    if ncm is None and produto is not None:
        ncm = getattr(produto, 'ncm', None)

    regra = buscar_regra_fiscal_saida(
        produto_id=produto_id,
        ncm=ncm,
        uf_origem=getattr(empresa, 'uf', '') or '',
        uf_destino=getattr(fornecedor, 'uf', '') or '',
        destinatario_contribuinte='CONTRIBUINTE',
        consumidor_final=False,
        tipo_operacao='VENDA',
        cenario_id=None,
    )

    tem_regra = bool(regra) and regra.get('origem') != 'NAO_ENCONTRADA'

    if not tem_regra:
        snap = _montar_snapshot_fiscal(cfop=cfop_uf)
        snap['_meta'] = {'aviso': 'Regra fiscal nao encontrada', 'cfop_uf': cfop_uf}
        return snap

    cfop_venda = (regra.get('cfop') or cfop_uf or '').strip()
    cfop_dev = _traduzir_cfop_devolucao(cfop_venda)

    return {
        'cfop': cfop_dev,
        'icms': {
            'cst': regra.get('cst_icms', ''),
            'orig': '0',
            'base': None,
            'aliquota': regra.get('aliquota_icms'),
            'valor': None,
            'modalidade_bc': regra.get('modalidade_bc_icms'),
            'reducao_bc': regra.get('reducao_bc_icms'),
        },
        'pis': {
            'cst': regra.get('cst_pis', ''),
            'base': None,
            'aliquota': regra.get('aliquota_pis'),
            'valor': None,
        },
        'cofins': {
            'cst': regra.get('cst_cofins', ''),
            'base': None,
            'aliquota': regra.get('aliquota_cofins'),
            'valor': None,
        },
        'ipi': {
            'cst': regra.get('cst_ipi', ''),
            'base': None,
            'aliquota': regra.get('aliquota_ipi'),
            'valor': None,
        },
        '_meta': {
            'cfop_venda_origem': cfop_venda,
            'regra_id': regra.get('regra_id'),
            'origem': regra.get('origem'),
        },
    }


def _gerar_numero_interno(*, chave_compra: str) -> str:
    sufixo = (chave_compra or '')[-8:].strip() or 'SEMCHAVE'
    return f'DEV-{sufixo}-{uuid4().hex[:6]}'[:64]


# --- Entrada principal -------------------------------------------------------


@transaction.atomic
def gerar_saida_devolucao_compra(
    conferencia: NFeEntradaConferencia,
    *,
    itens: list[dict] | None = None,
    motivo: str,
    observacao: str = '',
    usuario=None,
) -> dict[str, Any]:
    """Cria rascunho de NFeSaida de devolucao ao fornecedor."""
    del usuario

    conf = (
        NFeEntradaConferencia.objects
        .select_for_update(of=('self',))
        .get(pk=conferencia.pk)
    )

    status_conf = (conf.status or '').strip().upper()
    if status_conf not in STATUS_CONFERENCIA_PERMITIDO:
        raise NFeSaidaFromEntradaError(
            f'Conferencia com status {conf.status!r} nao permite devolucao '
            f'(esperado: {", ".join(sorted(STATUS_CONFERENCIA_PERMITIDO))}).'
        )

    historica = conf.nf_entrada_historica
    if historica is None:
        raise NFeSaidaFromEntradaError('Conferencia sem NF-e historica vinculada.')

    fornecedor = historica.fornecedor_emitente
    if fornecedor is None:
        raise NFeSaidaFromEntradaError('NF-e de compra sem fornecedor_emitente.')

    empresa = historica.empresa_destinataria
    if empresa is None:
        raise NFeSaidaFromEntradaError('NF-e de compra sem empresa_destinataria.')

    motivo_norm = (motivo or '').strip().upper()
    if motivo_norm not in MOTIVOS_LABEL:
        raise NFeSaidaFromEntradaError(
            f'Motivo invalido: {motivo!r}. Valores: {", ".join(MOTIVOS_LABEL)}.'
        )
    if motivo_norm == 'OUTRO' and not (observacao or '').strip():
        raise NFeSaidaFromEntradaError('Motivo "OUTRO" exige observacao.')

    chave_compra = (historica.chave_acesso or '').strip()
    if len(chave_compra) != 44:
        raise NFeSaidaFromEntradaError('NF-e historica sem chave valida (44 digitos).')

    pares = _resolver_quantidades(conferencia=conf, itens=itens)
    if not pares:
        raise NFeSaidaFromEntradaError('Nenhum item elegivel para devolucao.')

    # CFOP base por UF (usado no fallback se regra fiscal nao casar)
    cfop_uf = _cfop_devolucao_saida(
        uf_empresa=getattr(empresa, 'uf', '') or '',
        uf_fornecedor=getattr(fornecedor, 'uf', '') or '',
    )

    motivo_label = MOTIVOS_LABEL[motivo_norm]
    obs_final = (
        f'Devolucao de compra - {motivo_label or "outro"}. {observacao.strip()}'
    ).strip()

    nf_saida = NFeSaida.objects.create(
        numero=_gerar_numero_interno(chave_compra=chave_compra),
        cliente=None,
        fornecedor=fornecedor,
        empresa_emitente=empresa,
        nfe_entrada_conferencia_origem=conf,
        data=date.today(),
        valor_total=Decimal('0'),
        status='RASCUNHO',
        observacoes_nfe=obs_final,
    )

    valor_total = Decimal('0')
    cfop_primeiro_item = cfop_uf
    for item_conf, qtd in pares:
        produto = item_conf.produto
        snap_prod = (
            item_conf.snapshot_produto
            if isinstance(item_conf.snapshot_produto, dict)
            else {}
        )
        snapshot_fiscal = _montar_snapshot_fiscal_via_xml_compra(
            item_conf=item_conf,
            empresa=empresa,
            fornecedor=fornecedor,
        )
        if snapshot_fiscal is None:
            snapshot_fiscal = _montar_snapshot_fiscal_via_regra(
                item_conf=item_conf,
                produto=produto,
                empresa=empresa,
                fornecedor=fornecedor,
                cfop_uf=cfop_uf,
            )
        if cfop_primeiro_item == cfop_uf:
            cfop_primeiro_item = snapshot_fiscal.get('cfop') or cfop_uf

        item_saida = ItemNFeSaida.objects.create(
            nf=nf_saida,
            produto=produto,
            quantidade=qtd,
            valor=_dec(item_conf.valor_unitario_nf),
            snapshot_produto=snap_prod,
            snapshot_fiscal=snapshot_fiscal,
            observacao_item=f'Devolucao do item conferencia {item_conf.pk}',
        )
        ItemDevolucaoCompra.objects.create(
            item_nf_saida=item_saida,
            item_conferencia=item_conf,
            quantidade_devolvida=qtd,
        )
        valor_total += qtd * _dec(item_conf.valor_unitario_nf)

    nf_saida.valor_total = valor_total.quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP,
    )
    nf_saida.save(update_fields=['valor_total'])

    return {
        'ok': True,
        'ja_existia': False,
        'nf_saida_id': nf_saida.pk,
        'numero': nf_saida.numero,
        'valor_total': str(nf_saida.valor_total),
        'itens_criados': len(pares),
        'cfop': cfop_primeiro_item,
        'mensagem': (
            'Rascunho de devolucao criado. Revise os dados e emita pela tela '
            'de NF-e de Saida.'
        ),
    }
