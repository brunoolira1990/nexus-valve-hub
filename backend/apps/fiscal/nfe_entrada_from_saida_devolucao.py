"""Gera rascunho de NF-e entrada própria (devolução/recusa) a partir de NF-e Saída autorizada."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.fiscal.models import (
    ItemNFeEntrada,
    ItemNFeSaida,
    ItemNFeSaidaHistoricaImportada,
    NFeEntrada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.serializers import NFeEntradaSerializer, recalcular_valor_nf_entrada
from apps.fiscal.snapshot_fiscal_helpers import (
    cfop_from_snapshot_fiscal,
    get_cofins_snapshot,
    get_icms_snapshot,
    get_ncm_snapshot,
    get_pis_snapshot,
)
from apps.produtos.models import Produto
from apps.produtos.snapshot import build_produto_snapshot

NAT_OP_DEVOLUCAO = 'Devolução de mercadoria'
MSG_SEM_CHAVE = 'NF-e de saída sem chave de acesso autorizada.'
MSG_NAO_AUTORIZADA = 'Gere a entrada própria apenas a partir de NF-e Saída autorizada na SEFAZ.'
MSG_SEM_ITENS = 'NF-e de saída sem itens para espelhar na entrada própria.'
MSG_SEM_EMITENTE = 'Empresa emitente da NF-e de saída não resolvida.'
MSG_SEM_CLIENTE = 'NF-e de saída sem cliente — necessário para destinatário da entrada própria.'
MSG_CANCELADA = 'NF-e de saída cancelada não pode gerar entrada própria.'
MSG_HIST_NAO_AUTORIZADA = (
    'Gere a entrada própria apenas a partir de NF-e saída importada autorizada (não cancelada).'
)
MSG_HIST_SEM_PRODUTO = (
    'Não foi possível vincular produto do cadastro a um ou mais itens do XML. '
    'Cadastre/ajuste o código do produto (cProd) ou NCM único e tente novamente.'
)


class NFeEntradaFromSaidaError(ValueError):
    pass


def _digits(val: Any, *, max_len: int | None = None) -> str:
    out = ''.join(c for c in str(val or '') if c.isdigit())
    if max_len is not None:
        return out[:max_len]
    return out


def cfop_entrada_devolucao_from_saida(cfop_saida: str) -> str:
    """Convenção V1: 1xxx→1202 (dentro do estado), 6xxx→2202 (interestadual)."""
    digits = _digits(cfop_saida, max_len=4)
    if digits.startswith('6'):
        return '2202'
    return '1202'


def _impostos_json_from_item_saida(item: ItemNFeSaida) -> dict[str, Any]:
    snap = item.snapshot_fiscal if isinstance(item.snapshot_fiscal, dict) else {}

    # Prefer nested shape already compatible with entrada XML builder.
    if isinstance(snap.get('icms'), dict) or isinstance(snap.get('pis'), dict):
        icms_raw = snap.get('icms') if isinstance(snap.get('icms'), dict) else {}
        pis_raw = snap.get('pis') if isinstance(snap.get('pis'), dict) else {}
        cof_raw = snap.get('cofins') if isinstance(snap.get('cofins'), dict) else {}
        return {
            'icms': {
                'cst': str(icms_raw.get('cst') or icms_raw.get('cst_icms') or icms_raw.get('csosn') or '41'),
                'orig': str(icms_raw.get('orig') or '0'),
                'base': icms_raw.get('base'),
                'aliquota': icms_raw.get('aliquota'),
                'valor': icms_raw.get('valor'),
            },
            'pis': {
                'cst': str(pis_raw.get('cst') or '07'),
                'base': pis_raw.get('base'),
                'aliquota': pis_raw.get('aliquota'),
                'valor': pis_raw.get('valor'),
            },
            'cofins': {
                'cst': str(cof_raw.get('cst') or '07'),
                'base': cof_raw.get('base'),
                'aliquota': cof_raw.get('aliquota'),
                'valor': cof_raw.get('valor'),
            },
        }

    icms = get_icms_snapshot(snap)
    pis = get_pis_snapshot(snap)
    cof = get_cofins_snapshot(snap)
    cst_icms = icms.get('cst_icms') or icms.get('csosn') or '41'
    return {
        'icms': {
            'cst': cst_icms,
            'orig': '0',
            'base': icms.get('base') or None,
            'aliquota': icms.get('aliquota') or None,
            'valor': icms.get('valor') or None,
        },
        'pis': {
            'cst': pis.get('cst') or '07',
            'base': pis.get('base') or None,
            'aliquota': pis.get('aliquota') or None,
            'valor': pis.get('valor') or None,
        },
        'cofins': {
            'cst': cof.get('cst') or '07',
            'base': cof.get('base') or None,
            'aliquota': cof.get('aliquota') or None,
            'valor': cof.get('valor') or None,
        },
    }


def _unidade_item(item: ItemNFeSaida) -> str:
    snap = item.snapshot_produto if isinstance(item.snapshot_produto, dict) else {}
    for key in ('unidade', 'uCom', 'unidade_comercial'):
        u = str(snap.get(key) or '').strip()
        if u:
            return u[:6]
    if item.produto_id and getattr(item.produto, 'unidade', None):
        return str(item.produto.unidade).strip()[:6] or 'UN'
    return 'UN'


def _ncm_item(item: ItemNFeSaida) -> str:
    ncm = get_ncm_snapshot(item.snapshot_fiscal if isinstance(item.snapshot_fiscal, dict) else {})
    if ncm:
        return ncm
    snap = item.snapshot_produto if isinstance(item.snapshot_produto, dict) else {}
    ncm2 = _digits(snap.get('ncm') or snap.get('NCM'), max_len=8)
    if ncm2:
        return ncm2
    if item.produto_id and getattr(item.produto, 'ncm', None):
        return _digits(item.produto.ncm, max_len=8)
    return ''


def _saida_autorizada(nf: NFeSaida) -> bool:
    st = (nf.status_emissao_sefaz or '').strip().upper()
    return st in (
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_PRODUCAO,
        NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
        'AUTORIZADA',
    )


def _buscar_entrada_existente(
    *,
    nfe_saida: NFeSaida | None = None,
    nfe_historica: NFeSaidaHistoricaImportada | None = None,
    chave: str = '',
) -> NFeEntrada | None:
    qs = NFeEntrada.objects.filter(tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA)
    if nfe_saida is not None:
        por_fk = qs.filter(nfe_saida_origem_id=nfe_saida.pk).order_by('-id').first()
        if por_fk:
            return por_fk
    if nfe_historica is not None:
        por_hist = qs.filter(nfe_saida_historica_origem_id=nfe_historica.pk).order_by('-id').first()
        if por_hist:
            return por_hist
    chave44 = _digits(chave, max_len=44)
    if len(chave44) == 44:
        return qs.filter(chave_nfe_referenciada=chave44).order_by('-id').first()
    return None


def _resposta_entrada(entrada: NFeEntrada, *, ja_existia: bool, mensagem: str, itens_criados: int = 0) -> dict[str, Any]:
    ser = NFeEntradaSerializer(entrada)
    payload: dict[str, Any] = {
        'ok': True,
        'ja_existia': ja_existia,
        'nf_entrada_id': entrada.pk,
        'numero': entrada.numero,
        'tipo_origem': entrada.tipo_origem,
        'status_operacional': entrada.status_operacional,
        'mensagem': mensagem,
        'nfe_entrada': ser.data,
    }
    if not ja_existia:
        payload['itens_criados'] = itens_criados
    return payload


def _primeiro_grupo_imposto(bloco: Any) -> dict[str, Any]:
    if not isinstance(bloco, dict):
        return {}
    for _k, v in bloco.items():
        if isinstance(v, dict):
            return v
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v[0]
    return {}


def impostos_json_from_imposto_xml(imposto_json: dict[str, Any] | None) -> dict[str, Any]:
    """Converte imposto_json do XML importado para shape da entrada própria."""
    raw = imposto_json if isinstance(imposto_json, dict) else {}
    icms_blk = raw.get('ICMS') if isinstance(raw.get('ICMS'), dict) else {}
    pis_blk = raw.get('PIS') if isinstance(raw.get('PIS'), dict) else {}
    cof_blk = raw.get('COFINS') if isinstance(raw.get('COFINS'), dict) else {}
    icms = _primeiro_grupo_imposto(icms_blk)
    pis = _primeiro_grupo_imposto(pis_blk)
    cof = _primeiro_grupo_imposto(cof_blk)
    return {
        'icms': {
            'cst': str(icms.get('CST') or icms.get('CSOSN') or '41'),
            'orig': str(icms.get('orig') or '0'),
            'base': icms.get('vBC'),
            'aliquota': icms.get('pICMS'),
            'valor': icms.get('vICMS'),
        },
        'pis': {
            'cst': str(pis.get('CST') or '07'),
            'base': pis.get('vBC'),
            'aliquota': pis.get('pPIS'),
            'valor': pis.get('vPIS'),
        },
        'cofins': {
            'cst': str(cof.get('CST') or '07'),
            'base': cof.get('vBC'),
            'aliquota': cof.get('pCOFINS'),
            'valor': cof.get('vCOFINS'),
        },
    }


def _resolver_produto_de_prod_json(prod_json: dict[str, Any]) -> Produto | None:
    c_prod = str(prod_json.get('cProd') or prod_json.get('cprod') or '').strip()
    ncm = _digits(prod_json.get('NCM') or prod_json.get('ncm'), max_len=8)
    if c_prod:
        p = Produto.objects.filter(codigo_completo__iexact=c_prod).first()
        if p:
            return p
        p = Produto.objects.filter(codigo_completo__icontains=c_prod).order_by('id').first()
        if p:
            return p
    if ncm:
        qs = Produto.objects.filter(ncm=ncm).order_by('id')
        if qs.count() == 1:
            return qs.first()
    return None


def _dec_prod(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _historica_autorizada(nf: NFeSaidaHistoricaImportada) -> bool:
    if nf.cancelada:
        return False
    st = (nf.status_documento or '').strip().lower()
    if st in ('cancelada', 'cancelado'):
        return False
    cstat = (nf.cstat or '').strip()
    if cstat and cstat not in ('100', '150'):
        return False
    return True


@transaction.atomic
def gerar_entrada_devolucao_from_nfe_saida(
    nfe_saida: NFeSaida,
    *,
    usuario=None,
) -> dict[str, Any]:
    """
    Cria rascunho ENTRADA_PROPRIA_EMITIDA espelhando a saída (finNFe=4).
    Não transmite SEFAZ; não aplica estoque/financeiro.
    """
    del usuario
    nf = (
        NFeSaida.objects.select_related('cliente', 'empresa_emitente', 'pedido_venda')
        .prefetch_related('itens__produto')
        .get(pk=nfe_saida.pk)
    )

    status_doc = (nf.status or '').strip().upper()
    if 'CANCEL' in status_doc or (nf.status_emissao_sefaz or '').upper().startswith('CANCEL'):
        raise NFeEntradaFromSaidaError(MSG_CANCELADA)

    if not _saida_autorizada(nf):
        raise NFeEntradaFromSaidaError(MSG_NAO_AUTORIZADA)

    chave = (nf.chave_acesso or '').strip()
    if len(_digits(chave)) != 44:
        raise NFeEntradaFromSaidaError(MSG_SEM_CHAVE)
    chave = _digits(chave, max_len=44)

    existente = _buscar_entrada_existente(nfe_saida=nf, chave=chave)
    if existente:
        return _resposta_entrada(
            existente,
            ja_existia=True,
            mensagem='Já existe entrada própria vinculada a esta NF-e de saída.',
        )

    try:
        empresa = resolver_empresa_emitente_nfe(nf)
    except Exception as exc:
        raise NFeEntradaFromSaidaError(MSG_SEM_EMITENTE) from exc
    if not empresa:
        raise NFeEntradaFromSaidaError(MSG_SEM_EMITENTE)
    if not nf.cliente_id:
        raise NFeEntradaFromSaidaError(MSG_SEM_CLIENTE)

    itens_saida = list(nf.itens.all().order_by('id'))
    if not itens_saida:
        raise NFeEntradaFromSaidaError(MSG_SEM_ITENS)

    numero_ref = (nf.numero_nfe or nf.numero or str(nf.pk)).strip()
    ambiente = nf.ambiente_emissao or NFeEntrada.AmbienteEmissao.PRODUCAO
    if ambiente not in (
        NFeEntrada.AmbienteEmissao.HOMOLOGACAO,
        NFeEntrada.AmbienteEmissao.PRODUCAO,
    ):
        ambiente = NFeEntrada.AmbienteEmissao.PRODUCAO

    entrada = NFeEntrada.objects.create(
        numero=f'EP-DEV-{numero_ref}'[:64],
        data=date.today(),
        tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        status_operacional=NFeEntrada.StatusOperacional.RASCUNHO,
        ambiente_emissao=ambiente,
        empresa_emitente=empresa,
        cliente_destinatario_id=nf.cliente_id,
        fornecedor=None,
        fin_nfe='4',
        nat_op=NAT_OP_DEVOLUCAO,
        chave_nfe_referenciada=chave,
        nfe_saida_origem=nf,
        valor_total=Decimal('0'),
    )

    for idx, item in enumerate(itens_saida, start=1):
        snap_fisc = item.snapshot_fiscal if isinstance(item.snapshot_fiscal, dict) else {}
        cfop_sai = cfop_from_snapshot_fiscal(snap_fisc)
        ncm = _ncm_item(item)
        unidade = _unidade_item(item)
        snap_prod = item.snapshot_produto if isinstance(item.snapshot_produto, dict) else {}
        if not snap_prod and item.produto_id:
            snap_prod = build_produto_snapshot(item.produto)
        ItemNFeEntrada.objects.create(
            nf=entrada,
            produto_id=item.produto_id,
            quantidade=item.quantidade,
            valor=item.valor,
            corrida_id=item.corrida_id,
            snapshot_produto=snap_prod or {},
            numero_item=idx,
            ncm=ncm,
            cfop=cfop_entrada_devolucao_from_saida(cfop_sai),
            unidade=unidade,
            descricao_xml=str(snap_prod.get('descricao') or getattr(item.produto, 'descricao', '') or '')[:120],
            impostos_json=_impostos_json_from_item_saida(item),
        )

    recalcular_valor_nf_entrada(entrada)
    entrada.refresh_from_db()
    return _resposta_entrada(
        entrada,
        ja_existia=False,
        itens_criados=len(itens_saida),
        mensagem=(
            'Rascunho de entrada própria (devolução) criado a partir da NF-e de saída. '
            'Revise e emita pela tela Entrada Própria.'
        ),
    )


@transaction.atomic
def gerar_entrada_devolucao_from_nfe_saida_historica(
    nfe_historica: NFeSaidaHistoricaImportada,
    *,
    usuario=None,
) -> dict[str, Any]:
    """
    Cria rascunho ENTRADA_PROPRIA_EMITIDA a partir de NF-e saída importada por XML.
    Não transmite SEFAZ; não aplica estoque/financeiro.
    """
    del usuario
    nf = (
        NFeSaidaHistoricaImportada.objects.select_related('cliente', 'empresa_emitente')
        .prefetch_related('itens')
        .get(pk=nfe_historica.pk)
    )

    if not _historica_autorizada(nf):
        raise NFeEntradaFromSaidaError(MSG_HIST_NAO_AUTORIZADA)

    chave = _digits(nf.chave_acesso, max_len=44)
    if len(chave) != 44:
        raise NFeEntradaFromSaidaError(MSG_SEM_CHAVE)

    existente = _buscar_entrada_existente(nfe_historica=nf, chave=chave)
    if existente:
        return _resposta_entrada(
            existente,
            ja_existia=True,
            mensagem='Já existe entrada própria vinculada a esta NF-e importada.',
        )

    if not nf.empresa_emitente_id:
        raise NFeEntradaFromSaidaError(MSG_SEM_EMITENTE)

    cliente = nf.cliente
    if cliente is None:
        from apps.fiscal.nfe_import.service import _resolve_cliente

        cliente = _resolve_cliente(nf.dest_json if isinstance(nf.dest_json, dict) else {})
    if cliente is None:
        raise NFeEntradaFromSaidaError(
            'Cliente destinatário não encontrado no cadastro. '
            'Vincule o CNPJ do destinatário do XML a um Cliente e tente novamente.',
        )

    itens_hist = list(nf.itens.all().order_by('n_item', 'id'))
    if not itens_hist:
        raise NFeEntradaFromSaidaError(MSG_SEM_ITENS)

    faltando: list[str] = []
    resolvidos: list[tuple[ItemNFeSaidaHistoricaImportada, Produto, dict[str, Any]]] = []
    for item in itens_hist:
        prod_json = item.prod_json if isinstance(item.prod_json, dict) else {}
        produto = _resolver_produto_de_prod_json(prod_json)
        if not produto:
            label = str(prod_json.get('xProd') or prod_json.get('cProd') or f'item {item.n_item}')
            faltando.append(f'{item.n_item}: {label}')
            continue
        resolvidos.append((item, produto, prod_json))
    if faltando:
        raise NFeEntradaFromSaidaError(f'{MSG_HIST_SEM_PRODUTO} Itens: {"; ".join(faltando[:8])}')

    ambiente = (
        NFeEntrada.AmbienteEmissao.HOMOLOGACAO
        if (nf.tp_amb or '').strip() == '2'
        else NFeEntrada.AmbienteEmissao.PRODUCAO
    )
    numero_ref = (nf.numero or str(nf.pk)).strip()

    entrada = NFeEntrada.objects.create(
        numero=f'EP-DEV-XML-{numero_ref}'[:64],
        data=date.today(),
        tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA,
        status_operacional=NFeEntrada.StatusOperacional.RASCUNHO,
        ambiente_emissao=ambiente,
        empresa_emitente_id=nf.empresa_emitente_id,
        cliente_destinatario=cliente,
        fornecedor=None,
        fin_nfe='4',
        nat_op=(nf.nat_op or NAT_OP_DEVOLUCAO)[:60] or NAT_OP_DEVOLUCAO,
        chave_nfe_referenciada=chave,
        nfe_saida_historica_origem=nf,
        valor_total=Decimal('0'),
    )

    for idx, (item, produto, prod_json) in enumerate(resolvidos, start=1):
        qtd = _dec_prod(prod_json.get('qCom') or prod_json.get('qTrib') or '1')
        v_un = _dec_prod(prod_json.get('vUnCom') or prod_json.get('vUnTrib'))
        v_prod = _dec_prod(prod_json.get('vProd'))
        if v_un <= 0 and qtd > 0 and v_prod > 0:
            v_un = (v_prod / qtd).quantize(Decimal('0.0001'))
        if qtd <= 0:
            qtd = Decimal('1')
        ncm = _digits(prod_json.get('NCM') or prod_json.get('ncm') or getattr(produto, 'ncm', ''), max_len=8)
        cfop_sai = _digits(prod_json.get('CFOP') or prod_json.get('cfop'), max_len=4)
        unidade = str(prod_json.get('uCom') or prod_json.get('uTrib') or produto.unidade or 'UN').strip()[:6]
        ItemNFeEntrada.objects.create(
            nf=entrada,
            produto=produto,
            quantidade=qtd,
            valor=v_un,
            snapshot_produto=build_produto_snapshot(produto),
            numero_item=item.n_item or idx,
            ncm=ncm,
            cfop=cfop_entrada_devolucao_from_saida(cfop_sai),
            unidade=unidade or 'UN',
            descricao_xml=str(prod_json.get('xProd') or produto.descricao or '')[:120],
            impostos_json=impostos_json_from_imposto_xml(
                item.imposto_json if isinstance(item.imposto_json, dict) else {},
            ),
        )

    recalcular_valor_nf_entrada(entrada)
    entrada.refresh_from_db()
    return _resposta_entrada(
        entrada,
        ja_existia=False,
        itens_criados=len(resolvidos),
        mensagem=(
            'Rascunho de entrada própria (devolução) criado a partir da NF-e importada por XML. '
            'Revise e emita pela tela Entrada Própria.'
        ),
    )
