"""Motor de avaliação fiscal read-only para itens da conferência de NF-e entrada."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, TypedDict

from apps.comercial.pricing import normalize_ncm
from apps.fiscal.models import ItemNFeEntradaConferencia, NFeEntradaConferencia
from apps.fiscal.services.imposto_item_xml import extrair_tributos_item
from apps.regras_fiscais.cst_icms_perspectiva import (
    normalizar_cst_icms_xml_para_entrada,
    obter_cst_icms_bruto_nf,
)
from apps.regras_fiscais.cst_ipi_perspectiva import normalizar_cst_ipi_xml_para_entrada
from apps.regras_fiscais.cst_pis_cofins_perspectiva import normalizar_cst_pis_cofins_xml_para_entrada
from apps.regras_fiscais.models import RegraFiscalEntrada
from apps.regras_fiscais.reforma_tributaria_config import (
    reforma_tributaria_para_snapshot,
    reforma_tributaria_preenchida,
)

MSG_SEM_REGRA_FISCAL_ENTRADA = (
    'Não há regra fiscal de entrada configurada para este CFOP/NCM/UF. '
    'Cadastre uma regra ou valide com o fiscal.'
)

TOLERANCIA_ALIQUOTA = Decimal('0.01')
TOLERANCIA_VALOR = Decimal('0.01')


class DivergenciaFiscalDict(TypedDict):
    campo: str
    label: str
    esperado: str
    informado: str
    mensagem: str


class ImpostosSnapshotDict(TypedDict, total=False):
    cst_icms: str
    csosn: str
    modalidade_bc_icms: str
    aliquota_icms: str
    reducao_bc_icms: str
    motivo_desoneracao_icms: str
    codigo_beneficio_icms: str
    icms_st_aplicavel: str
    cst_icms_st: str
    aliquota_icms_st: str
    mva_st: str
    reducao_bc_st: str
    cst_ipi: str
    tipo_calculo_ipi: str
    aliquota_ipi: str
    valor_ipi_unidade: str
    enquadramento_ipi: str
    cst_pis: str
    tipo_calculo_pis: str
    aliquota_pis: str
    reducao_base_pis: str
    valor_minimo_pis_unidade: str
    aliquota_pis_st: str
    cst_cofins: str
    tipo_calculo_cofins: str
    aliquota_cofins: str
    reducao_base_cofins: str
    valor_minimo_cofins_unidade: str
    aliquota_cofins_st: str
    fcp_aplicavel: str
    aliquota_fcp: str
    aliquota_fcp_st: str
    reducao_bc_fcp: str
    valor_fcp_unidade: str


class ResultadoFiscalEntradaOpcionalDict(TypedDict, total=False):
    tem_reforma_configurada: bool
    reforma_tributaria_esperada: dict[str, str]


class ResultadoFiscalEntradaDict(ResultadoFiscalEntradaOpcionalDict):
    status: str
    regra_id: int | None
    regra_nome: str
    regra_codigo: str
    descricao_cenario: str
    regra_score_especificidade: int
    regra_prioridade: int
    regra_match_motivos: list[str]
    severidade: str
    mensagens: list[str]
    movimenta_estoque: bool | None
    exige_certificado_fornecedor: bool | None
    permite_credito_fiscal: bool | None
    cfop_nf: str
    cfop_entrada_esperado: str
    ncm_nf: str
    cst_icms_nf: str
    csosn_nf: str
    cst_pis_nf: str
    cst_cofins_nf: str
    cst_ipi_nf: str
    impostos_nf: ImpostosSnapshotDict
    impostos_esperados: ImpostosSnapshotDict
    divergencias: list[DivergenciaFiscalDict]


@dataclass(frozen=True)
class ContextoFiscalEntrada:
    uf_origem: str = ''
    uf_destino: str = ''
    fornecedor_id: int | None = None
    tipo_operacao_fiscal: str = ''


@dataclass(frozen=True)
class EspecificidadeRegraEntrada:
    score: int
    motivos: list[str]


# Pontuação de especificidade (maior = regra mais específica).
SCORE_BASE_REGRA_GERAL = 10
SCORE_PRODUTO = 1000
SCORE_FORNECEDOR = 200
SCORE_NCM_EXATO = 500
SCORE_NCM_PREFIXO = 300
SCORE_CFOP_ORIGEM = 150
SCORE_UF_ORIGEM = 80
SCORE_UF_DESTINO = 80
SCORE_TIPO_OPERACAO = 100


class ResumoFiscalConferenciaDict(TypedDict):
    total_itens: int
    ok: int
    alerta: int
    sem_regra: int
    bloqueado: int
    movimenta_estoque: int
    exige_certificado_fornecedor: int
    ignorados: int
    uf_origem: str
    uf_destino: str


def _only_digits(value: str) -> str:
    return ''.join(c for c in (value or '') if c.isdigit())


def _norm_cfop(value: str) -> str:
    return _only_digits(value)


def _cfop_origem_regra(regra: RegraFiscalEntrada) -> str:
    return _norm_cfop((regra.cfop_origem or '').strip() or (regra.cfop or '').strip())


def _uf_from_party(party: dict[str, Any] | None) -> str:
    if not isinstance(party, dict):
        return ''
    for key in ('UF', 'uf'):
        val = party.get(key)
        if val:
            return str(val).strip().upper()[:2]
    for nest in ('enderEmit', 'enderDest', 'ender'):
        sub = party.get(nest)
        if isinstance(sub, dict):
            u = sub.get('UF') or sub.get('uf')
            if u:
                return str(u).strip().upper()[:2]
    return ''


def montar_contexto_fiscal_entrada(conferencia: NFeEntradaConferencia) -> ContextoFiscalEntrada:
    nf = conferencia.nf_entrada_historica
    uf_origem = ''
    uf_destino = ''
    if nf.fornecedor_emitente_id and getattr(nf.fornecedor_emitente, 'uf', None):
        uf_origem = (nf.fornecedor_emitente.uf or '').strip().upper()[:2]
    if not uf_origem:
        uf_origem = _uf_from_party(nf.emit_json if isinstance(nf.emit_json, dict) else None)
    if nf.empresa_destinataria_id and getattr(nf.empresa_destinataria, 'uf', None):
        uf_destino = (nf.empresa_destinataria.uf or '').strip().upper()[:2]
    if not uf_destino:
        uf_destino = _uf_from_party(nf.dest_json if isinstance(nf.dest_json, dict) else None)
    fornecedor_id = nf.fornecedor_emitente_id
    return ContextoFiscalEntrada(
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        fornecedor_id=fornecedor_id,
        tipo_operacao_fiscal='',
    )


def _fmt_decimal(val: Decimal | None, *, casas: int = 2) -> str:
    if val is None:
        return ''
    q = Decimal('1').scaleb(-casas)
    return f'{val.quantize(q):.{casas}f}'


def _fmt_bool(val: bool | None) -> str:
    if val is None:
        return ''
    return 'sim' if val else 'nao'


def _dec_preenchido(val: Decimal | None) -> bool:
    return val is not None


def _str_preenchido(val: str | None) -> bool:
    return bool((val or '').strip())


def _dec_iguais(esperado: Decimal, informado: Decimal, tolerancia: Decimal) -> bool:
    return abs(esperado - informado) <= tolerancia


def _montar_impostos_nf(trib: dict[str, Any]) -> ImpostosSnapshotDict:
    csosn = str(trib.get('csosn') or trib.get('cst_icms_detalhe') or '').strip()
    cst_icms = str(trib.get('cst_icms') or '').strip()
    snap: ImpostosSnapshotDict = {}
    if cst_icms:
        snap['cst_icms'] = cst_icms
    if csosn:
        snap['csosn'] = csosn
    if trib.get('modalidade_bc_icms'):
        snap['modalidade_bc_icms'] = str(trib['modalidade_bc_icms']).strip()
    if trib.get('aliquota_icms') is not None:
        snap['aliquota_icms'] = _fmt_decimal(trib['aliquota_icms'])
    if trib.get('reducao_bc_icms') is not None:
        snap['reducao_bc_icms'] = _fmt_decimal(trib['reducao_bc_icms'])
    if trib.get('motivo_desoneracao_icms'):
        snap['motivo_desoneracao_icms'] = str(trib['motivo_desoneracao_icms']).strip()
    if trib.get('codigo_beneficio_icms'):
        snap['codigo_beneficio_icms'] = str(trib['codigo_beneficio_icms']).strip()
    if trib.get('icms_st_aplicavel_nf') is not None:
        snap['icms_st_aplicavel'] = _fmt_bool(bool(trib['icms_st_aplicavel_nf']))
    if trib.get('cst_icms_st_nf'):
        snap['cst_icms_st'] = str(trib['cst_icms_st_nf']).strip()
    if trib.get('aliquota_icms_st') is not None:
        snap['aliquota_icms_st'] = _fmt_decimal(trib['aliquota_icms_st'])
    if trib.get('mva_st') is not None:
        snap['mva_st'] = _fmt_decimal(trib['mva_st'])
    if trib.get('reducao_bc_st') is not None:
        snap['reducao_bc_st'] = _fmt_decimal(trib['reducao_bc_st'])
    if trib.get('fcp_presente_nf') is not None:
        snap['fcp_aplicavel'] = _fmt_bool(bool(trib.get('fcp_presente_nf')))
    if trib.get('aliquota_fcp') is not None:
        snap['aliquota_fcp'] = _fmt_decimal(trib['aliquota_fcp'])
    if trib.get('aliquota_fcp_st') is not None:
        snap['aliquota_fcp_st'] = _fmt_decimal(trib['aliquota_fcp_st'])
    if trib.get('reducao_bc_fcp') is not None:
        snap['reducao_bc_fcp'] = _fmt_decimal(trib['reducao_bc_fcp'])
    if trib.get('valor_fcp_unidade') is not None:
        snap['valor_fcp_unidade'] = _fmt_decimal(trib['valor_fcp_unidade'], casas=4)
    if trib.get('cst_ipi'):
        snap['cst_ipi'] = str(trib['cst_ipi']).strip()
    if trib.get('aliquota_ipi') is not None:
        snap['aliquota_ipi'] = _fmt_decimal(trib['aliquota_ipi'])
    if trib.get('valor_ipi_unidade') is not None:
        snap['valor_ipi_unidade'] = _fmt_decimal(trib['valor_ipi_unidade'], casas=4)
    if trib.get('enquadramento_ipi'):
        snap['enquadramento_ipi'] = str(trib['enquadramento_ipi']).strip()
    if trib.get('cst_pis'):
        snap['cst_pis'] = str(trib['cst_pis']).strip()
    if trib.get('aliquota_pis') is not None:
        snap['aliquota_pis'] = _fmt_decimal(trib['aliquota_pis'])
    if trib.get('reducao_base_pis') is not None:
        snap['reducao_base_pis'] = _fmt_decimal(trib['reducao_base_pis'])
    if trib.get('cst_cofins'):
        snap['cst_cofins'] = str(trib['cst_cofins']).strip()
    if trib.get('aliquota_cofins') is not None:
        snap['aliquota_cofins'] = _fmt_decimal(trib['aliquota_cofins'])
    if trib.get('reducao_base_cofins') is not None:
        snap['reducao_base_cofins'] = _fmt_decimal(trib['reducao_base_cofins'])
    return snap


def _divergencia(
    *,
    campo: str,
    label: str,
    esperado: str,
    informado: str,
    mensagem: str,
) -> DivergenciaFiscalDict:
    return {
        'campo': campo,
        'label': label,
        'esperado': esperado,
        'informado': informado or '—',
        'mensagem': mensagem,
    }


def _normalizar_cst_comparacao(val: str) -> str:
    """Remove zeros à esquerda para comparar códigos CST equivalentes (ex.: 060 vs 60)."""
    s = (val or '').strip()
    if not s:
        return ''
    digits = ''.join(ch for ch in s if ch.isdigit())
    if not digits:
        return s
    return digits.lstrip('0') or '0'


def _comparar_texto(
    *,
    campo: str,
    label: str,
    esperado: str,
    informado: str,
    informado_alt: str = '',
    normalizar_cst: bool = False,
) -> DivergenciaFiscalDict | None:
    exp = (esperado or '').strip()
    if not exp:
        return None
    at = (informado or '').strip()
    alt = (informado_alt or '').strip()
    if normalizar_cst:
        if _normalizar_cst_comparacao(exp) == _normalizar_cst_comparacao(at):
            return None
    elif exp == at or exp == alt:
        return None
    inf = at or alt or '—'
    return _divergencia(
        campo=campo,
        label=label,
        esperado=exp,
        informado=inf,
        mensagem=f'{label} divergente: esperado "{exp}", informado "{inf}".',
    )


def _comparar_decimal(
    *,
    campo: str,
    label: str,
    esperado: Decimal,
    informado: Decimal | None,
    tolerancia: Decimal,
    sufixo: str = '%',
) -> DivergenciaFiscalDict | None:
    if informado is None:
        return _divergencia(
            campo=campo,
            label=label,
            esperado=_fmt_decimal(esperado),
            informado='—',
            mensagem=f'{label} divergente: esperado {_fmt_decimal(esperado)}{sufixo}, NF sem valor.',
        )
    if _dec_iguais(esperado, informado, tolerancia):
        return None
    esp = _fmt_decimal(esperado)
    inf = _fmt_decimal(informado)
    return _divergencia(
        campo=campo,
        label=label,
        esperado=esp,
        informado=inf,
        mensagem=f'{label} divergente: esperado {esp}{sufixo}, informado {inf}{sufixo}.',
    )


def _nf_tem_fcp(trib: dict[str, Any]) -> bool:
    return bool(trib.get('fcp_presente_nf'))


def _comparar_fcp_aplicavel(
    regra: RegraFiscalEntrada,
    trib: dict[str, Any],
) -> DivergenciaFiscalDict | None:
    if regra.fcp_aplicavel is None:
        return None
    nf_fcp = _nf_tem_fcp(trib)
    if regra.fcp_aplicavel == nf_fcp:
        return None
    esp = _fmt_bool(regra.fcp_aplicavel)
    inf = _fmt_bool(nf_fcp)
    return _divergencia(
        campo='fcp_aplicavel',
        label='FCP aplicável',
        esperado=esp,
        informado=inf,
        mensagem=f'FCP divergente: regra indica "{esp}", NF indica presença de FCP "{inf}".',
    )


def _comparar_decimal_fcp(
    *,
    campo: str,
    label: str,
    esperado: Decimal,
    trib: dict[str, Any],
    chave_nf: str,
    tolerancia: Decimal,
    sufixo: str = '%',
) -> DivergenciaFiscalDict | None:
    informado = trib.get(chave_nf)
    if informado is None and not _nf_tem_fcp(trib):
        return _divergencia(
            campo=campo,
            label=label,
            esperado=_fmt_decimal(esperado),
            informado='—',
            mensagem=(
                f'{label}: regra configurada ({_fmt_decimal(esperado)}{sufixo}), '
                'mas a NF não informa FCP no XML para comparar.'
            ),
        )
    return _comparar_decimal(
        campo=campo,
        label=label,
        esperado=esperado,
        informado=informado,
        tolerancia=tolerancia,
        sufixo=sufixo,
    )


def _comparar_icms_st(
    regra: RegraFiscalEntrada,
    trib: dict[str, Any],
) -> DivergenciaFiscalDict | None:
    if regra.icms_st_aplicavel is None:
        return None
    nf_st = bool(trib.get('icms_st_aplicavel_nf'))
    if regra.icms_st_aplicavel == nf_st:
        return None
    esp = _fmt_bool(regra.icms_st_aplicavel)
    inf = _fmt_bool(nf_st)
    return _divergencia(
        campo='icms_st_aplicavel',
        label='ICMS ST aplicável',
        esperado=esp,
        informado=inf,
        mensagem=f'ICMS ST divergente: regra indica "{esp}", NF indica "{inf}".',
    )


def _montar_impostos_esperados(regra: RegraFiscalEntrada) -> ImpostosSnapshotDict:
    snap: ImpostosSnapshotDict = {}
    if _str_preenchido(regra.cst_icms_esperado):
        snap['cst_icms'] = regra.cst_icms_esperado.strip()
    if _str_preenchido(regra.csosn_esperado):
        snap['csosn'] = regra.csosn_esperado.strip()
    if _str_preenchido(regra.modalidade_bc_icms):
        snap['modalidade_bc_icms'] = regra.modalidade_bc_icms.strip()
    if _dec_preenchido(regra.aliquota_icms):
        snap['aliquota_icms'] = _fmt_decimal(regra.aliquota_icms)
    if _dec_preenchido(regra.reducao_bc_icms):
        snap['reducao_bc_icms'] = _fmt_decimal(regra.reducao_bc_icms)
    if _str_preenchido(regra.motivo_desoneracao_icms):
        snap['motivo_desoneracao_icms'] = regra.motivo_desoneracao_icms.strip()
    if _str_preenchido(regra.codigo_beneficio_icms):
        snap['codigo_beneficio_icms'] = regra.codigo_beneficio_icms.strip()
    if regra.icms_st_aplicavel is not None:
        snap['icms_st_aplicavel'] = _fmt_bool(regra.icms_st_aplicavel)
    if _str_preenchido(regra.cst_icms_st_esperado):
        snap['cst_icms_st'] = regra.cst_icms_st_esperado.strip()
    if _dec_preenchido(regra.aliquota_icms_st):
        snap['aliquota_icms_st'] = _fmt_decimal(regra.aliquota_icms_st)
    if _dec_preenchido(regra.mva_st):
        snap['mva_st'] = _fmt_decimal(regra.mva_st)
    if _dec_preenchido(regra.reducao_bc_st):
        snap['reducao_bc_st'] = _fmt_decimal(regra.reducao_bc_st)
    if regra.fcp_aplicavel is not None:
        snap['fcp_aplicavel'] = _fmt_bool(regra.fcp_aplicavel)
    if _dec_preenchido(regra.aliquota_fcp):
        snap['aliquota_fcp'] = _fmt_decimal(regra.aliquota_fcp)
    if _dec_preenchido(regra.aliquota_fcp_st):
        snap['aliquota_fcp_st'] = _fmt_decimal(regra.aliquota_fcp_st)
    if _dec_preenchido(regra.reducao_bc_fcp):
        snap['reducao_bc_fcp'] = _fmt_decimal(regra.reducao_bc_fcp)
    if _dec_preenchido(regra.valor_fcp_unidade):
        snap['valor_fcp_unidade'] = _fmt_decimal(regra.valor_fcp_unidade, casas=4)
    if _str_preenchido(regra.cst_ipi_esperado):
        snap['cst_ipi'] = regra.cst_ipi_esperado.strip()
    if _str_preenchido(regra.tipo_calculo_ipi):
        snap['tipo_calculo_ipi'] = regra.tipo_calculo_ipi.strip()
    if _dec_preenchido(regra.aliquota_ipi):
        snap['aliquota_ipi'] = _fmt_decimal(regra.aliquota_ipi)
    if _dec_preenchido(regra.valor_ipi_unidade):
        snap['valor_ipi_unidade'] = _fmt_decimal(regra.valor_ipi_unidade, casas=4)
    if _str_preenchido(regra.enquadramento_ipi):
        snap['enquadramento_ipi'] = regra.enquadramento_ipi.strip()
    if _str_preenchido(regra.cst_pis_esperado):
        snap['cst_pis'] = regra.cst_pis_esperado.strip()
    if _str_preenchido(regra.tipo_calculo_pis):
        snap['tipo_calculo_pis'] = regra.tipo_calculo_pis.strip()
    if _dec_preenchido(regra.aliquota_pis):
        snap['aliquota_pis'] = _fmt_decimal(regra.aliquota_pis)
    if _dec_preenchido(regra.reducao_base_pis):
        snap['reducao_base_pis'] = _fmt_decimal(regra.reducao_base_pis)
    if _dec_preenchido(regra.valor_minimo_pis_unidade):
        snap['valor_minimo_pis_unidade'] = _fmt_decimal(regra.valor_minimo_pis_unidade, casas=4)
    if _dec_preenchido(regra.aliquota_pis_st):
        snap['aliquota_pis_st'] = _fmt_decimal(regra.aliquota_pis_st)
    if _str_preenchido(regra.cst_cofins_esperado):
        snap['cst_cofins'] = regra.cst_cofins_esperado.strip()
    if _str_preenchido(regra.tipo_calculo_cofins):
        snap['tipo_calculo_cofins'] = regra.tipo_calculo_cofins.strip()
    if _dec_preenchido(regra.aliquota_cofins):
        snap['aliquota_cofins'] = _fmt_decimal(regra.aliquota_cofins)
    if _dec_preenchido(regra.reducao_base_cofins):
        snap['reducao_base_cofins'] = _fmt_decimal(regra.reducao_base_cofins)
    if _dec_preenchido(regra.valor_minimo_cofins_unidade):
        snap['valor_minimo_cofins_unidade'] = _fmt_decimal(
            regra.valor_minimo_cofins_unidade,
            casas=4,
        )
    if _dec_preenchido(regra.aliquota_cofins_st):
        snap['aliquota_cofins_st'] = _fmt_decimal(regra.aliquota_cofins_st)
    return snap


def _comparar_cst_icms_e_csosn(
    regra: RegraFiscalEntrada,
    trib: dict[str, Any],
    add,
) -> None:
    """
    CST (regime normal) e CSOSN (Simples) são mutuamente exclusivos no XML.
    Não cruzar valores entre os campos na comparação.
    """
    cst_nf = str(trib.get('cst_icms') or '').strip()
    csosn_nf = str(trib.get('csosn') or '').strip()
    cst_bruto_nf = obter_cst_icms_bruto_nf(trib)

    if _str_preenchido(regra.cst_icms_esperado):
        add(
            _comparar_texto(
                campo='cst_icms',
                label='CST ICMS',
                esperado=regra.cst_icms_esperado,
                informado=normalizar_cst_icms_xml_para_entrada(cst_bruto_nf) if cst_bruto_nf else '',
                normalizar_cst=True,
            ),
        )

    if _str_preenchido(regra.csosn_esperado):
        if csosn_nf:
            add(
                _comparar_texto(
                    campo='csosn',
                    label='CSOSN',
                    esperado=regra.csosn_esperado,
                    informado=csosn_nf,
                    normalizar_cst=True,
                ),
            )
        elif not cst_nf:
            add(
                _comparar_texto(
                    campo='csosn',
                    label='CSOSN',
                    esperado=regra.csosn_esperado,
                    informado='',
                    normalizar_cst=True,
                ),
            )


def _comparar_divergencias_cst_regra(
    regra: RegraFiscalEntrada,
    trib: dict[str, Any],
) -> list[DivergenciaFiscalDict]:
    """Compara somente campos CST/CSOSN para ranqueamento de regras candidatas."""
    divergencias: list[DivergenciaFiscalDict] = []

    def add(div: DivergenciaFiscalDict | None) -> None:
        if div:
            divergencias.append(div)

    _comparar_cst_icms_e_csosn(regra, trib, add)
    add(
        _comparar_texto(
            campo='cst_icms_st',
            label='CST ICMS ST',
            esperado=regra.cst_icms_st_esperado,
            informado=str(trib.get('cst_icms_st_nf') or ''),
            normalizar_cst=True,
        ),
    )
    add(
        _comparar_texto(
            campo='cst_ipi',
            label='CST IPI',
            esperado=regra.cst_ipi_esperado,
            informado=normalizar_cst_ipi_xml_para_entrada(str(trib.get('cst_ipi') or '')),
            normalizar_cst=True,
        ),
    )
    add(
        _comparar_texto(
            campo='cst_pis',
            label='CST PIS',
            esperado=regra.cst_pis_esperado,
            informado=normalizar_cst_pis_cofins_xml_para_entrada(str(trib.get('cst_pis') or '')),
            normalizar_cst=True,
        ),
    )
    add(
        _comparar_texto(
            campo='cst_cofins',
            label='CST COFINS',
            esperado=regra.cst_cofins_esperado,
            informado=normalizar_cst_pis_cofins_xml_para_entrada(str(trib.get('cst_cofins') or '')),
            normalizar_cst=True,
        ),
    )
    return divergencias


def _contar_divergencias_cst(regra: RegraFiscalEntrada, trib: dict[str, Any]) -> int:
    """Conta divergências de CST entre a regra e os tributos do item."""
    return len(_comparar_divergencias_cst_regra(regra, trib))


def _comparar_impostos_regra(
    regra: RegraFiscalEntrada,
    trib: dict[str, Any],
) -> list[DivergenciaFiscalDict]:
    divergencias: list[DivergenciaFiscalDict] = []

    def add(div: DivergenciaFiscalDict | None) -> None:
        if div:
            divergencias.append(div)

    _comparar_cst_icms_e_csosn(regra, trib, add)
    add(
        _comparar_texto(
            campo='modalidade_bc_icms',
            label='Modalidade BC ICMS',
            esperado=regra.modalidade_bc_icms,
            informado=str(trib.get('modalidade_bc_icms') or ''),
        ),
    )
    if _dec_preenchido(regra.aliquota_icms):
        add(
            _comparar_decimal(
                campo='aliquota_icms',
                label='Alíquota ICMS',
                esperado=regra.aliquota_icms,
                informado=trib.get('aliquota_icms'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.reducao_bc_icms):
        add(
            _comparar_decimal(
                campo='reducao_bc_icms',
                label='Redução BC ICMS',
                esperado=regra.reducao_bc_icms,
                informado=trib.get('reducao_bc_icms'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    add(
        _comparar_texto(
            campo='motivo_desoneracao_icms',
            label='Motivo desoneração ICMS',
            esperado=regra.motivo_desoneracao_icms,
            informado=str(trib.get('motivo_desoneracao_icms') or ''),
        ),
    )
    add(
        _comparar_texto(
            campo='codigo_beneficio_icms',
            label='Código benefício ICMS',
            esperado=regra.codigo_beneficio_icms,
            informado=str(trib.get('codigo_beneficio_icms') or ''),
        ),
    )
    add(_comparar_icms_st(regra, trib))
    add(
        _comparar_texto(
            campo='cst_icms_st',
            label='CST ICMS ST',
            esperado=regra.cst_icms_st_esperado,
            informado=str(trib.get('cst_icms_st_nf') or ''),
            normalizar_cst=True,
        ),
    )
    if _dec_preenchido(regra.aliquota_icms_st):
        add(
            _comparar_decimal(
                campo='aliquota_icms_st',
                label='Alíquota ICMS ST',
                esperado=regra.aliquota_icms_st,
                informado=trib.get('aliquota_icms_st'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.mva_st):
        add(
            _comparar_decimal(
                campo='mva_st',
                label='MVA ST',
                esperado=regra.mva_st,
                informado=trib.get('mva_st'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.reducao_bc_st):
        add(
            _comparar_decimal(
                campo='reducao_bc_st',
                label='Redução BC ST',
                esperado=regra.reducao_bc_st,
                informado=trib.get('reducao_bc_st'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    add(_comparar_fcp_aplicavel(regra, trib))
    if _dec_preenchido(regra.aliquota_fcp):
        add(
            _comparar_decimal_fcp(
                campo='aliquota_fcp',
                label='Alíquota FCP',
                esperado=regra.aliquota_fcp,
                trib=trib,
                chave_nf='aliquota_fcp',
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.aliquota_fcp_st):
        add(
            _comparar_decimal_fcp(
                campo='aliquota_fcp_st',
                label='Alíquota FCP ST',
                esperado=regra.aliquota_fcp_st,
                trib=trib,
                chave_nf='aliquota_fcp_st',
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.reducao_bc_fcp):
        add(
            _comparar_decimal_fcp(
                campo='reducao_bc_fcp',
                label='Redução BC FCP',
                esperado=regra.reducao_bc_fcp,
                trib=trib,
                chave_nf='reducao_bc_fcp',
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.valor_fcp_unidade):
        add(
            _comparar_decimal_fcp(
                campo='valor_fcp_unidade',
                label='Valor FCP por unidade',
                esperado=regra.valor_fcp_unidade,
                trib=trib,
                chave_nf='valor_fcp_unidade',
                tolerancia=TOLERANCIA_VALOR,
                sufixo='',
            ),
        )
    add(
        _comparar_texto(
            campo='cst_ipi',
            label='CST IPI',
            esperado=regra.cst_ipi_esperado,
            informado=normalizar_cst_ipi_xml_para_entrada(str(trib.get('cst_ipi') or '')),
            normalizar_cst=True,
        ),
    )
    add(
        _comparar_texto(
            campo='tipo_calculo_ipi',
            label='Tipo cálculo IPI',
            esperado=regra.tipo_calculo_ipi,
            informado=str(trib.get('tipo_calculo_ipi') or ''),
        ),
    )
    if _dec_preenchido(regra.aliquota_ipi):
        add(
            _comparar_decimal(
                campo='aliquota_ipi',
                label='Alíquota IPI',
                esperado=regra.aliquota_ipi,
                informado=trib.get('aliquota_ipi'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.valor_ipi_unidade):
        add(
            _comparar_decimal(
                campo='valor_ipi_unidade',
                label='Valor IPI por unidade',
                esperado=regra.valor_ipi_unidade,
                informado=trib.get('valor_ipi_unidade'),
                tolerancia=TOLERANCIA_VALOR,
                sufixo='',
            ),
        )
    add(
        _comparar_texto(
            campo='enquadramento_ipi',
            label='Enquadramento IPI',
            esperado=regra.enquadramento_ipi,
            informado=str(trib.get('enquadramento_ipi') or ''),
        ),
    )
    add(
        _comparar_texto(
            campo='cst_pis',
            label='CST PIS',
            esperado=regra.cst_pis_esperado,
            informado=normalizar_cst_pis_cofins_xml_para_entrada(str(trib.get('cst_pis') or '')),
            normalizar_cst=True,
        ),
    )
    add(
        _comparar_texto(
            campo='tipo_calculo_pis',
            label='Tipo cálculo PIS',
            esperado=regra.tipo_calculo_pis,
            informado=str(trib.get('tipo_calculo_pis') or ''),
        ),
    )
    if _dec_preenchido(regra.aliquota_pis):
        add(
            _comparar_decimal(
                campo='aliquota_pis',
                label='Alíquota PIS',
                esperado=regra.aliquota_pis,
                informado=trib.get('aliquota_pis'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.reducao_base_pis):
        add(
            _comparar_decimal(
                campo='reducao_base_pis',
                label='Redução base PIS',
                esperado=regra.reducao_base_pis,
                informado=trib.get('reducao_base_pis'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.valor_minimo_pis_unidade):
        add(
            _comparar_decimal(
                campo='valor_minimo_pis_unidade',
                label='Valor mínimo PIS/unidade',
                esperado=regra.valor_minimo_pis_unidade,
                informado=trib.get('valor_minimo_pis_unidade'),
                tolerancia=TOLERANCIA_VALOR,
                sufixo='',
            ),
        )
    if _dec_preenchido(regra.aliquota_pis_st):
        add(
            _comparar_decimal(
                campo='aliquota_pis_st',
                label='Alíquota PIS ST',
                esperado=regra.aliquota_pis_st,
                informado=trib.get('aliquota_pis_st'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    add(
        _comparar_texto(
            campo='cst_cofins',
            label='CST COFINS',
            esperado=regra.cst_cofins_esperado,
            informado=normalizar_cst_pis_cofins_xml_para_entrada(str(trib.get('cst_cofins') or '')),
            normalizar_cst=True,
        ),
    )
    add(
        _comparar_texto(
            campo='tipo_calculo_cofins',
            label='Tipo cálculo COFINS',
            esperado=regra.tipo_calculo_cofins,
            informado=str(trib.get('tipo_calculo_cofins') or ''),
        ),
    )
    if _dec_preenchido(regra.aliquota_cofins):
        add(
            _comparar_decimal(
                campo='aliquota_cofins',
                label='Alíquota COFINS',
                esperado=regra.aliquota_cofins,
                informado=trib.get('aliquota_cofins'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.reducao_base_cofins):
        add(
            _comparar_decimal(
                campo='reducao_base_cofins',
                label='Redução base COFINS',
                esperado=regra.reducao_base_cofins,
                informado=trib.get('reducao_base_cofins'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    if _dec_preenchido(regra.valor_minimo_cofins_unidade):
        add(
            _comparar_decimal(
                campo='valor_minimo_cofins_unidade',
                label='Valor mínimo COFINS/unidade',
                esperado=regra.valor_minimo_cofins_unidade,
                informado=trib.get('valor_minimo_cofins_unidade'),
                tolerancia=TOLERANCIA_VALOR,
                sufixo='',
            ),
        )
    if _dec_preenchido(regra.aliquota_cofins_st):
        add(
            _comparar_decimal(
                campo='aliquota_cofins_st',
                label='Alíquota COFINS ST',
                esperado=regra.aliquota_cofins_st,
                informado=trib.get('aliquota_cofins_st'),
                tolerancia=TOLERANCIA_ALIQUOTA,
            ),
        )
    return divergencias


def _extrair_tributos_item_conf(item_conf: ItemNFeEntradaConferencia) -> dict[str, Any]:
    prod_json = item_conf.item_nfe_historico.prod_json or {}
    imposto_json = item_conf.item_nfe_historico.imposto_json or {}
    return extrair_tributos_item(prod_json, imposto_json)


def _dados_legados_cst(trib: dict[str, Any], prod_json: dict[str, Any]) -> dict[str, str]:
    csosn = str(trib.get('csosn') or trib.get('cst_icms_detalhe') or '').strip()
    cst_icms = obter_cst_icms_bruto_nf(trib)
    return {
        'cfop_nf': str(prod_json.get('CFOP') or '').strip(),
        'ncm_nf': str(prod_json.get('NCM') or '').strip(),
        'cst_icms_nf': cst_icms,
        'csosn_nf': csosn,
        'cst_pis_nf': str(trib.get('cst_pis') or '').strip(),
        'cst_cofins_nf': str(trib.get('cst_cofins') or '').strip(),
        'cst_ipi_nf': str(trib.get('cst_ipi') or '').strip(),
    }


def _resultado_base(
    trib: dict[str, Any],
    prod_json: dict[str, Any],
) -> ResultadoFiscalEntradaDict:
    dados = _dados_legados_cst(trib, prod_json)
    return {
        'status': 'SEM_REGRA',
        'regra_id': None,
        'regra_nome': '',
        'regra_codigo': '',
        'descricao_cenario': '',
        'regra_score_especificidade': 0,
        'regra_prioridade': 0,
        'regra_match_motivos': [],
        'severidade': '',
        'mensagens': [],
        'movimenta_estoque': None,
        'exige_certificado_fornecedor': None,
        'permite_credito_fiscal': None,
        'cfop_entrada_esperado': '',
        'impostos_nf': _montar_impostos_nf(trib),
        'impostos_esperados': {},
        'divergencias': [],
        **dados,
    }


def _regra_tem_criterio(regra: RegraFiscalEntrada) -> bool:
    return bool(
        _cfop_origem_regra(regra)
        or (regra.ncm or '').strip()
        or (regra.uf_origem or '').strip()
        or (regra.uf_destino or '').strip()
        or regra.tipo_operacao_fiscal
        or regra.produto_id
        or regra.fornecedor_id
    )


def _ncm_match(item_ncm: str, regra: RegraFiscalEntrada) -> bool:
    rule_ncm = normalize_ncm(regra.ncm)
    item_n = normalize_ncm(item_ncm)
    if not rule_ncm:
        return True
    if not item_n:
        return False
    if regra.ncm_prefixo:
        return item_n.startswith(rule_ncm)
    return item_n == rule_ncm or item_n.startswith(rule_ncm[:8])


def _ncm_casa_exato(item_ncm: str, regra: RegraFiscalEntrada) -> bool:
    rule_ncm = normalize_ncm(regra.ncm)
    if not rule_ncm or regra.ncm_prefixo:
        return False
    return normalize_ncm(item_ncm) == rule_ncm


def _ncm_casa_prefixo(item_ncm: str, regra: RegraFiscalEntrada) -> bool:
    rule_ncm = normalize_ncm(regra.ncm)
    if not rule_ncm or not regra.ncm_prefixo:
        return False
    item_n = normalize_ncm(item_ncm)
    return bool(item_n) and item_n.startswith(rule_ncm)


def _regra_casa(
    regra: RegraFiscalEntrada,
    *,
    cfop_nf: str,
    ncm_nf: str,
    contexto: ContextoFiscalEntrada,
    produto_id: int | None,
) -> bool:
    if not regra.ativo or not _regra_tem_criterio(regra):
        return False
    cfop_rule = _cfop_origem_regra(regra)
    if cfop_rule and _norm_cfop(cfop_nf) != cfop_rule:
        return False
    if not _ncm_match(ncm_nf, regra):
        return False
    if (regra.uf_origem or '').strip():
        if contexto.uf_origem != (regra.uf_origem or '').strip().upper()[:2]:
            return False
    if (regra.uf_destino or '').strip():
        if contexto.uf_destino != (regra.uf_destino or '').strip().upper()[:2]:
            return False
    if regra.tipo_operacao_fiscal and contexto.tipo_operacao_fiscal:
        if regra.tipo_operacao_fiscal != contexto.tipo_operacao_fiscal:
            return False
    if regra.produto_id and produto_id != regra.produto_id:
        return False
    if regra.fornecedor_id and contexto.fornecedor_id != regra.fornecedor_id:
        return False
    return True


def _status_final(severidade_regra: str, divergencias: list[DivergenciaFiscalDict]) -> str:
    if severidade_regra == RegraFiscalEntrada.Severidade.BLOQUEIO:
        return 'BLOQUEADO'
    if severidade_regra == RegraFiscalEntrada.Severidade.ALERTA or divergencias:
        return 'ALERTA'
    return 'OK'


def calcular_score_especificidade_regra_entrada(
    regra: RegraFiscalEntrada,
    *,
    cfop_nf: str,
    ncm_nf: str,
    contexto: ContextoFiscalEntrada,
    produto_id: int | None,
) -> EspecificidadeRegraEntrada | None:
    """
    Retorna score e motivos se a regra é candidata; None se algum critério preenchido não casa.
    Critério vazio na regra não pontua nem bloqueia.
    """
    if not _regra_casa(
        regra,
        cfop_nf=cfop_nf,
        ncm_nf=ncm_nf,
        contexto=contexto,
        produto_id=produto_id,
    ):
        return None

    score = SCORE_BASE_REGRA_GERAL
    motivos: list[str] = ['Critérios gerais']

    if regra.produto_id and produto_id == regra.produto_id:
        score += SCORE_PRODUTO
        motivos.append('Produto específico')
    if regra.fornecedor_id and contexto.fornecedor_id == regra.fornecedor_id:
        score += SCORE_FORNECEDOR
        motivos.append('Fornecedor específico')
    if _ncm_casa_exato(ncm_nf, regra):
        score += SCORE_NCM_EXATO
        motivos.append('NCM exato')
    elif _ncm_casa_prefixo(ncm_nf, regra):
        score += SCORE_NCM_PREFIXO
        motivos.append('NCM prefixo')
    if _cfop_origem_regra(regra):
        score += SCORE_CFOP_ORIGEM
        motivos.append('CFOP origem')
    if (regra.uf_origem or '').strip() and contexto.uf_origem == (regra.uf_origem or '').strip().upper()[:2]:
        score += SCORE_UF_ORIGEM
        motivos.append('UF origem')
    if (regra.uf_destino or '').strip() and contexto.uf_destino == (regra.uf_destino or '').strip().upper()[:2]:
        score += SCORE_UF_DESTINO
        motivos.append('UF destino')
    if (
        regra.tipo_operacao_fiscal
        and contexto.tipo_operacao_fiscal
        and regra.tipo_operacao_fiscal == contexto.tipo_operacao_fiscal
    ):
        score += SCORE_TIPO_OPERACAO
        motivos.append('Tipo operação')

    return EspecificidadeRegraEntrada(score=score, motivos=motivos)


def _comparar_candidatas_regra_entrada(
    atual: tuple[RegraFiscalEntrada, EspecificidadeRegraEntrada],
    candidata: tuple[RegraFiscalEntrada, EspecificidadeRegraEntrada],
) -> bool:
    """True se candidata deve vencer atual (score, prioridade, id)."""
    regra_c, esp_c = candidata
    regra_a, esp_a = atual
    if esp_c.score != esp_a.score:
        return esp_c.score > esp_a.score
    if regra_c.prioridade != regra_a.prioridade:
        return regra_c.prioridade > regra_a.prioridade
    return (regra_c.id or 0) < (regra_a.id or 0)


def _comparar_candidatas_por_cst(
    atual: tuple[RegraFiscalEntrada, EspecificidadeRegraEntrada],
    candidata: tuple[RegraFiscalEntrada, EspecificidadeRegraEntrada],
    trib: dict[str, Any],
) -> bool:
    """True se candidata deve vencer atual (menos divergências CST; depois prioridade/id)."""
    div_a = _contar_divergencias_cst(atual[0], trib)
    div_c = _contar_divergencias_cst(candidata[0], trib)
    if div_c != div_a:
        return div_c < div_a
    return _comparar_candidatas_regra_entrada(atual, candidata)


def encontrar_regra_fiscal_entrada(
    regras: list[RegraFiscalEntrada],
    *,
    cfop_nf: str,
    ncm_nf: str,
    contexto: ContextoFiscalEntrada,
    produto_id: int | None,
    trib: dict[str, Any] | None = None,
) -> tuple[RegraFiscalEntrada, EspecificidadeRegraEntrada] | None:
    candidatas: list[tuple[RegraFiscalEntrada, EspecificidadeRegraEntrada]] = []
    for regra in regras:
        esp = calcular_score_especificidade_regra_entrada(
            regra,
            cfop_nf=cfop_nf,
            ncm_nf=ncm_nf,
            contexto=contexto,
            produto_id=produto_id,
        )
        if esp is None:
            continue
        candidatas.append((regra, esp))
    if not candidatas:
        return None
    if len(candidatas) == 1:
        return candidatas[0]

    melhor_score = max(esp.score for _regra, esp in candidatas)
    top = [par for par in candidatas if par[1].score == melhor_score]
    if len(top) == 1:
        return top[0]

    melhor = top[0]
    if trib is not None:
        for par in top[1:]:
            if _comparar_candidatas_por_cst(melhor, par, trib):
                melhor = par
        return melhor

    for par in top[1:]:
        if _comparar_candidatas_regra_entrada(melhor, par):
            melhor = par
    return melhor


def avaliar_item_entrada_fiscal(
    item_conf: ItemNFeEntradaConferencia,
    contexto: ContextoFiscalEntrada,
    regras: list[RegraFiscalEntrada],
) -> ResultadoFiscalEntradaDict:
    trib = _extrair_tributos_item_conf(item_conf)
    prod_json = item_conf.item_nfe_historico.prod_json or {}
    base = _resultado_base(trib, prod_json)

    match = encontrar_regra_fiscal_entrada(
        regras,
        cfop_nf=base['cfop_nf'],
        ncm_nf=base['ncm_nf'],
        contexto=contexto,
        produto_id=item_conf.produto_id,
        trib=trib,
    )
    if not match:
        base['mensagens'] = [MSG_SEM_REGRA_FISCAL_ENTRADA]
        return base
    regra, especificidade = match

    mensagens: list[str] = []
    if regra.mensagem_padrao:
        mensagens.append(regra.mensagem_padrao.strip())

    divergencias = _comparar_impostos_regra(regra, trib)
    mensagens.extend(d['mensagem'] for d in divergencias)
    status = _status_final(regra.severidade, divergencias)

    descricao = (regra.descricao_cenario or '').strip() or (regra.nome or '').strip()
    cfop_entrada_esp = _norm_cfop(regra.cfop_entrada or '')

    resultado: ResultadoFiscalEntradaDict = {
        **base,
        'status': status,
        'regra_id': regra.id,
        'regra_nome': regra.nome,
        'regra_codigo': regra.codigo or '',
        'descricao_cenario': descricao,
        'regra_score_especificidade': especificidade.score,
        'regra_prioridade': regra.prioridade,
        'regra_match_motivos': list(especificidade.motivos),
        'severidade': regra.severidade,
        'mensagens': mensagens,
        'movimenta_estoque': regra.movimenta_estoque,
        'exige_certificado_fornecedor': regra.exige_certificado_fornecedor,
        'permite_credito_fiscal': regra.permite_credito_fiscal,
        'cfop_entrada_esperado': cfop_entrada_esp,
        'impostos_esperados': _montar_impostos_esperados(regra),
        'divergencias': divergencias,
    }
    if reforma_tributaria_preenchida(regra.reforma_tributaria):
        resultado['tem_reforma_configurada'] = True
        resultado['reforma_tributaria_esperada'] = reforma_tributaria_para_snapshot(
            regra.reforma_tributaria,
        )
    return resultado


def carregar_regras_fiscais_entrada_ativas(
    *,
    cenario_id: int | None = None,
) -> list[RegraFiscalEntrada]:
    """
    Carrega folhas ativas do cenário informado ou do cenário padrão.
    Mantém fallback para regras sem cenario (legado / transição).
    """
    from django.db.models import Q

    from apps.regras_fiscais.models import CenarioFiscalEntrada

    qs = RegraFiscalEntrada.objects.filter(ativo=True).select_related('cenario', 'escopo')

    if cenario_id is not None:
        qs = qs.filter(Q(cenario_id=cenario_id) | Q(cenario__isnull=True))
    else:
        cenario_padrao = (
            CenarioFiscalEntrada.objects.filter(ativo=True, padrao=True).order_by('id').first()
        )
        if cenario_padrao:
            qs = qs.filter(Q(cenario=cenario_padrao) | Q(cenario__isnull=True))
        # sem cenário padrão: todas as regras ativas (comportamento legado)

    return list(qs.order_by('-prioridade', 'nome', 'id'))


def montar_resumo_fiscal_conferencia(
    resultados: list[ResultadoFiscalEntradaDict],
    contexto: ContextoFiscalEntrada | None = None,
    *,
    linhas_ignoradas: int = 0,
) -> ResumoFiscalConferenciaDict:
    """Agrega status fiscal das linhas (read-only, sem persistir)."""
    resumo: ResumoFiscalConferenciaDict = {
        'total_itens': len(resultados),
        'ok': 0,
        'alerta': 0,
        'sem_regra': 0,
        'bloqueado': 0,
        'movimenta_estoque': 0,
        'exige_certificado_fornecedor': 0,
        'ignorados': linhas_ignoradas,
        'uf_origem': contexto.uf_origem if contexto else '',
        'uf_destino': contexto.uf_destino if contexto else '',
    }
    for row in resultados:
        status = (row.get('status') or 'SEM_REGRA').upper()
        if status == 'OK':
            resumo['ok'] += 1
        elif status == 'ALERTA':
            resumo['alerta'] += 1
        elif status == 'BLOQUEADO':
            resumo['bloqueado'] += 1
        else:
            resumo['sem_regra'] += 1
        if row.get('movimenta_estoque') is True:
            resumo['movimenta_estoque'] += 1
        if row.get('exige_certificado_fornecedor') is True:
            resumo['exige_certificado_fornecedor'] += 1
    return resumo


def descricao_criterios_regra_entrada(regra: RegraFiscalEntrada) -> str:
    """Texto legível dos critérios de match (diagnóstico)."""
    partes: list[str] = []
    cfop_orig = _cfop_origem_regra(regra)
    if cfop_orig:
        partes.append(f'CFOP orig. {cfop_orig}')
    if (regra.cfop_entrada or '').strip():
        partes.append(f'CFOP entr. {_norm_cfop(regra.cfop_entrada)}')
    if (regra.ncm or '').strip():
        suf = ' (prefixo)' if regra.ncm_prefixo else ''
        partes.append(f'NCM {regra.ncm.strip()}{suf}')
    if (regra.uf_origem or '').strip() or (regra.uf_destino or '').strip():
        partes.append(f'UF {regra.uf_origem or "*"}→{regra.uf_destino or "*"}')
    if regra.tipo_operacao_fiscal:
        partes.append(regra.get_tipo_operacao_fiscal_display())
    if regra.produto_id:
        partes.append(f'Produto #{regra.produto_id}')
    if regra.fornecedor_id:
        partes.append(f'Fornecedor #{regra.fornecedor_id}')
    return ' · '.join(partes) if partes else '—'


def _mensagem_bloqueio_fiscal_item(
    n_item: int,
    resultado: ResultadoFiscalEntradaDict,
) -> str:
    cfop = (resultado.get('cfop_nf') or '').strip() or '—'
    ncm = (resultado.get('ncm_nf') or '').strip() or '—'
    regra_nome = (resultado.get('regra_nome') or '').strip() or '—'
    msgs = [m.strip() for m in (resultado.get('mensagens') or []) if (m or '').strip()]
    msg_regra = '; '.join(msgs) if msgs else '—'
    return (
        f'Item {n_item} (CFOP {cfop}, NCM {ncm}): regra fiscal «{regra_nome}» — {msg_regra}'
    )


def validar_bloqueio_fiscal_preparar_conferencia(
    conferencia: NFeEntradaConferencia,
    itens: list[ItemNFeEntradaConferencia],
) -> list[str]:
    """
    Itens não ignorados com regra fiscal severidade BLOQUEIO impedem preparar estoque.
    SEM_REGRA e ALERTA não bloqueiam.
    """
    contexto = montar_contexto_fiscal_entrada(conferencia)
    regras = carregar_regras_fiscais_entrada_ativas()
    bloqueios: list[str] = []
    for item_conf in itens:
        if item_conf.status == ItemNFeEntradaConferencia.Status.IGNORADO:
            continue
        resultado = avaliar_item_entrada_fiscal(item_conf, contexto, regras)
        if resultado.get('status') != 'BLOQUEADO':
            continue
        n_item = item_conf.item_nfe_historico.n_item
        bloqueios.append(_mensagem_bloqueio_fiscal_item(n_item, resultado))
    return bloqueios
