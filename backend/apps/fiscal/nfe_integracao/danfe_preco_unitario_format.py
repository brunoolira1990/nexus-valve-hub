"""Formatação visual do preço unitário no DANFE (min 2 / max 3 casas).

Não altera XML nem persistência — apenas a string exibida nas colunas
``vUnCom`` / ``vUnTrib`` via override em ``DanfeNexus._get_products_info``.

Alinhado ao padrão brasileiro do BrazilFiscalReport 0.7.4
(milhar ``.``, decimal ``,``), sem usar ``float``.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

__all__ = ['format_preco_unitario_danfe']

_QUANT_MAX = Decimal('0.001')
_QUANT_MIN = Decimal('0.01')


def _com_separador_milhar(parte_inteira: str) -> str:
    digitos = parte_inteira.lstrip('+') or '0'
    negativo = digitos.startswith('-')
    if negativo:
        digitos = digitos[1:]
    digitos = digitos.lstrip('0') or '0'
    grupos: list[str] = []
    while len(digitos) > 3:
        grupos.append(digitos[-3:])
        digitos = digitos[:-3]
    grupos.append(digitos)
    formatado = '.'.join(reversed(grupos))
    return f'-{formatado}' if negativo else formatado


def format_preco_unitario_danfe(valor) -> str:
    """
    Exibe preço unitário no DANFE: mínimo 2 e máximo 3 casas decimais.

    A terceira casa aparece somente quando significativa após
    ``ROUND_HALF_UP`` em 3 casas (valores históricos com 4+ casas
    são limitados visualmente a 3; o XML permanece intacto).
    """
    if valor is None or str(valor).strip() == '':
        d = Decimal('0')
    else:
        d = Decimal(str(valor).strip())

    d3 = d.quantize(_QUANT_MAX, rounding=ROUND_HALF_UP)
    d2 = d.quantize(_QUANT_MIN, rounding=ROUND_HALF_UP)
    if d3 == d2:
        casas = 2
        d_exibir = d2
    else:
        casas = 3
        d_exibir = d3

    # format(Decimal, '.Nf') usa ponto decimal e não introduz float.
    texto = format(d_exibir, f'.{casas}f')
    if '.' in texto:
        inteira, fracao = texto.split('.', 1)
    else:
        inteira, fracao = texto, '0' * casas
    return f'{_com_separador_milhar(inteira)},{fracao}'
