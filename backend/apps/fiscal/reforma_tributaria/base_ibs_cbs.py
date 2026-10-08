"""Base de cálculo IBS/CBS 2026 — parametrizada, auditável e comparável."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MODOS_BASE_IBS_CBS = frozenset(
    {
        'BASE_CHEIA_OPERACAO',
        'BASE_SEM_ICMS',
        'BASE_SEM_ICMS_PIS_COFINS',
        'BASE_SEM_ICMS_PIS_COFINS_IPI',
        'BASE_OFICIAL_2026',
        'BASE_CUSTOMIZADA',
    },
)

FONTES_REGRA_BASE = frozenset(
    {
        'oficial',
        'contador',
        'comparativo_erp',
        'manual',
        'pendente',
    },
)

# NT 2025.002 / LC 214/2025 — base = valor operação excluindo IBS/CBS e tributos antigos.
# Adotada como referência para BASE_OFICIAL_2026; exige fonte=oficial|contador para produção.
FORMULA_OFICIAL_2026 = 'vProd - vICMS - vPIS - vCOFINS - vIPI - vISS'

NORMATIVA_REFERENCIA = (
    'NT NF-e/NFC-e 2025.002-RTC (Reforma Tributária do Consumo); '
    'LC 214/2025. Consulta registrada em docs/reforma-tributaria-nfe-nexus.md (2026-05-27). '
    'Base IBS/CBS: valor da operação, excluindo montantes de IBS/CBS e tributos substituídos '
    '(ICMS, ISS, PIS, COFINS), conforme orientação normativa — confirmar com contabilidade antes de produção.'
)


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _dec(val: Any) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        return Decimal(str(val).replace(',', '.'))
    except Exception:
        return Decimal('0')


def _text(val: Any) -> str:
    return (str(val) if val is not None else '').strip()


def _flags_por_modo(modo: str) -> dict[str, bool]:
    m = (modo or 'BASE_CHEIA_OPERACAO').strip().upper()
    if m == 'BASE_SEM_ICMS':
        return {'icms': True, 'pis': False, 'cofins': False, 'ipi': False, 'iss': False}
    if m == 'BASE_SEM_ICMS_PIS_COFINS':
        return {'icms': True, 'pis': True, 'cofins': True, 'ipi': False, 'iss': False}
    if m in ('BASE_SEM_ICMS_PIS_COFINS_IPI', 'BASE_OFICIAL_2026'):
        return {'icms': True, 'pis': True, 'cofins': True, 'ipi': True, 'iss': True}
    if m == 'BASE_CUSTOMIZADA':
        return {'icms': False, 'pis': False, 'cofins': False, 'ipi': False, 'iss': False}
    return {'icms': False, 'pis': False, 'cofins': False, 'ipi': False, 'iss': False}


def resolver_deducoes_base_reforma(reforma_config: dict[str, Any] | None) -> tuple[str, dict[str, bool], str]:
    """
    Retorna (modo, flags dedução, fonte).
    BASE_CUSTOMIZADA usa flags explícitas da regra; demais modos têm flags fixas.
    """
    cfg = reforma_config or {}
    modo = _text(cfg.get('modo_base_ibs_cbs')) or 'BASE_CHEIA_OPERACAO'
    if modo not in MODOS_BASE_IBS_CBS:
        modo = 'BASE_CHEIA_OPERACAO'
    fonte = _text(cfg.get('fonte_regra_base_ibs_cbs')) or 'pendente'
    if fonte not in FONTES_REGRA_BASE:
        fonte = 'pendente'

    flags = _flags_por_modo(modo)
    if modo == 'BASE_CUSTOMIZADA':
        flags = {
            'icms': _truthy(cfg.get('deduzir_icms_base_ibs_cbs')),
            'pis': _truthy(cfg.get('deduzir_pis_base_ibs_cbs')),
            'cofins': _truthy(cfg.get('deduzir_cofins_base_ibs_cbs')),
            'ipi': _truthy(cfg.get('deduzir_ipi_base_ibs_cbs')),
            'iss': _truthy(cfg.get('deduzir_iss_base_ibs_cbs')),
        }
    return modo, flags, fonte


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return _text(val).lower() in ('1', 'true', 'sim', 's', 'yes')


def montar_formula_base(flags: dict[str, bool]) -> str:
    partes = ['vProd']
    if flags.get('icms'):
        partes.append('vICMS')
    if flags.get('pis'):
        partes.append('vPIS')
    if flags.get('cofins'):
        partes.append('vCOFINS')
    if flags.get('ipi'):
        partes.append('vIPI')
    if flags.get('iss'):
        partes.append('vISS')
    if len(partes) == 1:
        return 'vProd'
    return ' - '.join([partes[0]] + partes[1:])


def status_base_reforma(fonte: str, modo: str) -> str:
    if fonte in ('oficial', 'contador'):
        return 'confirmada'
    if fonte == 'comparativo_erp':
        return 'comparativo'
    if fonte == 'manual':
        return 'manual'
    if modo == 'BASE_OFICIAL_2026' and fonte == 'pendente':
        return 'pendente_confirmacao'
    return 'pendente_confirmacao'


@dataclass
class ContextoBaseIbsCbs:
    valor_produto: Decimal
    valor_icms: Decimal = Decimal('0')
    valor_pis: Decimal = Decimal('0')
    valor_cofins: Decimal = Decimal('0')
    valor_ipi: Decimal = Decimal('0')
    valor_iss: Decimal = Decimal('0')
    valor_frete: Decimal = Decimal('0')
    valor_seguro: Decimal = Decimal('0')
    desconto: Decimal = Decimal('0')
    outras_despesas: Decimal = Decimal('0')
    ano_emissao: int = 2026
    ambiente: str = 'homologacao'


@dataclass
class ResultadoBaseIbsCbs:
    base_original_operacao: Decimal
    deducoes_aplicadas: dict[str, Decimal]
    base_ibs_cbs: Decimal
    modo_base_ibs_cbs: str
    formula_base_ibs_cbs: str
    fonte_regra_base_ibs_cbs: str
    status_base_reforma: str
    alertas: list[str] = field(default_factory=list)

    def para_snapshot(self) -> dict[str, str]:
        d = self.deducoes_aplicadas
        return {
            'base_original_reforma': str(_q2(self.base_original_operacao)),
            'base_ibs_cbs': str(_q2(self.base_ibs_cbs)),
            'modo_base_ibs_cbs': self.modo_base_ibs_cbs,
            'valor_deduzido_icms': str(_q2(d.get('icms', Decimal('0')))),
            'valor_deduzido_pis': str(_q2(d.get('pis', Decimal('0')))),
            'valor_deduzido_cofins': str(_q2(d.get('cofins', Decimal('0')))),
            'valor_deduzido_ipi': str(_q2(d.get('ipi', Decimal('0')))),
            'valor_deduzido_iss': str(_q2(d.get('iss', Decimal('0')))),
            'formula_base_ibs_cbs': self.formula_base_ibs_cbs,
            'fonte_regra_base_ibs_cbs': self.fonte_regra_base_ibs_cbs,
            'status_base_reforma': self.status_base_reforma,
        }


def calcular_base_ibs_cbs_2026(
    ctx: ContextoBaseIbsCbs,
    reforma_config: dict[str, Any] | None,
) -> ResultadoBaseIbsCbs:
    """Calcula base IBS/CBS conforme modo configurado na regra."""
    modo, flags, fonte = resolver_deducoes_base_reforma(reforma_config)
    if modo == 'BASE_OFICIAL_2026':
        flags = _flags_por_modo('BASE_SEM_ICMS_PIS_COFINS_IPI')

    base_original = max(
        _dec(ctx.valor_produto)
        + _dec(ctx.valor_frete)
        + _dec(ctx.valor_seguro)
        + _dec(ctx.outras_despesas)
        - _dec(ctx.desconto),
        Decimal('0'),
    )
    base_original = _q2(base_original)

    deducoes: dict[str, Decimal] = {}
    alertas: list[str] = []
    if flags.get('icms'):
        deducoes['icms'] = _q2(_dec(ctx.valor_icms))
    if flags.get('pis'):
        deducoes['pis'] = _q2(_dec(ctx.valor_pis))
    if flags.get('cofins'):
        deducoes['cofins'] = _q2(_dec(ctx.valor_cofins))
    if flags.get('ipi'):
        deducoes['ipi'] = _q2(_dec(ctx.valor_ipi))
    if flags.get('iss'):
        deducoes['iss'] = _q2(_dec(ctx.valor_iss))

    total_ded = sum(deducoes.values(), Decimal('0'))
    base = max(Decimal('0'), _q2(base_original - total_ded))
    formula = montar_formula_base(flags)
    if modo == 'BASE_OFICIAL_2026':
        formula = FORMULA_OFICIAL_2026

    st = status_base_reforma(fonte, modo)
    if fonte == 'pendente' and modo != 'BASE_CHEIA_OPERACAO':
        alertas.append(
            'Base IBS/CBS calculada com regra pendente de confirmação oficial/contábil.',
        )
    if total_ded > base_original:
        alertas.append('Deduções superiores à base original da operação — base zerada.')

    return ResultadoBaseIbsCbs(
        base_original_operacao=base_original,
        deducoes_aplicadas=deducoes,
        base_ibs_cbs=base,
        modo_base_ibs_cbs=modo,
        formula_base_ibs_cbs=formula,
        fonte_regra_base_ibs_cbs=fonte,
        status_base_reforma=st,
        alertas=alertas,
    )


def _calcular_valores_cenario(
    base: Decimal,
    *,
    aliquota_cbs: Decimal,
    aliquota_ibs_uf: Decimal,
    aliquota_ibs_mun: Decimal = Decimal('0'),
) -> dict[str, str]:
    v_cbs = _q2(base * aliquota_cbs / Decimal('100')) if aliquota_cbs else Decimal('0')
    v_ibs = _q2(base * aliquota_ibs_uf / Decimal('100')) if aliquota_ibs_uf else Decimal('0')
    v_mun = _q2(base * aliquota_ibs_mun / Decimal('100')) if aliquota_ibs_mun else Decimal('0')
    return {
        'base_ibs_cbs': str(base),
        'valor_cbs': str(v_cbs),
        'valor_ibs_estadual': str(v_ibs),
        'valor_ibs_municipal': str(v_mun),
        'valor_total_ibs_cbs': str(_q2(v_cbs + v_ibs + v_mun)),
    }


def diagnosticar_base_reforma_cenarios(
    ctx: ContextoBaseIbsCbs,
    *,
    aliquota_cbs: Any,
    aliquota_ibs_uf: Any,
    aliquota_ibs_mun: Any = None,
) -> list[dict[str, Any]]:
    """Comparativo técnico A–D — não altera cálculo ativo."""
    ali_cbs = _dec(aliquota_cbs)
    ali_uf = _dec(aliquota_ibs_uf)
    ali_mun = _dec(aliquota_ibs_mun)
    cenarios: list[tuple[str, str]] = [
        ('A', 'BASE_CHEIA_OPERACAO'),
        ('B', 'BASE_SEM_ICMS'),
        ('C', 'BASE_SEM_ICMS_PIS_COFINS'),
        ('D', 'BASE_SEM_ICMS_PIS_COFINS_IPI'),
    ]
    out: list[dict[str, Any]] = []
    for letra, modo in cenarios:
        res = calcular_base_ibs_cbs_2026(ctx, {'modo_base_ibs_cbs': modo, 'fonte_regra_base_ibs_cbs': 'pendente'})
        vals = _calcular_valores_cenario(
            res.base_ibs_cbs,
            aliquota_cbs=ali_cbs,
            aliquota_ibs_uf=ali_uf,
            aliquota_ibs_mun=ali_mun,
        )
        out.append(
            {
                'cenario': letra,
                'modo': modo,
                'formula': res.formula_base_ibs_cbs,
                'base_original': str(res.base_original_operacao),
                'deducoes': {k: str(v) for k, v in res.deducoes_aplicadas.items()},
                **vals,
            },
        )
    return out


def comparar_reforma_xml_externo(
    xml_nexus: str,
    xml_externo: str,
) -> dict[str, Any]:
    """Diagnóstico comparativo — não altera regra automaticamente."""
    import re

    def _extrair(tag: str, xml: str) -> Decimal | None:
        m = re.search(rf'<{tag}>([^<]+)</{tag}>', xml, re.I)
        if not m:
            return None
        return _dec(m.group(1))

    campos = [
        'vProd',
        'vICMS',
        'vPIS',
        'vCOFINS',
        'vNF',
        'vCBS',
        'vIBSUF',
    ]
    diff: dict[str, dict[str, str | None]] = {}
    for c in campos:
        a = _extrair(c, xml_nexus)
        b = _extrair(c, xml_externo)
        if a is None and b is None:
            continue
        diff[c] = {
            'nexus': str(a) if a is not None else None,
            'externo': str(b) if b is not None else None,
            'igual': str(a == b) if a is not None and b is not None else 'na',
        }

    vbc_n = _extrair('vBC', xml_nexus)
    vbc_e = _extrair('vBC', xml_externo)
    vbc_igual = vbc_n is not None and vbc_e is not None and vbc_n == vbc_e
    formula_provavel = 'indeterminada'
    if vbc_n is not None and diff.get('vProd', {}).get('nexus'):
        vp = _dec(diff['vProd']['nexus'])
        if vbc_n == vp:
            formula_provavel = 'vProd'
        elif diff.get('vICMS', {}).get('nexus') and vbc_n == _q2(vp - _dec(diff['vICMS']['nexus'])):
            formula_provavel = 'vProd - vICMS'
    divergente = any(v.get('igual') == 'False' for v in diff.values()) or (
        vbc_n is not None and vbc_e is not None and not vbc_igual
    )
    return {
        'campos': diff,
        'vbc_ibs_cbs': {
            'nexus': str(vbc_n) if vbc_n is not None else None,
            'externo': str(vbc_e) if vbc_e is not None else None,
            'igual': str(vbc_igual) if vbc_n is not None and vbc_e is not None else 'na',
        },
        'formula_provavel_externo': formula_provavel,
        'resultado': 'igual' if not divergente else 'divergente',
    }
