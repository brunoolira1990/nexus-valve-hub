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
Regime de base do DIFAL (`base_dupla`, Sprint 3.11): True nas UFs cujo DIFAL é calculado
"por dentro" (base dupla) e False nas que usam a diferença de alíquotas sobre a BC da
operação (base única). RN não veio em nenhuma das duas listas e ficou em base única —
confirmar com o contador antes de emitir nota para RN.
"""

from __future__ import annotations

from decimal import Decimal

ALICOTAS_ICMS_UF: dict[str, dict[str, Decimal | bool | None]] = {
    'AC': {'interna': Decimal('19'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'AL': {'interna': Decimal('21.5'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'AM': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'AP': {'interna': Decimal('18'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'BA': {'interna': Decimal('20.5'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'CE': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'DF': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'ES': {'interna': Decimal('17'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'GO': {'interna': Decimal('19'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'MA': {'interna': Decimal('23'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'MG': {'interna': Decimal('18'), 'interestadual': Decimal('12'), 'fcp': None, 'base_dupla': True},
    'MS': {'interna': Decimal('17'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'MT': {'interna': Decimal('17'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'PA': {'interna': Decimal('19'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'PB': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'PE': {'interna': Decimal('20.5'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'PI': {'interna': Decimal('22.5'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'PR': {'interna': Decimal('19.5'), 'interestadual': Decimal('12'), 'fcp': None, 'base_dupla': True},
    'RJ': {'interna': Decimal('22'), 'interestadual': Decimal('12'), 'fcp': None, 'base_dupla': True},
    'RN': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'RO': {'interna': Decimal('19.5'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'RR': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': False},
    'RS': {'interna': Decimal('17'), 'interestadual': Decimal('12'), 'fcp': None, 'base_dupla': True},
    'SC': {'interna': Decimal('17'), 'interestadual': Decimal('12'), 'fcp': None, 'base_dupla': True},
    'SE': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
    'SP': {'interna': Decimal('18'), 'interestadual': Decimal('12'), 'fcp': None, 'base_dupla': False},
    'TO': {'interna': Decimal('20'), 'interestadual': Decimal('7'), 'fcp': None, 'base_dupla': True},
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
