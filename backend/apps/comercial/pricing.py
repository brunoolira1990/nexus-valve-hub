"""Formação de preço da proposta comercial (regra validada: divisor fixo 0,60)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from apps.regras_fiscais.models import RegraFiscal

PRECO_BASE_DIVISOR = Decimal('0.60')


def normalize_ncm(ncm: str) -> str:
    return ''.join(c for c in (ncm or '') if c.isdigit())


def ncm_fiscal_valido(ncm: str) -> bool:
    """NCM brasileiro: ao menos 8 dígitos após normalização."""
    return len(normalize_ncm(ncm)) >= 8


def find_regra_fiscal_saida_com_fallback(
    ncm: str,
    uf_origem: str,
    uf_destino: str,
    operacao: str = 'Saída',
    **kwargs,
):
    """Delega ao motor de saída (cenário + fallback legado conforme settings)."""
    from apps.regras_fiscais.saida_fiscal import find_regra_fiscal_saida_com_fallback as _buscar

    return _buscar(ncm, uf_origem, uf_destino, operacao, **kwargs)


def find_regra_fiscal(
    ncm: str,
    uf_origem: str,
    uf_destino: str,
    operacao: str,
) -> Optional[RegraFiscal]:
    uo = (uf_origem or '').strip().upper()[:2]
    ud = (uf_destino or '').strip().upper()[:2]
    op = (operacao or '').strip()
    target = normalize_ncm(ncm)
    if not target or len(uo) != 2 or len(ud) != 2 or not op:
        return None
    qs = RegraFiscal.objects.filter(uf_origem=uo, uf_destino=ud, operacao=op)
    for r in qs.only('id', 'ncm', 'uf_origem', 'uf_destino', 'operacao', 'aliquota_icms', 'aliquota_pis', 'aliquota_cofins', 'aliquota_ipi'):
        if normalize_ncm(r.ncm) == target:
            return r
    return None


def float_to_dec(v) -> Decimal:
    if v is None:
        return Decimal('0')
    return Decimal(str(v))


def compute_ipi_entrada_valor(custo_produto: Decimal, ipi_entrada_percentual: Decimal, ipi_custo_legacy: Decimal) -> Decimal:
    if ipi_entrada_percentual and ipi_entrada_percentual > 0:
        return (custo_produto * (ipi_entrada_percentual / Decimal('100'))).quantize(Decimal('0.01'))
    return ipi_custo_legacy.quantize(Decimal('0.01'))


def compute_custo_carregado(
    custo_produto: Decimal,
    ipi_entrada_valor: Decimal,
    st_valor: Decimal,
    frete_entrada: Decimal,
    despesas_entrada: Decimal,
    outros_entrada: Decimal,
) -> Decimal:
    return (custo_produto + ipi_entrada_valor + st_valor + frete_entrada + despesas_entrada + outros_entrada).quantize(
        Decimal('0.01')
    )


def compute_preco_base(custo_carregado: Decimal) -> Decimal:
    if PRECO_BASE_DIVISOR <= 0:
        return Decimal('0')
    return (custo_carregado / PRECO_BASE_DIVISOR).quantize(Decimal('0.01'))


def percentual_saida_total(
    icms: Decimal,
    pis: Decimal,
    cofins: Decimal,
    ipi_saida: Decimal,
    irpj: Decimal,
    csll: Decimal,
    comissao: Decimal,
) -> Decimal:
    return (icms + pis + cofins + ipi_saida + irpj + csll + comissao).quantize(Decimal('0.01'))


def compute_valor_carga_saida(preco_ref: Decimal, percentual_saida: Decimal) -> Decimal:
    if preco_ref <= 0:
        return Decimal('0')
    return (preco_ref * (percentual_saida / Decimal('100'))).quantize(Decimal('0.01'))


def compute_lucro_margem(
    preco_ref: Decimal,
    custo_carregado: Decimal,
    valor_carga_saida: Decimal,
    frete_saida: Decimal,
    outras_despesas_saida: Decimal,
) -> Tuple[Decimal, Decimal]:
    lucro = (preco_ref - custo_carregado - valor_carga_saida - frete_saida - outras_despesas_saida).quantize(Decimal('0.01'))
    margem = Decimal('0')
    if preco_ref > 0:
        margem = ((lucro / preco_ref) * Decimal('100')).quantize(Decimal('0.01'))
    return lucro, margem
