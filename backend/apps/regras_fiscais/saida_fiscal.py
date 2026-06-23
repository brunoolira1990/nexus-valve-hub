"""Motor de busca de regra fiscal de saída (cenário) com fallback para RegraFiscal legado."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal, TypedDict

from django.conf import settings
from django.db.models import Q
from django.utils.dateparse import parse_date

from apps.comercial.models import ItemProposta
from apps.comercial.pricing import find_regra_fiscal, normalize_ncm
from apps.fiscal.nfe_cbenef_sp import normalizar_codigo_beneficio_icms
from apps.regras_fiscais.cenario_fiscal_saida import garantir_cenario_saida_padrao
from apps.regras_fiscais.models import CenarioFiscalSaidaEscopo, RegraFiscal, RegraFiscalSaida

OrigemRegraFiscalSaida = Literal['CENARIO_SAIDA', 'LEGADO', 'NAO_ENCONTRADA']


class BuscaRegraFiscalSaidaDict(TypedDict):
    origem: OrigemRegraFiscalSaida
    regra_id: int | None
    regra_legada_id: int | None
    cfop: str
    cfop_st: str
    cst_icms: str
    modalidade_bc_icms: str
    reducao_bc_icms: str
    codigo_beneficio_icms: str
    motivo_desoneracao_icms: str
    aliquota_icms: str
    cst_ipi: str
    aliquota_ipi: str
    cst_pis: str
    aliquota_pis: str
    cst_cofins: str
    aliquota_cofins: str
    movimenta_estoque: bool
    gera_financeiro: bool
    deduzir_icms_base_pis: bool
    deduzir_icms_base_cofins: bool
    tem_reforma_configurada: bool
    tem_recomendacoes_nfe: bool
    difal_aplicavel: bool
    aliquota_icms_interestadual: str
    aliquota_icms_interna_destino: str
    fcp_destino_aplicavel: bool
    aliquota_fcp_destino: str
    mensagens: list[str]


@dataclass(frozen=True)
class ContextoBuscaFiscalSaida:
    produto_id: int | None = None
    ncm: str = ''
    uf_origem: str = ''
    uf_destino: str = ''
    destinatario_contribuinte: str = ''
    consumidor_final: bool | None = None
    tipo_operacao: str = 'VENDA'
    cenario_id: int | None = None


@dataclass(frozen=True)
class EspecificidadeRegraSaida:
    score: int
    motivos: list[str]


SCORE_BASE_GERAL = 10
SCORE_PRODUTO = 1000
SCORE_NCM_EXATO = 500
SCORE_NCM_PREFIXO = 300
SCORE_UF_ORIGEM = 80
SCORE_UF_DESTINO = 80
SCORE_DESTINATARIO_ESPECIFICO = 60
SCORE_TIPO_OPERACAO = 100
SCORE_CONSUMIDOR_FINAL = 40


def use_cenario_fiscal_saida_for_propostas() -> bool:
    return bool(getattr(settings, 'USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS', False))


def resolve_usar_cenario_fiscal_para_proposta(
    proposta=None,
    *,
    incoming_usar_cenario: bool | None = None,
) -> bool:
    """
    Política: flag global OU opt-in da proposta.
    """
    if use_cenario_fiscal_saida_for_propostas():
        return True
    if proposta is not None and bool(getattr(proposta, 'usar_cenario_fiscal_saida', False)):
        return True
    if incoming_usar_cenario is not None:
        return bool(incoming_usar_cenario)
    return False


def deve_usar_cenario_fiscal_saida(
    proposta=None,
    *,
    incoming_usar_cenario: bool | None = None,
) -> bool:
    """Alias semântico: flag global OU opt-in da proposta."""
    return resolve_usar_cenario_fiscal_para_proposta(
        proposta,
        incoming_usar_cenario=incoming_usar_cenario,
    )


def resolve_cenario_fiscal_id_para_proposta(
    proposta=None,
    *,
    incoming_cenario_id: int | None = None,
) -> int | None:
    if proposta is not None and getattr(proposta, 'cenario_fiscal_saida_id', None):
        return proposta.cenario_fiscal_saida_id
    if incoming_cenario_id:
        return incoming_cenario_id
    return None


def mensagem_origem_fiscal_saida(origem: OrigemRegraFiscalSaida) -> str:
    if origem == 'CENARIO_SAIDA':
        return 'Regra aplicada pelo cenário fiscal de saída.'
    if origem == 'LEGADO':
        return 'Regra aplicada pela tabela fiscal legada.'
    return 'Nenhuma regra fiscal de saída encontrada para este item.'


def _norm_uf(value: str | None) -> str:
    return (value or '').strip().upper()[:2]


def _only_digits_cfop(value: str) -> str:
    return ''.join(c for c in (value or '') if c.isdigit())


def _fmt_aliquota(val: float | Decimal | None) -> str:
    if val is None:
        return '0'
    d = Decimal(str(val))
    return f'{d.quantize(Decimal("0.01")):.2f}'


def _fmt_reducao_bc(val: float | Decimal | None) -> str:
    if val is None:
        return ''
    d = Decimal(str(val))
    if d == 0:
        return ''
    return f'{d.quantize(Decimal("0.0001")):.4f}'


def _resolve_cenario(cenario_id: int | None) -> int:
    if cenario_id:
        return cenario_id
    return garantir_cenario_saida_padrao().id


def carregar_regras_fiscais_saida_ativas(*, cenario_id: int | None = None) -> list[RegraFiscalSaida]:
    cid = _resolve_cenario(cenario_id)
    return list(
        RegraFiscalSaida.objects.filter(cenario_id=cid, ativo=True, escopo__ativo=True)
        .select_related('escopo', 'escopo__produto', 'cenario')
        .order_by('-prioridade', 'id'),
    )


def _ncm_match_exato(item_ncm: str, escopo_ncm: str) -> bool:
    item_n = normalize_ncm(item_ncm)
    rule_n = normalize_ncm(escopo_ncm)
    return bool(item_n and rule_n and item_n == rule_n)


def _ncm_match_prefixo(item_ncm: str, escopo_ncm: str) -> bool:
    item_n = normalize_ncm(item_ncm)
    rule_n = normalize_ncm(escopo_ncm)
    return bool(item_n and rule_n and item_n.startswith(rule_n))


def _destinatario_casa(regra: RegraFiscalSaida, ctx: ContextoBuscaFiscalSaida) -> bool:
    regra_dest = (regra.destinatario_contribuinte or RegraFiscalSaida.DestinatarioContribuinte.QUALQUER).strip()
    if regra_dest == RegraFiscalSaida.DestinatarioContribuinte.QUALQUER:
        return True
    ctx_dest = (ctx.destinatario_contribuinte or '').strip().upper()
    if not ctx_dest:
        return True
    return regra_dest == ctx_dest


def _consumidor_final_casa(regra: RegraFiscalSaida, ctx: ContextoBuscaFiscalSaida) -> bool:
    if regra.consumidor_final is None:
        return True
    if ctx.consumidor_final is None:
        return True
    return regra.consumidor_final is ctx.consumidor_final


def _tipo_operacao_casa(regra: RegraFiscalSaida, ctx: ContextoBuscaFiscalSaida) -> bool:
    regra_tipo = (regra.tipo_operacao or '').strip()
    if not regra_tipo:
        return True
    ctx_tipo = (ctx.tipo_operacao or 'VENDA').strip()
    return regra_tipo == ctx_tipo


def _uf_casa(regra: RegraFiscalSaida, ctx: ContextoBuscaFiscalSaida) -> bool:
    if (regra.uf_origem or '').strip():
        if _norm_uf(regra.uf_origem) != _norm_uf(ctx.uf_origem):
            return False
    if (regra.uf_destino or '').strip():
        if _norm_uf(regra.uf_destino) != _norm_uf(ctx.uf_destino):
            return False
    return True


def calcular_score_especificidade_regra_saida(
    regra: RegraFiscalSaida,
    ctx: ContextoBuscaFiscalSaida,
) -> EspecificidadeRegraSaida | None:
    escopo = regra.escopo
    if escopo is None or not escopo.ativo:
        return None
    if not _uf_casa(regra, ctx):
        return None
    if not _destinatario_casa(regra, ctx):
        return None
    if not _consumidor_final_casa(regra, ctx):
        return None
    if not _tipo_operacao_casa(regra, ctx):
        return None

    motivos: list[str] = []
    score = 0

    if escopo.tipo_escopo == CenarioFiscalSaidaEscopo.TipoEscopo.PRODUTO:
        if not ctx.produto_id or escopo.produto_id != ctx.produto_id:
            return None
        score = SCORE_PRODUTO
        motivos.append('Produto específico')
    elif escopo.tipo_escopo == CenarioFiscalSaidaEscopo.TipoEscopo.NCM:
        if not _ncm_match_exato(ctx.ncm, escopo.ncm):
            return None
        score = SCORE_NCM_EXATO
        motivos.append('NCM exato')
    elif escopo.tipo_escopo == CenarioFiscalSaidaEscopo.TipoEscopo.NCM_PREFIXO:
        if not _ncm_match_prefixo(ctx.ncm, escopo.ncm):
            return None
        score = SCORE_NCM_PREFIXO
        motivos.append('NCM prefixo')
    elif escopo.tipo_escopo == CenarioFiscalSaidaEscopo.TipoEscopo.GERAL:
        score = SCORE_BASE_GERAL
        motivos.append('Regra geral')
    else:
        return None

    if (regra.uf_origem or '').strip() and _norm_uf(regra.uf_origem) == _norm_uf(ctx.uf_origem):
        score += SCORE_UF_ORIGEM
        motivos.append('UF origem')
    if (regra.uf_destino or '').strip() and _norm_uf(regra.uf_destino) == _norm_uf(ctx.uf_destino):
        score += SCORE_UF_DESTINO
        motivos.append('UF destino')
    if (regra.destinatario_contribuinte or '').strip() not in (
        '',
        RegraFiscalSaida.DestinatarioContribuinte.QUALQUER,
    ):
        score += SCORE_DESTINATARIO_ESPECIFICO
        motivos.append('Destinatário')
    if (regra.tipo_operacao or '').strip() and regra.tipo_operacao == (ctx.tipo_operacao or 'VENDA'):
        score += SCORE_TIPO_OPERACAO
        motivos.append('Tipo operação')
    if regra.consumidor_final is not None and ctx.consumidor_final is not None:
        score += SCORE_CONSUMIDOR_FINAL
        motivos.append('Consumidor final')

    return EspecificidadeRegraSaida(score=score, motivos=motivos)


def _comparar_candidatas(
    atual: tuple[RegraFiscalSaida, EspecificidadeRegraSaida],
    candidata: tuple[RegraFiscalSaida, EspecificidadeRegraSaida],
) -> bool:
    regra_c, esp_c = candidata
    regra_a, esp_a = atual
    if esp_c.score != esp_a.score:
        return esp_c.score > esp_a.score
    if regra_c.prioridade != regra_a.prioridade:
        return regra_c.prioridade > regra_a.prioridade
    return (regra_c.id or 0) < (regra_a.id or 0)


def encontrar_regra_fiscal_saida(
    regras: list[RegraFiscalSaida],
    ctx: ContextoBuscaFiscalSaida,
) -> RegraFiscalSaida | None:
    melhor: tuple[RegraFiscalSaida, EspecificidadeRegraSaida] | None = None
    for regra in regras:
        esp = calcular_score_especificidade_regra_saida(regra, ctx)
        if esp is None:
            continue
        candidata = (regra, esp)
        if melhor is None or _comparar_candidatas(melhor, candidata):
            melhor = candidata
    return melhor[0] if melhor else None


def _resultado_de_regra_saida(regra: RegraFiscalSaida) -> BuscaRegraFiscalSaidaDict:
    from apps.regras_fiscais.recomendacoes_nfe_config import recomendacoes_nfe_preenchidas
    from apps.regras_fiscais.reforma_tributaria_config import reforma_tributaria_preenchida

    return {
        'origem': 'CENARIO_SAIDA',
        'regra_id': regra.id,
        'regra_legada_id': None,
        'cfop': _only_digits_cfop(regra.cfop_venda),
        'cfop_st': _only_digits_cfop(regra.cfop_venda_st),
        'cst_icms': (regra.cst_icms or regra.csosn or '').strip(),
        'modalidade_bc_icms': (regra.modalidade_bc_icms or '').strip(),
        'reducao_bc_icms': _fmt_reducao_bc(regra.reducao_bc_icms),
        'codigo_beneficio_icms': normalizar_codigo_beneficio_icms(regra.codigo_beneficio_icms),
        'motivo_desoneracao_icms': (regra.motivo_desoneracao_icms or '').strip(),
        'aliquota_icms': _fmt_aliquota(regra.aliquota_icms),
        'cst_ipi': (regra.cst_ipi or '').strip(),
        'aliquota_ipi': _fmt_aliquota(regra.aliquota_ipi),
        'cst_pis': (regra.cst_pis or '').strip(),
        'aliquota_pis': _fmt_aliquota(regra.aliquota_pis),
        'cst_cofins': (regra.cst_cofins or '').strip(),
        'aliquota_cofins': _fmt_aliquota(regra.aliquota_cofins),
        'movimenta_estoque': bool(regra.movimenta_estoque),
        'gera_financeiro': bool(regra.gera_financeiro),
        'deduzir_icms_base_pis': bool(regra.deduzir_icms_base_pis),
        'deduzir_icms_base_cofins': bool(regra.deduzir_icms_base_cofins),
        'tem_reforma_configurada': reforma_tributaria_preenchida(regra.reforma_tributaria),
        'tem_recomendacoes_nfe': recomendacoes_nfe_preenchidas(regra.recomendacoes_nfe),
        'difal_aplicavel': bool(regra.difal_aplicavel),
        'aliquota_icms_interestadual': _fmt_aliquota(regra.aliquota_icms_interestadual),
        'aliquota_icms_interna_destino': _fmt_aliquota(regra.aliquota_icms_interna_destino),
        'fcp_destino_aplicavel': bool(regra.fcp_aplicavel),
        'aliquota_fcp_destino': _fmt_aliquota(regra.aliquota_fcp),
        'mensagens': [],
    }


def _resultado_de_regra_legada(regra: RegraFiscal) -> BuscaRegraFiscalSaidaDict:
    return {
        'origem': 'LEGADO',
        'regra_id': None,
        'regra_legada_id': regra.id,
        'cfop': _only_digits_cfop(regra.cfop),
        'cfop_st': '',
        'cst_icms': (regra.cst_icms or '').strip(),
        'modalidade_bc_icms': '',
        'reducao_bc_icms': '',
        'codigo_beneficio_icms': '',
        'motivo_desoneracao_icms': '',
        'aliquota_icms': _fmt_aliquota(regra.aliquota_icms),
        'cst_ipi': (regra.cst_ipi or '').strip(),
        'aliquota_ipi': _fmt_aliquota(regra.aliquota_ipi),
        'cst_pis': (regra.cst_pis or '').strip(),
        'aliquota_pis': _fmt_aliquota(regra.aliquota_pis),
        'cst_cofins': (regra.cst_cofins or '').strip(),
        'aliquota_cofins': _fmt_aliquota(regra.aliquota_cofins),
        'movimenta_estoque': True,
        'gera_financeiro': True,
        'deduzir_icms_base_pis': False,
        'deduzir_icms_base_cofins': False,
        'tem_reforma_configurada': False,
        'tem_recomendacoes_nfe': False,
        'difal_aplicavel': False,
        'aliquota_icms_interestadual': '0',
        'aliquota_icms_interna_destino': '0',
        'fcp_destino_aplicavel': False,
        'aliquota_fcp_destino': '0',
        'mensagens': [],
    }


def _resultado_nao_encontrada(*, mensagens: list[str] | None = None) -> BuscaRegraFiscalSaidaDict:
    return {
        'origem': 'NAO_ENCONTRADA',
        'regra_id': None,
        'regra_legada_id': None,
        'cfop': '',
        'cfop_st': '',
        'cst_icms': '',
        'modalidade_bc_icms': '',
        'reducao_bc_icms': '',
        'codigo_beneficio_icms': '',
        'motivo_desoneracao_icms': '',
        'aliquota_icms': '0',
        'cst_ipi': '',
        'aliquota_ipi': '0',
        'cst_pis': '',
        'aliquota_pis': '0',
        'cst_cofins': '',
        'aliquota_cofins': '0',
        'movimenta_estoque': True,
        'gera_financeiro': True,
        'deduzir_icms_base_pis': False,
        'deduzir_icms_base_cofins': False,
        'tem_reforma_configurada': False,
        'tem_recomendacoes_nfe': False,
        'difal_aplicavel': False,
        'aliquota_icms_interestadual': '0',
        'aliquota_icms_interna_destino': '0',
        'fcp_destino_aplicavel': False,
        'aliquota_fcp_destino': '0',
        'mensagens': mensagens or [],
    }


def _montar_contexto_busca(
    *,
    produto_id: int | None = None,
    ncm: str | None = None,
    uf_origem: str,
    uf_destino: str,
    destinatario_contribuinte: str | None = None,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
    cenario_id: int | None = None,
    produto=None,
) -> tuple[ContextoBuscaFiscalSaida | None, list[str]]:
    """Retorna contexto ou None com mensagens de erro de validação."""
    if produto is not None:
        produto_id = getattr(produto, 'pk', None) or getattr(produto, 'id', None)
        if not ncm:
            ncm = getattr(produto, 'get_ncm_efetivo_codigo', lambda: '')() or getattr(produto, 'ncm', '') or ''

    ncm_norm = normalize_ncm(ncm or '')
    ufo = _norm_uf(uf_origem)
    ufd = _norm_uf(uf_destino)

    if len(ufo) != 2 or len(ufd) != 2:
        return None, ['Informe UF origem e destino válidas (2 caracteres).']

    ctx = ContextoBuscaFiscalSaida(
        produto_id=produto_id,
        ncm=ncm_norm,
        uf_origem=ufo,
        uf_destino=ufd,
        destinatario_contribuinte=(destinatario_contribuinte or '').strip().upper(),
        consumidor_final=consumidor_final,
        tipo_operacao=(tipo_operacao or 'VENDA').strip().upper(),
        cenario_id=cenario_id,
    )
    return ctx, []


def montar_filtros_busca_regra_nfe(
    *,
    ncm: str,
    uf_origem: str,
    uf_destino: str,
    cenario_id: int | None = None,
    tipo_operacao: str = 'VENDA',
    destinatario_contribuinte: str | None = None,
) -> dict[str, Any]:
    """Filtros normalizados usados na busca de regra fiscal da NF-e rascunho."""
    cid = _resolve_cenario(cenario_id)
    return {
        'fonte_consultada': 'CENARIO_SAIDA_PADRAO',
        'cenario_fiscal_saida_id': cid,
        'ncm': normalize_ncm(ncm),
        'uf_origem': _norm_uf(uf_origem),
        'uf_destino': _norm_uf(uf_destino),
        'tipo_operacao': (tipo_operacao or 'VENDA').strip().upper(),
        'destinatario_contribuinte': (destinatario_contribuinte or 'QUALQUER').strip().upper() or 'QUALQUER',
        'fallback_legado': False,
    }


def diagnosticar_busca_regra_nfe_cenario(
    *,
    ncm: str,
    uf_origem: str,
    uf_destino: str,
    cenario_id: int | None = None,
    produto_id: int | None = None,
) -> dict[str, Any]:
    """
    Conta regras candidatas no cenário para auditoria quando a busca principal falha.
    Não altera banco.
    """
    filtros = montar_filtros_busca_regra_nfe(
        ncm=ncm,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        cenario_id=cenario_id,
    )
    ctx, erros = _montar_contexto_busca(
        produto_id=produto_id,
        ncm=filtros['ncm'],
        uf_origem=filtros['uf_origem'],
        uf_destino=filtros['uf_destino'],
        cenario_id=filtros['cenario_fiscal_saida_id'],
        tipo_operacao=filtros['tipo_operacao'],
    )
    if ctx is None:
        return {**filtros, 'regras_candidatas': 0, 'erros_contexto': erros}

    regras = carregar_regras_fiscais_saida_ativas(cenario_id=filtros['cenario_fiscal_saida_id'])
    ncm_norm = ctx.ncm
    por_ncm = 0
    por_uf = 0
    aplicavel = 0
    descartadas: list[str] = []

    for regra in regras:
        escopo = regra.escopo
        if escopo is None:
            continue
        escopo_ncm = normalize_ncm(escopo.ncm or '')
        if escopo.tipo_escopo == CenarioFiscalSaidaEscopo.TipoEscopo.NCM and escopo_ncm == ncm_norm:
            por_ncm += 1
        if (
            _norm_uf(regra.uf_origem) == ctx.uf_origem
            and _norm_uf(regra.uf_destino) == ctx.uf_destino
        ):
            por_uf += 1
        if calcular_score_especificidade_regra_saida(regra, ctx) is not None:
            aplicavel += 1
        elif escopo_ncm == ncm_norm:
            motivos = []
            if not _uf_casa(regra, ctx):
                motivos.append(
                    f'UF {regra.uf_origem or "—"}→{regra.uf_destino or "—"} '
                    f'incompatível com {ctx.uf_origem}→{ctx.uf_destino}',
                )
            if not _tipo_operacao_casa(regra, ctx):
                motivos.append(f'tipo operação {regra.tipo_operacao or "—"}')
            if motivos:
                descartadas.append(f'Regra #{regra.pk}: ' + '; '.join(motivos))

    return {
        **filtros,
        'regras_candidatas': aplicavel,
        'regras_mesmo_ncm': por_ncm,
        'regras_mesma_rota_uf': por_uf,
        'regras_descartadas': descartadas[:5],
    }


def buscar_regra_fiscal_nfe_saida_rascunho(
    *,
    produto_id: int | None = None,
    ncm: str | None = None,
    uf_origem: str,
    uf_destino: str,
    cenario_id: int | None = None,
    produto=None,
    destinatario_contribuinte: str | None = None,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
) -> tuple[BuscaRegraFiscalSaidaDict, RegraFiscalSaida | None, dict[str, Any]]:
    """
    Busca regra fiscal para NF-e rascunho (Atualizar fiscal).

    Sempre usa o cenário padrão de saída — mesma fonte da tela Regras Fiscais.
    Não usa fallback legado nem o flag USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS.
    """
    cid = _resolve_cenario(cenario_id)
    filtros = montar_filtros_busca_regra_nfe(
        ncm=ncm or '',
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        cenario_id=cid,
        tipo_operacao=tipo_operacao,
        destinatario_contribuinte=destinatario_contribuinte,
    )
    regra = buscar_regra_fiscal_saida_apenas_cenario(
        produto_id=produto_id,
        ncm=filtros['ncm'],
        uf_origem=filtros['uf_origem'],
        uf_destino=filtros['uf_destino'],
        destinatario_contribuinte=destinatario_contribuinte,
        consumidor_final=consumidor_final,
        tipo_operacao=filtros['tipo_operacao'],
        cenario_id=cid,
        produto=produto,
    )
    if regra is not None:
        return _resultado_de_regra_saida(regra), regra, filtros

    diag = diagnosticar_busca_regra_nfe_cenario(
        ncm=filtros['ncm'],
        uf_origem=filtros['uf_origem'],
        uf_destino=filtros['uf_destino'],
        cenario_id=cid,
        produto_id=produto_id,
    )
    mensagens = [
        (
            f'Não foi encontrada regra fiscal de saída para NCM {filtros["ncm"]}, '
            f'origem {filtros["uf_origem"]} e destino {filtros["uf_destino"]}.'
        ),
    ]
    if diag.get('regras_mesma_rota_uf', 0) == 0 and diag.get('regras_mesmo_ncm', 0) > 0:
        mensagens.append(
            f'Existem regras para o NCM {filtros["ncm"]}, mas nenhuma para a rota '
            f'{filtros["uf_origem"]}→{filtros["uf_destino"]}.',
        )
    return _resultado_nao_encontrada(mensagens=mensagens), None, {**filtros, **diag}


def buscar_regra_fiscal_saida_apenas_cenario(
    *,
    produto_id: int | None = None,
    ncm: str | None = None,
    uf_origem: str,
    uf_destino: str,
    destinatario_contribuinte: str | None = None,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
    cenario_id: int | None = None,
    produto=None,
) -> RegraFiscalSaida | None:
    """Busca somente no cenário fiscal de saída, sem fallback legado."""
    ctx, _ = _montar_contexto_busca(
        produto_id=produto_id,
        ncm=ncm,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        destinatario_contribuinte=destinatario_contribuinte,
        consumidor_final=consumidor_final,
        tipo_operacao=tipo_operacao,
        cenario_id=cenario_id,
        produto=produto,
    )
    if ctx is None:
        return None
    regras = carregar_regras_fiscais_saida_ativas(cenario_id=cenario_id)
    return encontrar_regra_fiscal_saida(regras, ctx)


def buscar_regra_fiscal_legado_apenas(
    ncm: str,
    uf_origem: str,
    uf_destino: str,
    operacao: str = 'Saída',
) -> RegraFiscal | None:
    """Busca somente na tabela RegraFiscal legada."""
    ncm_norm = normalize_ncm(ncm)
    uo = _norm_uf(uf_origem)
    ud = _norm_uf(uf_destino)
    if not ncm_norm or len(uo) != 2 or len(ud) != 2:
        return None
    return find_regra_fiscal(ncm_norm, uo, ud, operacao)


def buscar_regra_fiscal_saida(
    *,
    produto_id: int | None = None,
    ncm: str | None = None,
    uf_origem: str,
    uf_destino: str,
    destinatario_contribuinte: str | None = None,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
    cenario_id: int | None = None,
    produto=None,
) -> BuscaRegraFiscalSaidaDict:
    """
    Tenta RegraFiscalSaida no cenário; se não achar, fallback RegraFiscal legado.
    """
    ctx, erros = _montar_contexto_busca(
        produto_id=produto_id,
        ncm=ncm,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        destinatario_contribuinte=destinatario_contribuinte,
        consumidor_final=consumidor_final,
        tipo_operacao=tipo_operacao,
        cenario_id=cenario_id,
        produto=produto,
    )
    if ctx is None:
        return _resultado_nao_encontrada(mensagens=erros)

    regra_saida = buscar_regra_fiscal_saida_apenas_cenario(
        produto_id=ctx.produto_id,
        ncm=ctx.ncm,
        uf_origem=ctx.uf_origem,
        uf_destino=ctx.uf_destino,
        destinatario_contribuinte=ctx.destinatario_contribuinte,
        consumidor_final=ctx.consumidor_final,
        tipo_operacao=ctx.tipo_operacao,
        cenario_id=ctx.cenario_id,
    )
    if regra_saida is not None:
        return _resultado_de_regra_saida(regra_saida)

    if ctx.ncm:
        legado = find_regra_fiscal(ctx.ncm, ctx.uf_origem, ctx.uf_destino, 'Saída')
        if legado is not None:
            return _resultado_de_regra_legada(legado)

    return _resultado_nao_encontrada(
        mensagens=[
            'Não encontramos regra fiscal de saída no cenário nem na tabela legada para este NCM/UF.',
        ],
    )


def find_regra_fiscal_saida_com_fallback(
    ncm: str,
    uf_origem: str,
    uf_destino: str,
    operacao: str = 'Saída',
    *,
    produto_id: int | None = None,
    destinatario_contribuinte: str | None = None,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
    cenario_id: int | None = None,
    usar_cenario: bool | None = None,
) -> BuscaRegraFiscalSaidaDict:
    """
    Ponto único para propostas: cenário novo (se habilitado) + fallback legado.
    Se usar_cenario=False, comportamento idêntico ao legado puro.
    """
    uo = _norm_uf(uf_origem)
    ud = _norm_uf(uf_destino)
    ncm_norm = normalize_ncm(ncm)

    if usar_cenario is None:
        usar_cenario = use_cenario_fiscal_saida_for_propostas()

    if not usar_cenario:
        if not ncm_norm or len(uo) != 2 or len(ud) != 2:
            return _resultado_nao_encontrada()
        legado = find_regra_fiscal(ncm_norm, uo, ud, operacao)
        if legado:
            return _resultado_de_regra_legada(legado)
        return _resultado_nao_encontrada(
            mensagens=['Não encontramos regra fiscal legada para este NCM com UF origem/destino e operação saída.'],
        )

    return buscar_regra_fiscal_saida(
        produto_id=produto_id,
        ncm=ncm_norm,
        uf_origem=uo,
        uf_destino=ud,
        destinatario_contribuinte=destinatario_contribuinte,
        consumidor_final=consumidor_final,
        tipo_operacao=tipo_operacao,
        cenario_id=cenario_id,
    )


StatusComparativoFiscal = Literal[
    'IGUAL',
    'DIVERGENTE',
    'CENARIO_NAO_ENCONTRADO',
    'LEGADO_NAO_ENCONTRADO',
    'AMBOS_NAO_ENCONTRADOS',
]


class LadoComparativoFiscalDict(TypedDict):
    encontrado: bool
    regra_id: int | None
    cfop: str
    cfop_st: str
    cst_icms: str
    aliquota_icms: str
    cst_ipi: str
    aliquota_ipi: str
    cst_pis: str
    aliquota_pis: str
    cst_cofins: str
    aliquota_cofins: str
    movimenta_estoque: bool | None
    gera_financeiro: bool | None
    aliquota_fcp: str
    aliquota_icms_st: str
    deduzir_icms_base_pis: bool
    deduzir_icms_base_cofins: bool


class DivergenciaComparativoDict(TypedDict):
    campo: str
    label: str
    legado: str
    cenario: str


class ComparativoFiscalSaidaDict(TypedDict):
    status: StatusComparativoFiscal
    cenario: LadoComparativoFiscalDict
    legado: LadoComparativoFiscalDict
    divergencias: list[DivergenciaComparativoDict]
    mensagens: list[str]
    origem_oficial_proposta: str
    origem_se_flag_cenario_ativa: OrigemRegraFiscalSaida


TOLERANCIA_ALIQUOTA = Decimal('0.01')

_CAMPOS_COMPARACAO_MINIMOS: list[tuple[str, str, str]] = [
    ('cfop', 'CFOP', 'texto'),
    ('cst_icms', 'CST ICMS', 'texto'),
    ('aliquota_icms', 'Alíquota ICMS', 'decimal'),
    ('cst_ipi', 'CST IPI', 'texto'),
    ('aliquota_ipi', 'Alíquota IPI', 'decimal'),
    ('cst_pis', 'CST PIS', 'texto'),
    ('aliquota_pis', 'Alíquota PIS', 'decimal'),
    ('cst_cofins', 'CST COFINS', 'texto'),
    ('aliquota_cofins', 'Alíquota COFINS', 'decimal'),
]

_CAMPOS_COMPARACAO_OPCIONAIS: list[tuple[str, str, str]] = [
    ('cfop_st', 'CFOP ST', 'texto'),
    ('aliquota_fcp', 'Alíquota FCP', 'decimal'),
    ('aliquota_icms_st', 'Alíquota ICMS ST', 'decimal'),
    ('movimenta_estoque', 'Movimenta estoque', 'bool'),
    ('gera_financeiro', 'Gera financeiro', 'bool'),
    ('deduzir_icms_base_pis', 'Deduzir ICMS da base PIS', 'bool'),
    ('deduzir_icms_base_cofins', 'Deduzir ICMS da base COFINS', 'bool'),
]


def _lado_vazio() -> LadoComparativoFiscalDict:
    return {
        'encontrado': False,
        'regra_id': None,
        'cfop': '',
        'cfop_st': '',
        'cst_icms': '',
        'aliquota_icms': '',
        'cst_ipi': '',
        'aliquota_ipi': '',
        'cst_pis': '',
        'aliquota_pis': '',
        'cst_cofins': '',
        'aliquota_cofins': '',
        'movimenta_estoque': None,
        'gera_financeiro': None,
        'aliquota_fcp': '',
        'aliquota_icms_st': '',
        'deduzir_icms_base_pis': False,
        'deduzir_icms_base_cofins': False,
    }


def _snapshot_cenario(regra: RegraFiscalSaida) -> LadoComparativoFiscalDict:
    fcp = ''
    if regra.fcp_aplicavel:
        fcp = _fmt_aliquota(regra.aliquota_fcp)
    icms_st = ''
    if regra.icms_st_aplicavel:
        icms_st = _fmt_aliquota(regra.aliquota_icms_st)
    return {
        'encontrado': True,
        'regra_id': regra.id,
        'cfop': _only_digits_cfop(regra.cfop_venda),
        'cfop_st': _only_digits_cfop(regra.cfop_venda_st),
        'cst_icms': (regra.cst_icms or regra.csosn or '').strip(),
        'aliquota_icms': _fmt_aliquota(regra.aliquota_icms),
        'cst_ipi': (regra.cst_ipi or '').strip(),
        'aliquota_ipi': _fmt_aliquota(regra.aliquota_ipi),
        'cst_pis': (regra.cst_pis or '').strip(),
        'aliquota_pis': _fmt_aliquota(regra.aliquota_pis),
        'cst_cofins': (regra.cst_cofins or '').strip(),
        'aliquota_cofins': _fmt_aliquota(regra.aliquota_cofins),
        'movimenta_estoque': bool(regra.movimenta_estoque),
        'gera_financeiro': bool(regra.gera_financeiro),
        'aliquota_fcp': fcp,
        'aliquota_icms_st': icms_st,
        'deduzir_icms_base_pis': bool(regra.deduzir_icms_base_pis),
        'deduzir_icms_base_cofins': bool(regra.deduzir_icms_base_cofins),
    }


def _snapshot_legado(regra: RegraFiscal) -> LadoComparativoFiscalDict:
    return {
        'encontrado': True,
        'regra_id': regra.id,
        'cfop': _only_digits_cfop(regra.cfop),
        'cfop_st': '',
        'cst_icms': (regra.cst_icms or '').strip(),
        'aliquota_icms': _fmt_aliquota(regra.aliquota_icms),
        'cst_ipi': (regra.cst_ipi or '').strip(),
        'aliquota_ipi': _fmt_aliquota(regra.aliquota_ipi),
        'cst_pis': (regra.cst_pis or '').strip(),
        'aliquota_pis': _fmt_aliquota(regra.aliquota_pis),
        'cst_cofins': (regra.cst_cofins or '').strip(),
        'aliquota_cofins': _fmt_aliquota(regra.aliquota_cofins),
        'movimenta_estoque': None,
        'gera_financeiro': None,
        'aliquota_fcp': '',
        'aliquota_icms_st': '',
        'deduzir_icms_base_pis': False,
        'deduzir_icms_base_cofins': False,
    }


def _valor_vazio_para_cmp(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, bool):
        return False
    s = str(val).strip()
    return s in ('', '0', '0.0', '0.00', '0.0000')


def _norm_texto_cmp(val: Any) -> str:
    return str(val or '').strip().upper()


def _norm_decimal_cmp(val: Any) -> Decimal:
    if _valor_vazio_para_cmp(val):
        return Decimal('0.00')
    return Decimal(str(val)).quantize(Decimal('0.01'))


def _valores_iguais(tipo: str, a: Any, b: Any) -> bool:
    if tipo == 'decimal':
        return abs(_norm_decimal_cmp(a) - _norm_decimal_cmp(b)) <= TOLERANCIA_ALIQUOTA
    if tipo == 'bool':
        return bool(a) is bool(b)
    return _norm_texto_cmp(a) == _norm_texto_cmp(b)


def _fmt_valor_exibicao(tipo: str, val: Any) -> str:
    if tipo == 'decimal':
        return f'{_norm_decimal_cmp(val):.2f}'
    if tipo == 'bool':
        return 'Sim' if val else 'Não'
    return str(val or '').strip()


def _listar_divergencias(
    cenario: LadoComparativoFiscalDict,
    legado: LadoComparativoFiscalDict,
) -> list[DivergenciaComparativoDict]:
    divergencias: list[DivergenciaComparativoDict] = []

    for campo, label, tipo in _CAMPOS_COMPARACAO_MINIMOS:
        va = cenario.get(campo)  # type: ignore[literal-required]
        vb = legado.get(campo)  # type: ignore[literal-required]
        if not _valores_iguais(tipo, va, vb):
            divergencias.append(
                {
                    'campo': campo,
                    'label': label,
                    'legado': _fmt_valor_exibicao(tipo, vb),
                    'cenario': _fmt_valor_exibicao(tipo, va),
                },
            )

    for campo, label, tipo in _CAMPOS_COMPARACAO_OPCIONAIS:
        va = cenario.get(campo)  # type: ignore[literal-required]
        vb = legado.get(campo)  # type: ignore[literal-required]
        if tipo == 'bool' and (va is None or vb is None):
            continue
        if _valor_vazio_para_cmp(va) and _valor_vazio_para_cmp(vb):
            continue
        if not _valores_iguais(tipo, va, vb):
            divergencias.append(
                {
                    'campo': campo,
                    'label': label,
                    'legado': _fmt_valor_exibicao(tipo, vb) if not _valor_vazio_para_cmp(vb) else '—',
                    'cenario': _fmt_valor_exibicao(tipo, va) if not _valor_vazio_para_cmp(va) else '—',
                },
            )

    return divergencias


def comparar_regra_fiscal_saida_legado_cenario(
    *,
    produto_id: int | None = None,
    ncm: str | None = None,
    uf_origem: str,
    uf_destino: str,
    destinatario_contribuinte: str | None = None,
    consumidor_final: bool | None = None,
    tipo_operacao: str = 'VENDA',
    cenario_id: int | None = None,
    produto=None,
) -> ComparativoFiscalSaidaDict:
    """
    Compara RegraFiscalSaida (cenário) e RegraFiscal legado de forma independente.
    Não altera o cálculo oficial da proposta.
    """
    ctx, erros = _montar_contexto_busca(
        produto_id=produto_id,
        ncm=ncm,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        destinatario_contribuinte=destinatario_contribuinte,
        consumidor_final=consumidor_final,
        tipo_operacao=tipo_operacao,
        cenario_id=cenario_id,
        produto=produto,
    )
    mensagens: list[str] = list(erros)

    if ctx is None:
        return {
            'status': 'AMBOS_NAO_ENCONTRADOS',
            'cenario': _lado_vazio(),
            'legado': _lado_vazio(),
            'divergencias': [],
            'mensagens': mensagens,
            'origem_oficial_proposta': 'LEGADO',
            'origem_se_flag_cenario_ativa': 'NAO_ENCONTRADA',
        }

    regra_cenario = buscar_regra_fiscal_saida_apenas_cenario(
        produto_id=ctx.produto_id,
        ncm=ctx.ncm,
        uf_origem=ctx.uf_origem,
        uf_destino=ctx.uf_destino,
        destinatario_contribuinte=ctx.destinatario_contribuinte,
        consumidor_final=ctx.consumidor_final,
        tipo_operacao=ctx.tipo_operacao,
        cenario_id=ctx.cenario_id,
    )
    regra_legado = buscar_regra_fiscal_legado_apenas(ctx.ncm, ctx.uf_origem, ctx.uf_destino, 'Saída')

    lado_cenario = _snapshot_cenario(regra_cenario) if regra_cenario else _lado_vazio()
    lado_legado = _snapshot_legado(regra_legado) if regra_legado else _lado_vazio()

    if regra_cenario and not regra_legado:
        status: StatusComparativoFiscal = 'LEGADO_NAO_ENCONTRADO'
        mensagens.append('Cenário fiscal de saída possui regra, mas a tabela legada não.')
    elif regra_legado and not regra_cenario:
        status = 'CENARIO_NAO_ENCONTRADO'
        mensagens.append(
            'Cenário fiscal de saída ainda não possui regra para este item. '
            'A proposta continua usando a regra legada.',
        )
    elif not regra_cenario and not regra_legado:
        status = 'AMBOS_NAO_ENCONTRADOS'
        mensagens.append('Nenhuma regra encontrada no cenário novo nem na tabela legada.')
    else:
        divergencias = _listar_divergencias(lado_cenario, lado_legado)
        status = 'IGUAL' if not divergencias else 'DIVERGENTE'
        if status == 'DIVERGENTE':
            mensagens.append('Existem diferenças entre o cenário novo e a regra legada.')

    divergencias_final = (
        _listar_divergencias(lado_cenario, lado_legado)
        if regra_cenario and regra_legado
        else []
    )

    simulado = buscar_regra_fiscal_saida(
        produto_id=ctx.produto_id,
        ncm=ctx.ncm,
        uf_origem=ctx.uf_origem,
        uf_destino=ctx.uf_destino,
        destinatario_contribuinte=ctx.destinatario_contribuinte,
        consumidor_final=ctx.consumidor_final,
        tipo_operacao=ctx.tipo_operacao,
        cenario_id=ctx.cenario_id,
    )

    return {
        'status': status,
        'cenario': lado_cenario,
        'legado': lado_legado,
        'divergencias': divergencias_final,
        'mensagens': mensagens,
        'origem_oficial_proposta': 'LEGADO' if not use_cenario_fiscal_saida_for_propostas() else simulado['origem'],
        'origem_se_flag_cenario_ativa': simulado['origem'],
    }


class ResumoCoberturaPropostasDict(TypedDict):
    total_itens: int
    iguais: int
    divergentes: int
    cenario_nao_encontrado: int
    legado_nao_encontrado: int
    ambos_nao_encontrados: int
    percentual_cobertura_cenario: str
    percentual_iguais_entre_encontrados: str
    itens_analisados: int
    itens_ignorados_sem_contexto: int


class LadoResumoCoberturaDict(TypedDict):
    encontrado: bool
    regra_id: int | None
    cfop: str


class ItemCoberturaPropostaDict(TypedDict):
    proposta_id: int
    proposta_numero: str
    item_id: int
    produto_id: int | None
    produto_codigo: str
    produto_descricao: str
    ncm: str
    uf_origem: str
    uf_destino: str
    destinatario_contribuinte: str
    consumidor_final: bool | None
    tipo_operacao: str
    status: StatusComparativoFiscal
    divergencias: list[DivergenciaComparativoDict]
    cenario: LadoResumoCoberturaDict
    legado: LadoResumoCoberturaDict


class LacunaCoberturaPropostaDict(TypedDict):
    ncm: str
    uf_origem: str
    uf_destino: str
    destinatario_contribuinte: str
    consumidor_final: bool | None
    tipo_operacao: str
    quantidade_itens: int
    status_predominante: StatusComparativoFiscal
    acao_sugerida: str


class CoberturaPropostasFiscalSaidaDict(TypedDict):
    resumo: ResumoCoberturaPropostasDict
    itens: list[ItemCoberturaPropostaDict]
    lacunas: list[LacunaCoberturaPropostaDict]
    filtros_aplicados: dict[str, Any]


COBERTURA_MAX_SCAN_PADRAO = 500
COBERTURA_LIMITE_PADRAO = 50
COBERTURA_PERIODOD_PADRAO_DIAS = 90

# --- Checklist ativação global (Fase Saída 3.4) ---
CHECKLIST_COBERTURA_MINIMA_OK = Decimal('95.00')
CHECKLIST_COBERTURA_MINIMA_ATENCAO = Decimal('85.00')
CHECKLIST_DIVERGENCIA_MAXIMA_OK = Decimal('2.00')
CHECKLIST_DIVERGENCIA_MAXIMA_ATENCAO = Decimal('5.00')
CHECKLIST_SEM_CENARIO_MAXIMO_OK = Decimal('3.00')
CHECKLIST_SEM_CENARIO_MAXIMO_ATENCAO = Decimal('10.00')
CHECKLIST_AMBOS_NAO_PERCENTUAL_NAO_RECOMENDADO = Decimal('5.00')
CHECKLIST_AMOSTRA_MINIMA_ITENS = 10
CHECKLIST_LACUNAS_PRIORITARIAS_MAX = 15

StatusChecklistAtivacao = Literal['PODE_ATIVAR', 'ATENCAO', 'NAO_RECOMENDADO']
StatusCriterioChecklist = Literal['OK', 'ATENCAO', 'NAO_RECOMENDADO']


class ResumoChecklistAtivacaoDict(TypedDict):
    total_itens: int
    iguais: int
    divergentes: int
    cenario_nao_encontrado: int
    legado_nao_encontrado: int
    ambos_nao_encontrados: int
    percentual_cobertura_cenario: str
    percentual_divergentes: str
    percentual_sem_cenario: str
    percentual_iguais_entre_encontrados: str
    itens_ignorados_sem_contexto: int


class CriterioChecklistAtivacaoDict(TypedDict):
    codigo: str
    label: str
    status: StatusCriterioChecklist
    valor: str
    limite: str
    mensagem: str


class ChecklistAtivacaoCenarioSaidaDict(TypedDict):
    status: StatusChecklistAtivacao
    label: str
    resumo: ResumoChecklistAtivacaoDict
    criterios: list[CriterioChecklistAtivacaoDict]
    recomendacoes: list[str]
    lacunas_prioritarias: list[LacunaCoberturaPropostaDict]
    filtros_aplicados: dict[str, Any]


def _parse_bool_query(value: str | None) -> bool:
    return (value or '').strip().lower() in ('1', 'true', 'sim', 'yes')


def _lado_resumo_cobertura(lado: LadoComparativoFiscalDict) -> LadoResumoCoberturaDict:
    return {
        'encontrado': bool(lado['encontrado']),
        'regra_id': lado.get('regra_id'),
        'cfop': lado.get('cfop') or '',
    }


def _contexto_fiscal_de_item_proposta(item: ItemProposta) -> dict[str, Any] | None:
    proposta = item.proposta
    ufo = (proposta.uf_origem or '').strip().upper()[:2]
    if len(ufo) != 2 and proposta.empresa_emitente_id and proposta.empresa_emitente:
        ufo = (proposta.empresa_emitente.uf or '').strip().upper()[:2]
    ufd = ''
    if proposta.cliente_id and proposta.cliente:
        ufd = (proposta.cliente.uf or '').strip().upper()[:2]
    if len(ufd) != 2:
        ufd = (proposta.uf_destino_avulso or '').strip().upper()[:2]

    produto_id: int | None = None
    ncm = ''
    produto = item.produto
    if produto is not None:
        produto_id = produto.pk
        ncm = normalize_ncm(produto.get_ncm_efetivo_codigo() or produto.ncm or '')
    else:
        ncm = normalize_ncm(item.ncm_avulso or '')

    if len(ncm) < 8 or len(ufo) != 2 or len(ufd) != 2:
        return None

    return {
        'produto_id': produto_id,
        'ncm': ncm,
        'uf_origem': ufo,
        'uf_destino': ufd,
        'destinatario_contribuinte': None,
        'consumidor_final': None,
        'tipo_operacao': 'VENDA',
        'cenario_id': None,
    }


def _query_itens_proposta_cobertura(
    *,
    data_inicial: date | None,
    data_final: date | None,
    proposta_id: int | None,
    cliente_id: int | None,
    status_proposta: str | None,
    ncm: str | None,
    uf_origem: str | None,
    uf_destino: str | None,
) -> Any:
    qs = (
        ItemProposta.objects.select_related(
            'proposta',
            'proposta__cliente',
            'proposta__empresa_emitente',
            'produto',
        )
        .order_by('-proposta__data', '-proposta__id', 'id')
    )
    if data_inicial:
        qs = qs.filter(proposta__data__gte=data_inicial)
    if data_final:
        qs = qs.filter(proposta__data__lte=data_final)
    if proposta_id:
        qs = qs.filter(proposta_id=proposta_id)
    if cliente_id:
        qs = qs.filter(proposta__cliente_id=cliente_id)
    if status_proposta:
        qs = qs.filter(proposta__status__iexact=status_proposta.strip())
    if ncm:
        ncm_norm = normalize_ncm(ncm)
        if ncm_norm:
            qs = qs.filter(
                Q(produto__ncm__icontains=ncm_norm)
                | Q(ncm_avulso__icontains=ncm_norm)
                | Q(produto__ncm__icontains=ncm),
            )
    if uf_origem and len(uf_origem) == 2:
        qs = qs.filter(
            Q(proposta__uf_origem=uf_origem) | Q(proposta__empresa_emitente__uf=uf_origem),
        )
    if uf_destino and len(uf_destino) == 2:
        qs = qs.filter(
            Q(proposta__cliente__uf=uf_destino) | Q(proposta__uf_destino_avulso=uf_destino),
        )
    return qs


def _calcular_resumo_cobertura(itens: list[ItemCoberturaPropostaDict]) -> ResumoCoberturaPropostasDict:
    total = len(itens)
    iguais = sum(1 for i in itens if i['status'] == 'IGUAL')
    divergentes = sum(1 for i in itens if i['status'] == 'DIVERGENTE')
    cenario_nao = sum(1 for i in itens if i['status'] == 'CENARIO_NAO_ENCONTRADO')
    legado_nao = sum(1 for i in itens if i['status'] == 'LEGADO_NAO_ENCONTRADO')
    ambos_nao = sum(1 for i in itens if i['status'] == 'AMBOS_NAO_ENCONTRADOS')
    cenario_encontrado = iguais + divergentes + legado_nao
    ambos_comparaveis = iguais + divergentes
    pct_cobertura = (Decimal(cenario_encontrado) / Decimal(total) * 100) if total else Decimal('0')
    pct_iguais = (Decimal(iguais) / Decimal(ambos_comparaveis) * 100) if ambos_comparaveis else Decimal('0')
    return {
        'total_itens': total,
        'iguais': iguais,
        'divergentes': divergentes,
        'cenario_nao_encontrado': cenario_nao,
        'legado_nao_encontrado': legado_nao,
        'ambos_nao_encontrados': ambos_nao,
        'percentual_cobertura_cenario': f'{pct_cobertura.quantize(Decimal("0.01")):.2f}',
        'percentual_iguais_entre_encontrados': f'{pct_iguais.quantize(Decimal("0.01")):.2f}',
        'itens_analisados': total,
        'itens_ignorados_sem_contexto': 0,
    }


def _montar_lacunas_cobertura(itens: list[ItemCoberturaPropostaDict]) -> list[LacunaCoberturaPropostaDict]:
    grupos: dict[tuple, list[ItemCoberturaPropostaDict]] = defaultdict(list)
    for row in itens:
        if row['status'] not in ('CENARIO_NAO_ENCONTRADO', 'AMBOS_NAO_ENCONTRADOS'):
            continue
        chave = (
            row['ncm'],
            row['uf_origem'],
            row['uf_destino'],
            row['destinatario_contribuinte'] or '',
            row['consumidor_final'],
            row['tipo_operacao'],
        )
        grupos[chave].append(row)

    lacunas: list[LacunaCoberturaPropostaDict] = []
    for chave, rows in grupos.items():
        ncm, ufo, ufd, dest, cf, tipo = chave
        status_counter = Counter(r['status'] for r in rows)
        status_pred = status_counter.most_common(1)[0][0]
        if status_pred == 'AMBOS_NAO_ENCONTRADOS':
            acao = 'Cadastre regra no cenário fiscal de saída e na tabela legada, se necessário.'
        else:
            acao = 'Cadastre regra no cenário fiscal de saída (escopo NCM/UF).'
        lacunas.append(
            {
                'ncm': ncm,
                'uf_origem': ufo,
                'uf_destino': ufd,
                'destinatario_contribuinte': dest,
                'consumidor_final': cf,
                'tipo_operacao': tipo,
                'quantidade_itens': len(rows),
                'status_predominante': status_pred,
                'acao_sugerida': acao,
            },
        )
    lacunas.sort(key=lambda x: (-x['quantidade_itens'], x['ncm'], x['uf_origem']))
    return lacunas


def _item_row_cobertura(item: ItemProposta, ctx: dict[str, Any], cmp: ComparativoFiscalSaidaDict) -> ItemCoberturaPropostaDict:
    prod = item.produto
    codigo = ''
    descricao = (item.descricao_avulsa or '').strip()
    if prod is not None:
        codigo = (prod.codigo_completo or '').strip()
        descricao = (prod.descricao or descricao).strip()
    return {
        'proposta_id': item.proposta_id,
        'proposta_numero': item.proposta.numero,
        'item_id': item.pk,
        'produto_id': ctx.get('produto_id'),
        'produto_codigo': codigo,
        'produto_descricao': descricao,
        'ncm': ctx['ncm'],
        'uf_origem': ctx['uf_origem'],
        'uf_destino': ctx['uf_destino'],
        'destinatario_contribuinte': (ctx.get('destinatario_contribuinte') or '').strip(),
        'consumidor_final': ctx.get('consumidor_final'),
        'tipo_operacao': ctx.get('tipo_operacao') or 'VENDA',
        'status': cmp['status'],
        'divergencias': cmp['divergencias'],
        'cenario': _lado_resumo_cobertura(cmp['cenario']),
        'legado': _lado_resumo_cobertura(cmp['legado']),
    }


def cobertura_propostas_fiscal_saida(
    *,
    data_inicial: date | None = None,
    data_final: date | None = None,
    proposta_id: int | None = None,
    cliente_id: int | None = None,
    status_proposta: str | None = None,
    ncm: str | None = None,
    uf_origem: str | None = None,
    uf_destino: str | None = None,
    somente_divergentes: bool = False,
    somente_sem_cenario: bool = False,
    limite: int = COBERTURA_LIMITE_PADRAO,
    max_scan: int = COBERTURA_MAX_SCAN_PADRAO,
    cenario_id: int | None = None,
) -> CoberturaPropostasFiscalSaidaDict:
    """
    Homologação em lote: compara itens de propostas (legado × cenário) sem alterar propostas.
    """
    limite = min(max(int(limite or COBERTURA_LIMITE_PADRAO), 1), 500)
    max_scan = min(max(int(max_scan or COBERTURA_MAX_SCAN_PADRAO), limite), 2000)

    ufo_f = _norm_uf(uf_origem) if uf_origem else ''
    ufd_f = _norm_uf(uf_destino) if uf_destino else ''
    if uf_origem and len(ufo_f) != 2:
        raise ValueError('uf_origem inválida.')
    if uf_destino and len(ufd_f) != 2:
        raise ValueError('uf_destino inválida.')

    qs = _query_itens_proposta_cobertura(
        data_inicial=data_inicial,
        data_final=data_final,
        proposta_id=proposta_id,
        cliente_id=cliente_id,
        status_proposta=status_proposta,
        ncm=ncm,
        uf_origem=ufo_f or None,
        uf_destino=ufd_f or None,
    )

    itens_analisados: list[ItemCoberturaPropostaDict] = []
    ignorados = 0
    itens_retorno: list[ItemCoberturaPropostaDict] = []

    for item in qs[:max_scan]:
        ctx = _contexto_fiscal_de_item_proposta(item)
        if ctx is None:
            ignorados += 1
            continue
        if cenario_id:
            ctx['cenario_id'] = cenario_id
        cmp = comparar_regra_fiscal_saida_legado_cenario(**ctx)
        row = _item_row_cobertura(item, ctx, cmp)
        itens_analisados.append(row)

        if somente_divergentes and row['status'] != 'DIVERGENTE':
            continue
        if somente_sem_cenario and row['status'] not in (
            'CENARIO_NAO_ENCONTRADO',
            'AMBOS_NAO_ENCONTRADOS',
        ):
            continue
        if len(itens_retorno) < limite:
            itens_retorno.append(row)

    resumo = _calcular_resumo_cobertura(itens_analisados)
    resumo['itens_ignorados_sem_contexto'] = ignorados

    return {
        'resumo': resumo,
        'itens': itens_retorno,
        'lacunas': _montar_lacunas_cobertura(itens_analisados),
        'filtros_aplicados': {
            'data_inicial': data_inicial.isoformat() if data_inicial else None,
            'data_final': data_final.isoformat() if data_final else None,
            'proposta_id': proposta_id,
            'cliente_id': cliente_id,
            'status_proposta': status_proposta,
            'ncm': ncm,
            'uf_origem': ufo_f or None,
            'uf_destino': ufd_f or None,
            'somente_divergentes': somente_divergentes,
            'somente_sem_cenario': somente_sem_cenario,
            'limite': limite,
            'max_scan': max_scan,
            'cenario_id': cenario_id,
        },
    }


def _percentual_sobre_total(parte: int, total: int) -> Decimal:
    if total <= 0:
        return Decimal('0')
    return (Decimal(parte) / Decimal(total) * 100).quantize(Decimal('0.01'))


def _classificar_maior_melhor(
    valor: Decimal,
    *,
    minimo_ok: Decimal,
    minimo_atencao: Decimal,
) -> StatusCriterioChecklist:
    if valor >= minimo_ok:
        return 'OK'
    if valor >= minimo_atencao:
        return 'ATENCAO'
    return 'NAO_RECOMENDADO'


def _classificar_menor_melhor(
    valor: Decimal,
    *,
    maximo_ok: Decimal,
    maximo_atencao: Decimal,
) -> StatusCriterioChecklist:
    if valor <= maximo_ok:
        return 'OK'
    if valor <= maximo_atencao:
        return 'ATENCAO'
    return 'NAO_RECOMENDADO'


def _status_geral_checklist(criterios: list[CriterioChecklistAtivacaoDict]) -> StatusChecklistAtivacao:
    if any(c['status'] == 'NAO_RECOMENDADO' for c in criterios):
        return 'NAO_RECOMENDADO'
    if any(c['status'] == 'ATENCAO' for c in criterios):
        return 'ATENCAO'
    return 'PODE_ATIVAR'


def _label_status_checklist(status: StatusChecklistAtivacao) -> str:
    if status == 'PODE_ATIVAR':
        return 'Pode ativar'
    if status == 'ATENCAO':
        return 'Atenção'
    return 'Não recomendado'


def _montar_recomendacoes_checklist(criterios: list[CriterioChecklistAtivacaoDict]) -> list[str]:
    por_codigo = {c['codigo']: c for c in criterios}
    msgs: list[str] = []
    amostra = por_codigo.get('AMOSTRA_MINIMA')
    if amostra and amostra['status'] != 'OK':
        msgs.append('Amostra pequena: analise mais propostas antes de ativar globalmente.')
    cobertura = por_codigo.get('COBERTURA_MINIMA')
    if cobertura and cobertura['status'] != 'OK':
        msgs.append('Cadastre regras no cenário fiscal para os NCMs/UFs sem cobertura.')
    sem_cenario = por_codigo.get('SEM_CENARIO')
    if sem_cenario and sem_cenario['status'] != 'OK':
        msgs.append('Reduza itens sem regra no cenário fiscal de saída.')
    divergencias = por_codigo.get('DIVERGENCIAS')
    if divergencias and divergencias['status'] != 'OK':
        msgs.append('Revise divergências de tributos (ex.: ICMS) antes de ativar globalmente.')
    ambos = por_codigo.get('AMBOS_NAO_ENCONTRADOS')
    if ambos and ambos['status'] != 'OK':
        msgs.append('Há combinações NCM/UF sem regra nem no cenário nem no legado.')
    if not msgs:
        msgs.append(
            'O cenário fiscal parece pronto para ativação global; a decisão final ainda é via configuração de ambiente.',
        )
    return msgs


def avaliar_prontidao_ativacao_cenario_saida(
    *,
    data_inicial: date | None = None,
    data_final: date | None = None,
    proposta_id: int | None = None,
    cliente_id: int | None = None,
    status_proposta: str | None = None,
    ncm: str | None = None,
    uf_origem: str | None = None,
    uf_destino: str | None = None,
    limite: int = COBERTURA_LIMITE_PADRAO,
    max_scan: int = COBERTURA_MAX_SCAN_PADRAO,
    cenario_id: int | None = None,
) -> ChecklistAtivacaoCenarioSaidaDict:
    """
    Diagnóstico read-only para decidir se é seguro ligar USE_CENARIO_FISCAL_SAIDA_FOR_PROPOSTAS.
    Reaproveita cobertura_propostas_fiscal_saida sem alterar propostas ou flags.
    """
    cobertura = cobertura_propostas_fiscal_saida(
        data_inicial=data_inicial,
        data_final=data_final,
        proposta_id=proposta_id,
        cliente_id=cliente_id,
        status_proposta=status_proposta,
        ncm=ncm,
        uf_origem=uf_origem,
        uf_destino=uf_destino,
        somente_divergentes=False,
        somente_sem_cenario=False,
        limite=limite,
        max_scan=max_scan,
        cenario_id=cenario_id,
    )
    base = cobertura['resumo']
    total = int(base['total_itens'])
    divergentes = int(base['divergentes'])
    cenario_nao = int(base['cenario_nao_encontrado'])
    ambos_nao = int(base['ambos_nao_encontrados'])

    pct_cobertura = Decimal(str(base['percentual_cobertura_cenario']))
    pct_divergentes = _percentual_sobre_total(divergentes, total)
    pct_sem_cenario = _percentual_sobre_total(cenario_nao, total)
    pct_ambos_nao = _percentual_sobre_total(ambos_nao, total)

    st_cobertura = _classificar_maior_melhor(
        pct_cobertura,
        minimo_ok=CHECKLIST_COBERTURA_MINIMA_OK,
        minimo_atencao=CHECKLIST_COBERTURA_MINIMA_ATENCAO,
    )
    st_divergencias = _classificar_menor_melhor(
        pct_divergentes,
        maximo_ok=CHECKLIST_DIVERGENCIA_MAXIMA_OK,
        maximo_atencao=CHECKLIST_DIVERGENCIA_MAXIMA_ATENCAO,
    )
    st_sem_cenario = _classificar_menor_melhor(
        pct_sem_cenario,
        maximo_ok=CHECKLIST_SEM_CENARIO_MAXIMO_OK,
        maximo_atencao=CHECKLIST_SEM_CENARIO_MAXIMO_ATENCAO,
    )

    if ambos_nao == 0:
        st_ambos = 'OK'
        msg_ambos = 'Nenhum item ficou sem regra no cenário e no legado.'
    elif pct_ambos_nao > CHECKLIST_AMBOS_NAO_PERCENTUAL_NAO_RECOMENDADO:
        st_ambos = 'NAO_RECOMENDADO'
        msg_ambos = (
            f'{ambos_nao} item(ns) sem regra no cenário nem no legado '
            f'({pct_ambos_nao}% da amostra).'
        )
    else:
        st_ambos = 'ATENCAO'
        msg_ambos = (
            f'{ambos_nao} item(ns) sem regra no cenário nem no legado; revise antes da ativação global.'
        )

    if total < CHECKLIST_AMOSTRA_MINIMA_ITENS:
        st_amostra = 'ATENCAO'
        msg_amostra = (
            f'Amostra analisada é pequena ({total} itens). '
            'Valide mais propostas antes de ativar globalmente.'
        )
    else:
        st_amostra = 'OK'
        msg_amostra = f'Amostra com {total} itens analisados.'

    criterios: list[CriterioChecklistAtivacaoDict] = [
        {
            'codigo': 'COBERTURA_MINIMA',
            'label': 'Cobertura mínima do cenário',
            'status': st_cobertura,
            'valor': f'{pct_cobertura:.2f}',
            'limite': f'{CHECKLIST_COBERTURA_MINIMA_OK:.2f}',
            'mensagem': (
                'Cobertura do cenário fiscal acima do mínimo recomendado.'
                if st_cobertura == 'OK'
                else (
                    'Cobertura do cenário abaixo do ideal; revise lacunas de cadastro.'
                    if st_cobertura == 'ATENCAO'
                    else 'Cobertura do cenário insuficiente para ativação global.'
                )
            ),
        },
        {
            'codigo': 'DIVERGENCIAS',
            'label': 'Divergências entre cenário e legado',
            'status': st_divergencias,
            'valor': f'{pct_divergentes:.2f}',
            'limite': f'{CHECKLIST_DIVERGENCIA_MAXIMA_OK:.2f}',
            'mensagem': (
                'Divergências dentro do limite recomendado.'
                if st_divergencias == 'OK'
                else (
                    'Existem divergências acima do limite recomendado.'
                    if st_divergencias == 'ATENCAO'
                    else 'Divergências elevadas; não recomendamos ativar globalmente ainda.'
                )
            ),
        },
        {
            'codigo': 'SEM_CENARIO',
            'label': 'Itens sem regra no cenário',
            'status': st_sem_cenario,
            'valor': f'{pct_sem_cenario:.2f}',
            'limite': f'{CHECKLIST_SEM_CENARIO_MAXIMO_OK:.2f}',
            'mensagem': (
                'Poucos itens sem regra no cenário fiscal.'
                if st_sem_cenario == 'OK'
                else (
                    'Percentual de itens sem cenário acima do ideal.'
                    if st_sem_cenario == 'ATENCAO'
                    else 'Muitos itens sem regra no cenário; cadastre antes de ativar globalmente.'
                )
            ),
        },
        {
            'codigo': 'AMBOS_NAO_ENCONTRADOS',
            'label': 'Sem regra no cenário nem no legado',
            'status': st_ambos,
            'valor': f'{pct_ambos_nao:.2f}',
            'limite': f'{CHECKLIST_AMBOS_NAO_PERCENTUAL_NAO_RECOMENDADO:.2f}',
            'mensagem': msg_ambos,
        },
        {
            'codigo': 'AMOSTRA_MINIMA',
            'label': 'Tamanho da amostra analisada',
            'status': st_amostra,
            'valor': str(total),
            'limite': str(CHECKLIST_AMOSTRA_MINIMA_ITENS),
            'mensagem': msg_amostra,
        },
    ]

    status_geral = _status_geral_checklist(criterios)
    resumo_checklist: ResumoChecklistAtivacaoDict = {
        'total_itens': total,
        'iguais': int(base['iguais']),
        'divergentes': divergentes,
        'cenario_nao_encontrado': cenario_nao,
        'legado_nao_encontrado': int(base['legado_nao_encontrado']),
        'ambos_nao_encontrados': ambos_nao,
        'percentual_cobertura_cenario': base['percentual_cobertura_cenario'],
        'percentual_divergentes': f'{pct_divergentes:.2f}',
        'percentual_sem_cenario': f'{pct_sem_cenario:.2f}',
        'percentual_iguais_entre_encontrados': base['percentual_iguais_entre_encontrados'],
        'itens_ignorados_sem_contexto': int(base.get('itens_ignorados_sem_contexto', 0)),
    }

    return {
        'status': status_geral,
        'label': _label_status_checklist(status_geral),
        'resumo': resumo_checklist,
        'criterios': criterios,
        'recomendacoes': _montar_recomendacoes_checklist(criterios),
        'lacunas_prioritarias': cobertura['lacunas'][:CHECKLIST_LACUNAS_PRIORITARIAS_MAX],
        'filtros_aplicados': cobertura['filtros_aplicados'],
    }


def parse_filtros_cobertura_propostas_request(request) -> tuple[dict[str, Any], str | None]:
    """Monta kwargs para cobertura_propostas_fiscal_saida a partir da query string."""
    data_inicial = parse_date((request.query_params.get('data_inicial') or '').strip())
    data_final = parse_date((request.query_params.get('data_final') or '').strip())
    if (request.query_params.get('data_inicial') or '').strip() and data_inicial is None:
        return {}, 'data_inicial inválida.'
    if (request.query_params.get('data_final') or '').strip() and data_final is None:
        return {}, 'data_final inválida.'
    if data_inicial and data_final and data_inicial > data_final:
        return {}, 'data_inicial não pode ser posterior a data_final.'

    proposta_id_raw = (request.query_params.get('proposta_id') or '').strip()
    cliente_id_raw = (request.query_params.get('cliente_id') or '').strip()
    cenario_id_raw = (request.query_params.get('cenario_id') or '').strip()
    limite_raw = (request.query_params.get('limite') or '').strip()

    tem_escopo_explicito = any(
        (request.query_params.get(k) or '').strip()
        for k in ('proposta_id', 'cliente_id', 'status_proposta', 'ncm', 'proposta_id')
    )
    tem_periodo_explicito = bool(
        (request.query_params.get('data_inicial') or '').strip()
        or (request.query_params.get('data_final') or '').strip(),
    )

    if not tem_periodo_explicito and not tem_escopo_explicito:
        data_final = data_final or date.today()
        data_inicial = data_inicial or (data_final - timedelta(days=COBERTURA_PERIODOD_PADRAO_DIAS))
    elif data_final is None and data_inicial is not None:
        data_final = date.today()
    elif data_inicial is None and data_final is not None:
        data_inicial = data_final - timedelta(days=COBERTURA_PERIODOD_PADRAO_DIAS)

    limite = int(limite_raw) if limite_raw.isdigit() else COBERTURA_LIMITE_PADRAO
    max_scan_raw = (request.query_params.get('max_scan') or '').strip()
    max_scan = int(max_scan_raw) if max_scan_raw.isdigit() else COBERTURA_MAX_SCAN_PADRAO

    return {
        'data_inicial': data_inicial,
        'data_final': data_final,
        'proposta_id': int(proposta_id_raw) if proposta_id_raw.isdigit() else None,
        'cliente_id': int(cliente_id_raw) if cliente_id_raw.isdigit() else None,
        'status_proposta': (request.query_params.get('status_proposta') or '').strip() or None,
        'ncm': (request.query_params.get('ncm') or '').strip() or None,
        'uf_origem': (request.query_params.get('uf_origem') or '').strip().upper() or None,
        'uf_destino': (request.query_params.get('uf_destino') or '').strip().upper() or None,
        'somente_divergentes': _parse_bool_query(request.query_params.get('somente_divergentes')),
        'somente_sem_cenario': _parse_bool_query(request.query_params.get('somente_sem_cenario')),
        'limite': limite,
        'max_scan': max_scan,
        'cenario_id': int(cenario_id_raw) if cenario_id_raw.isdigit() else None,
    }, None


def aplicar_resultado_busca_em_percentuais(resultado: BuscaRegraFiscalSaidaDict) -> dict[str, Any]:
    """Converte resultado da busca em campos de percentuais para ItemProposta."""
    if resultado['origem'] == 'NAO_ENCONTRADA':
        return {
            'icms_saida_percentual': Decimal('0'),
            'pis_saida_percentual': Decimal('0'),
            'cofins_saida_percentual': Decimal('0'),
            'ipi_saida_percentual': Decimal('0'),
            'regra_fiscal_id': None,
            'regra_fiscal_origem': resultado['origem'],
            'regra_fiscal_saida_id': None,
            'deduzir_icms_base_pis': False,
            'deduzir_icms_base_cofins': False,
            'mensagens_base_pis_cofins': [],
        }
    return {
        'icms_saida_percentual': Decimal(resultado['aliquota_icms'] or '0'),
        'pis_saida_percentual': Decimal(resultado['aliquota_pis'] or '0'),
        'cofins_saida_percentual': Decimal(resultado['aliquota_cofins'] or '0'),
        'ipi_saida_percentual': Decimal(resultado['aliquota_ipi'] or '0'),
        'regra_fiscal_id': resultado.get('regra_legada_id'),
        'regra_fiscal_origem': resultado['origem'],
        'regra_fiscal_saida_id': resultado.get('regra_id'),
        'deduzir_icms_base_pis': bool(resultado.get('deduzir_icms_base_pis')),
        'deduzir_icms_base_cofins': bool(resultado.get('deduzir_icms_base_cofins')),
        'mensagens_base_pis_cofins': list(resultado.get('mensagens') or []),
    }
