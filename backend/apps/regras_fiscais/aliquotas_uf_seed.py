"""Valores-canônicos da tabela de alíquotas ICMS por UF (seed das migrations 0016/0018).

Alíquotas internas: tabela oficial de grupos de tributação (taxgroup) 2026, informada
por Bruno Lira em 2026-10-29 — não deduzidas.
Interestadual (confirmado pelo contador em 2026-10-29, corrigindo a tabela taxgroup no
ponto do ES): 12% entre as UFs da faixa Sul/Sudeste exceto Espírito Santo; 7% quando o
destino é Norte/Nordeste/Centro-Oeste ou ES. A coluna é keyed pela UF de DESTINO porque
a Nexus emite só de SP (matriz na faixa de 12%).
Matriz origem×destino (27×27) fica no backlog da Sprint 3.11 — implementar se a Nexus
abrir filial em outro estado.
FCP fica NULL de propósito: só se emite FCP destino com a alíquota cadastrada
explicitamente na regra fiscal, sem número presumido.
"""

from __future__ import annotations

from decimal import Decimal

ALICOTAS_ICMS_UF: dict[str, dict[str, Decimal | None]] = {
    'AC': {'interna': Decimal('19'), 'interestadual': Decimal('7'), 'fcp': None},
    'AL': {'interna': Decimal('21.5'), 'interestadual': Decimal('7'), 'fcp': None},
    'AM': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'AP': {'interna': Decimal('18'), 'interestadual': Decimal('7'), 'fcp': None},
    'BA': {'interna': Decimal('20.5'), 'interestadual': Decimal('7'), 'fcp': None},
    'CE': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'DF': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'ES': {'interna': Decimal('17'), 'interestadual': Decimal('7'), 'fcp': None},
    'GO': {'interna': Decimal('19'), 'interestadual': Decimal('7'), 'fcp': None},
    'MA': {'interna': Decimal('23'), 'interestadual': Decimal('7'), 'fcp': None},
    'MG': {'interna': Decimal('18'), 'interestadual': Decimal('12'), 'fcp': None},
    'MS': {'interna': Decimal('17'), 'interestadual': Decimal('7'), 'fcp': None},
    'MT': {'interna': Decimal('17'), 'interestadual': Decimal('7'), 'fcp': None},
    'PA': {'interna': Decimal('19'), 'interestadual': Decimal('7'), 'fcp': None},
    'PB': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'PE': {'interna': Decimal('20.5'), 'interestadual': Decimal('7'), 'fcp': None},
    'PI': {'interna': Decimal('22.5'), 'interestadual': Decimal('7'), 'fcp': None},
    'PR': {'interna': Decimal('19.5'), 'interestadual': Decimal('12'), 'fcp': None},
    'RJ': {'interna': Decimal('22'), 'interestadual': Decimal('12'), 'fcp': None},
    'RN': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'RO': {'interna': Decimal('19.5'), 'interestadual': Decimal('7'), 'fcp': None},
    'RR': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'RS': {'interna': Decimal('17'), 'interestadual': Decimal('12'), 'fcp': None},
    'SC': {'interna': Decimal('17'), 'interestadual': Decimal('12'), 'fcp': None},
    'SE': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
    'SP': {'interna': Decimal('18'), 'interestadual': Decimal('12'), 'fcp': None},
    'TO': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None},
}

ALIQUOTA_INTERESTADUAL_SUL_SUDESTE = Decimal('12')
ALIQUOTA_INTERESTADUAL_DEMAIS = Decimal('7')

# Faixa dos 12%: Regiões Sul e Sudeste, EXCETO o Espírito Santo (contador, 2026-10-29).
UF_FAIXA_INTERESTADUAL_12 = frozenset({'PR', 'RS', 'SC', 'MG', 'RJ', 'SP'})


def interestadual_padrao_para_uf(uf: str) -> Decimal:
    """12% na faixa Sul/Sudeste exceto ES; 7% para Norte/Nordeste/Centro-Oeste e ES."""
    return (
        ALIQUOTA_INTERESTADUAL_SUL_SUDESTE
        if (uf or '').strip().upper()[:2] in UF_FAIXA_INTERESTADUAL_12
        else ALIQUOTA_INTERESTADUAL_DEMAIS
    )
