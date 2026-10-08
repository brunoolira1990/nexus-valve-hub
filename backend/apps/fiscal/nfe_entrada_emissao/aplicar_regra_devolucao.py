"""Aplica RegraFiscalEntrada (DEVOLUCAO_VENDA) em rascunhos de entrada própria."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from apps.fiscal.models import ItemNFeEntrada, NFeEntrada
from apps.fiscal.nfe_entrada_emissao.perfil_devolucao_lucro_presumido import (
    CST_COFINS_DEVOLUCAO_LP,
    CST_IPI_DEVOLUCAO,
    CST_PIS_DEVOLUCAO_LP,
    aplicar_perfil_impostos_devolucao_lucro_presumido,
    cfop_entrada_devolucao_from_saida,
)
from apps.fiscal.nfe_entrada_emissao.validacao import ICMS_NT_CSTS, PIS_COFINS_NT_CSTS
from apps.regras_fiscais.entrada_fiscal import (
    ContextoFiscalEntrada,
    _montar_impostos_esperados,
    encontrar_regra_fiscal_entrada,
)
from apps.regras_fiscais.models import RegraFiscalEntrada
from django.db.models import Q

Q2 = Decimal('0.01')
Q4 = Decimal('0.0001')


def _cfop_entrada_fallback(cfop_saida: str, contexto: ContextoFiscalEntrada | None = None) -> str:
    mesma_uf: bool | None = None
    if contexto and contexto.uf_origem and contexto.uf_destino:
        mesma_uf = contexto.uf_origem == contexto.uf_destino
    return cfop_entrada_devolucao_from_saida(cfop_saida, mesma_uf=mesma_uf)


def _dec(val: Any) -> Decimal | None:
    if val is None or val == '':
        return None
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return None


def _money(val: Decimal) -> str:
    return str(val.quantize(Q2, rounding=ROUND_HALF_UP))


def _pct(val: Decimal) -> str:
    return str(val.quantize(Q4, rounding=ROUND_HALF_UP))


def _uf(party) -> str:
    return (getattr(party, 'uf', None) or '').strip().upper()[:2]


def _carregar_regras_devolucao() -> list[RegraFiscalEntrada]:
    return list(
        RegraFiscalEntrada.objects.filter(ativo=True)
        .filter(
            Q(tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.DEVOLUCAO_VENDA)
            | Q(tipo_operacao_fiscal=''),
        )
        .select_related('produto', 'fornecedor', 'cenario', 'escopo')
        .order_by('-prioridade', 'id')
    )


def montar_contexto_devolucao_venda(
    *,
    empresa_emitente,
    cliente_destinatario=None,
    fornecedor=None,
) -> ContextoFiscalEntrada:
    """UF: origem = emitente (ERP), destino = cliente/fornecedor da devolução."""
    uf_origem = _uf(empresa_emitente)
    uf_destino = _uf(cliente_destinatario) or _uf(fornecedor)
    return ContextoFiscalEntrada(
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        fornecedor_id=getattr(fornecedor, 'pk', None) or getattr(fornecedor, 'id', None),
        tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.DEVOLUCAO_VENDA,
    )


def encontrar_regra_devolucao_venda(
    *,
    cfop_saida: str,
    ncm: str,
    produto_id: int | None,
    contexto: ContextoFiscalEntrada,
    regras: list[RegraFiscalEntrada] | None = None,
) -> RegraFiscalEntrada | None:
    pool = regras if regras is not None else _carregar_regras_devolucao()
    # Preferir regras explicitamente DEVOLUCAO_VENDA; fallback inclui tipo vazio.
    match = encontrar_regra_fiscal_entrada(
        pool,
        cfop_nf=cfop_saida or '',
        ncm_nf=ncm or '',
        contexto=contexto,
        produto_id=produto_id,
        trib=None,
    )
    if not match:
        return None
    regra, _esp = match
    return regra


def _bloco_imposto_calculado(
    *,
    cst: str,
    aliquota: Decimal | None,
    valor_base: Decimal,
    reducao_pct: Decimal | None = None,
    orig: str | None = None,
    nt_csts: frozenset[str],
) -> dict[str, Any]:
    cst_n = (cst or '').strip()
    out: dict[str, Any] = {'cst': cst_n or '41'}
    if orig is not None:
        out['orig'] = str(orig)
    if not cst_n or cst_n in nt_csts:
        return out
    base = valor_base
    if reducao_pct is not None and reducao_pct > 0:
        base = (valor_base * (Decimal('100') - reducao_pct) / Decimal('100')).quantize(
            Q2,
            rounding=ROUND_HALF_UP,
        )
    aliq = aliquota if aliquota is not None else Decimal('0')
    valor = (base * aliq / Decimal('100')).quantize(Q2, rounding=ROUND_HALF_UP)
    out['base'] = _money(base)
    out['aliquota'] = _pct(aliq)
    out['valor'] = _money(valor)
    return out


def impostos_json_from_regra_entrada(
    regra: RegraFiscalEntrada,
    *,
    valor_item: Decimal,
    impostos_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta impostos_json da entrada própria a partir da regra (com fallback da saída/XML)."""
    fb = impostos_fallback if isinstance(impostos_fallback, dict) else {}
    fb_icms = fb.get('icms') if isinstance(fb.get('icms'), dict) else {}
    fb_pis = fb.get('pis') if isinstance(fb.get('pis'), dict) else {}
    fb_cof = fb.get('cofins') if isinstance(fb.get('cofins'), dict) else {}
    fb_ipi = fb.get('ipi') if isinstance(fb.get('ipi'), dict) else {}

    esp = _montar_impostos_esperados(regra)
    v_item = valor_item if valor_item > 0 else Decimal('0')

    cst_icms = (
        (esp.get('cst_icms') or esp.get('csosn') or fb_icms.get('cst') or fb_icms.get('csosn') or '41')
    )
    cst_icms = str(cst_icms).strip()
    orig = str(fb_icms.get('orig') or '0')
    aliq_icms = _dec(esp.get('aliquota_icms'))
    if aliq_icms is None:
        aliq_icms = _dec(fb_icms.get('aliquota'))
    red_icms = _dec(esp.get('reducao_bc_icms'))

    # Devolução LP: CST 98 é o padrão quando a regra não declara PIS/COFINS.
    # (Não herdar CST 01 da saída — isso era o bug visto na revisão fiscal.)
    cst_pis = str(esp.get('cst_pis') or CST_PIS_DEVOLUCAO_LP).strip()
    aliq_pis = _dec(esp.get('aliquota_pis'))
    if aliq_pis is None:
        aliq_pis = _dec(fb_pis.get('aliquota'))
    red_pis = _dec(esp.get('reducao_base_pis'))

    cst_cof = str(esp.get('cst_cofins') or CST_COFINS_DEVOLUCAO_LP).strip()
    aliq_cof = _dec(esp.get('aliquota_cofins'))
    if aliq_cof is None:
        aliq_cof = _dec(fb_cof.get('aliquota'))
    red_cof = _dec(esp.get('reducao_base_cofins'))

    out: dict[str, Any] = {
        'icms': _bloco_imposto_calculado(
            cst=cst_icms,
            aliquota=aliq_icms,
            valor_base=v_item,
            reducao_pct=red_icms,
            orig=orig,
            nt_csts=ICMS_NT_CSTS,
        ),
        'pis': _bloco_imposto_calculado(
            cst=cst_pis,
            aliquota=aliq_pis,
            valor_base=v_item,
            reducao_pct=red_pis,
            nt_csts=PIS_COFINS_NT_CSTS,
        ),
        'cofins': _bloco_imposto_calculado(
            cst=cst_cof,
            aliquota=aliq_cof,
            valor_base=v_item,
            reducao_pct=red_cof,
            nt_csts=PIS_COFINS_NT_CSTS,
        ),
        '_meta': {
            'regra_id': regra.pk,
            'regra_nome': regra.nome,
            'regra_codigo': regra.codigo or '',
            'tipo_operacao_fiscal': regra.tipo_operacao_fiscal or '',
            'origem': 'regra_fiscal_entrada_devolucao_venda',
        },
    }

    # Preserva IPI devolvido e reforma (CBS/IBS) espelhados da saída.
    if isinstance(fb.get('imposto_devol'), dict):
        out['imposto_devol'] = dict(fb['imposto_devol'])
    if isinstance(fb.get('reforma_tributaria'), dict):
        out['reforma_tributaria'] = dict(fb['reforma_tributaria'])
    if isinstance(fb.get('_meta'), dict):
        meta_fb = {k: v for k, v in fb['_meta'].items() if k in ('cfop_saida', 'perfil_devolucao')}
        out['_meta'] = {**meta_fb, **out['_meta']}

    cst_ipi = str(esp.get('cst_ipi') or fb_ipi.get('cst') or '').strip()
    if not cst_ipi and (fb_ipi.get('valor') or fb_ipi.get('base') or fb.get('imposto_devol')):
        cst_ipi = CST_IPI_DEVOLUCAO
    if cst_ipi or fb_ipi:
        aliq_ipi = _dec(esp.get('aliquota_ipi'))
        if aliq_ipi is None:
            aliq_ipi = _dec(fb_ipi.get('aliquota'))
        # CST 49 (devolução): grupo IPI sem tributação; valor vai em imposto_devol.
        out['ipi'] = _bloco_imposto_calculado(
            cst=cst_ipi or CST_IPI_DEVOLUCAO,
            aliquota=aliq_ipi,
            valor_base=v_item,
            nt_csts=frozenset({CST_IPI_DEVOLUCAO}),
        )
        v_ipi_fb = _dec(fb_ipi.get('valor'))
        if v_ipi_fb is not None and v_ipi_fb > 0 and not out.get('imposto_devol'):
            from apps.fiscal.nfe_entrada_emissao.perfil_devolucao_lucro_presumido import P_DEVOL_PADRAO

            out['imposto_devol'] = {
                'p_devol': P_DEVOL_PADRAO,
                'v_ipi_devol': _money(v_ipi_fb),
            }
        if not out['ipi'].get('cst'):
            if fb_ipi:
                out['ipi'] = {**fb_ipi, 'cst': CST_IPI_DEVOLUCAO}
            else:
                del out['ipi']

    return out


def resolver_cfop_e_impostos_devolucao(
    *,
    cfop_saida: str,
    ncm: str,
    produto_id: int | None,
    valor_item: Decimal,
    impostos_fallback: dict[str, Any] | None,
    contexto: ContextoFiscalEntrada,
    regras: list[RegraFiscalEntrada] | None = None,
) -> tuple[str, dict[str, Any], RegraFiscalEntrada | None]:
    """
    Retorna (cfop_entrada, impostos_json, regra_ou_None).
    Sem regra: CFOP convenção 1202/2202 + impostos_fallback.
    """
    regra = encontrar_regra_devolucao_venda(
        cfop_saida=cfop_saida,
        ncm=ncm,
        produto_id=produto_id,
        contexto=contexto,
        regras=regras,
    )
    cfop_fb = _cfop_entrada_fallback(cfop_saida, contexto)
    if regra is None:
        return cfop_fb, impostos_fallback or {}, None

    cfop_reg = ''.join(c for c in (regra.cfop_entrada or '') if c.isdigit())[:4]
    cfop = cfop_reg or cfop_fb
    impostos = impostos_json_from_regra_entrada(
        regra,
        valor_item=valor_item,
        impostos_fallback=impostos_fallback,
    )
    # Perfil LP prevalece sobre CST herdado da saída quando a regra omite PIS/COFINS.
    impostos = aplicar_perfil_impostos_devolucao_lucro_presumido(impostos)
    return cfop, impostos, regra


def aplicar_regras_devolucao_nfe_entrada(nf_entrada: NFeEntrada) -> dict[str, Any]:
    """
    Reaplica DEVOLUCAO_VENDA nos itens de um rascunho ENTRADA_PROPRIA_EMITIDA.
    Não transmite SEFAZ.
    """
    nf = (
        NFeEntrada.objects.select_related('empresa_emitente', 'cliente_destinatario', 'fornecedor')
        .prefetch_related('itens')
        .get(pk=nf_entrada.pk)
    )
    if nf.tipo_origem != NFeEntrada.TipoOrigem.ENTRADA_PROPRIA_EMITIDA:
        raise ValueError('Aplicável apenas a entrada própria emitida.')
    if (nf.status_operacional or '').upper() != NFeEntrada.StatusOperacional.RASCUNHO:
        raise ValueError('Reaplicar regras só é permitido em rascunho.')
    st = (nf.status_emissao_sefaz or '').upper()
    if 'AUTORIZADA' in st:
        raise ValueError('NF-e já autorizada — não é possível reaplicar regras fiscais.')

    contexto = montar_contexto_devolucao_venda(
        empresa_emitente=nf.empresa_emitente,
        cliente_destinatario=nf.cliente_destinatario,
        fornecedor=nf.fornecedor,
    )
    regras = _carregar_regras_devolucao()
    atualizados = 0
    com_regra = 0
    nomes: list[str] = []

    for item in nf.itens.all().order_by('numero_item', 'id'):
        meta = {}
        impostos_atuais = item.impostos_json if isinstance(item.impostos_json, dict) else {}
        if isinstance(impostos_atuais.get('_meta'), dict):
            meta = impostos_atuais['_meta']
        cfop_saida = str(meta.get('cfop_saida') or '').strip()

        v_item = (item.quantidade or Decimal('0')) * (item.valor or Decimal('0'))
        impostos_fb = aplicar_perfil_impostos_devolucao_lucro_presumido(impostos_atuais)
        cfop, impostos, regra = resolver_cfop_e_impostos_devolucao(
            cfop_saida=cfop_saida,
            ncm=item.ncm or '',
            produto_id=item.produto_id,
            valor_item=v_item,
            impostos_fallback=impostos_fb,
            contexto=contexto,
            regras=regras,
        )
        # Garante CST 98/IPI devol mesmo se a regra veio sem PIS/COFINS preenchidos.
        if isinstance(impostos, dict):
            impostos = aplicar_perfil_impostos_devolucao_lucro_presumido(impostos)
        if isinstance(impostos, dict):
            impostos = {**impostos}
            meta_out = impostos.get('_meta') if isinstance(impostos.get('_meta'), dict) else {}
            if not regra:
                meta_out = {k: v for k, v in meta_out.items() if not str(k).startswith('regra')}
                meta_out.pop('origem', None)
                meta_out.pop('tipo_operacao_fiscal', None)
            if cfop_saida:
                meta_out['cfop_saida'] = cfop_saida
            impostos['_meta'] = meta_out

        ItemNFeEntrada.objects.filter(pk=item.pk).update(cfop=cfop, impostos_json=impostos or {})
        atualizados += 1
        if regra:
            com_regra += 1
            if regra.nome not in nomes:
                nomes.append(regra.nome)

    return {
        'ok': True,
        'nf_entrada_id': nf.pk,
        'itens_atualizados': atualizados,
        'itens_com_regra': com_regra,
        'regras': nomes,
        'mensagem': (
            f'Regras aplicadas em {com_regra}/{atualizados} item(ns).'
            + (f' Regra(s): {", ".join(nomes)}.' if nomes else ' Nenhuma regra DEVOLUCAO_VENDA casou — mantido fallback.')
        ),
    }
