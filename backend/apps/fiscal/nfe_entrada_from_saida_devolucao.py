"""Gera rascunho de NF-e entrada própria (devolução/recusa) a partir de NF-e Saída autorizada."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.fiscal.models import ItemNFeEntrada, ItemNFeSaida, NFeEntrada, NFeSaida
from apps.fiscal.nfe_emissao.empresa_emitente import resolver_empresa_emitente_nfe
from apps.fiscal.serializers import NFeEntradaSerializer, recalcular_valor_nf_entrada
from apps.fiscal.snapshot_fiscal_helpers import (
    cfop_from_snapshot_fiscal,
    get_cofins_snapshot,
    get_icms_snapshot,
    get_ncm_snapshot,
    get_pis_snapshot,
)
from apps.produtos.snapshot import build_produto_snapshot

NAT_OP_DEVOLUCAO = 'Devolução de mercadoria'
MSG_SEM_CHAVE = 'NF-e de saída sem chave de acesso autorizada.'
MSG_NAO_AUTORIZADA = 'Gere a entrada própria apenas a partir de NF-e Saída autorizada na SEFAZ.'
MSG_SEM_ITENS = 'NF-e de saída sem itens para espelhar na entrada própria.'
MSG_SEM_EMITENTE = 'Empresa emitente da NF-e de saída não resolvida.'
MSG_SEM_CLIENTE = 'NF-e de saída sem cliente — necessário para destinatário da entrada própria.'
MSG_CANCELADA = 'NF-e de saída cancelada não pode gerar entrada própria.'


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


def _buscar_entrada_existente(nf_saida: NFeSaida) -> NFeEntrada | None:
    qs = NFeEntrada.objects.filter(tipo_origem=NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA)
    por_fk = qs.filter(nfe_saida_origem_id=nf_saida.pk).order_by('-id').first()
    if por_fk:
        return por_fk
    chave = (nf_saida.chave_acesso or '').strip()
    if len(chave) == 44:
        return qs.filter(chave_nfe_referenciada=chave).order_by('-id').first()
    return None


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

    existente = _buscar_entrada_existente(nf)
    if existente:
        ser = NFeEntradaSerializer(existente)
        return {
            'ok': True,
            'ja_existia': True,
            'nf_entrada_id': existente.pk,
            'numero': existente.numero,
            'tipo_origem': existente.tipo_origem,
            'status_operacional': existente.status_operacional,
            'mensagem': 'Já existe entrada própria vinculada a esta NF-e de saída.',
            'nfe_entrada': ser.data,
        }

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
    ser = NFeEntradaSerializer(entrada)
    return {
        'ok': True,
        'ja_existia': False,
        'nf_entrada_id': entrada.pk,
        'numero': entrada.numero,
        'tipo_origem': entrada.tipo_origem,
        'status_operacional': entrada.status_operacional,
        'itens_criados': len(itens_saida),
        'mensagem': (
            'Rascunho de entrada própria (devolução) criado a partir da NF-e de saída. '
            'Revise e emita pela tela Entrada Própria.'
        ),
        'nfe_entrada': ser.data,
    }
