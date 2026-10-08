"""ERP 4.0.10.x — classificação de documentos DF-e e regras de inclusão fiscal.

Homologação nunca entra em apuração, contabilidade, precificação oficial ou BI fiscal oficial.
Base DF-e importada alimenta apuração quando produção + autorizada + válida.
Conferência revisa dados sem gerar efeito operacional automático.
"""

from __future__ import annotations

from typing import Any, Protocol

from django.db.models import Q

from apps.fiscal.models import (
    CTeHistoricoImportado,
    NFeEntrada,
    NFeEntradaHistoricaImportada,
    NFeSaida,
    NFeSaidaHistoricaImportada,
)

# --- Categorias conceituais (documentação / UI) ---
CATEGORIA_OPERACIONAL = 'OPERACIONAL'
CATEGORIA_BASE_DFE_IMPORTADA = 'BASE_DFE_IMPORTADA'
CATEGORIA_HOMOLOGACAO = 'HOMOLOGACAO'
CATEGORIA_FUTURO_DFE_RECEBIDO = 'FUTURO_DFE_RECEBIDO'
CATEGORIA_RECEBIDO_DFE_FUTURO = 'RECEBIDO_DFE_FUTURO'  # alias documentação 4.0.10.2

# Estado conferência (base importada) — não é categoria de origem do XML
ESTADO_CONFERIDO = 'CONFERIDO'
ESTADOS_CONFERENCIA_BASE_IMPORTADA = frozenset({
    'IMPORTADA',
    'IMPORTADO',
    'PROCESSADO',
    'PREPARADA',
    'PREPARADO',
    'CONFERIDA',
    'CONFERIDO',
    'DIVERGENTE',
    'IGNORADA',
    'IGNORADO',
})

TP_AMB_PRODUCAO = '1'
TP_AMB_HOMOLOGACAO = '2'

CSTAT_AUTORIZADO = frozenset({'100', '100.0'})

_STATUS_EMISSAO_HOMOLOG = frozenset({
    'AUTORIZADA_HOMOLOGACAO',
    'REJEITADA_HOMOLOGACAO',
})

_STATUS_EMISSAO_INVALIDO_APURACAO = frozenset({
    'RASCUNHO',
    'NUMERACAO_RESERVADA',
    'XML_GERADO',
    'XML_ASSINADO',
    'ENVIADA_HOMOLOGACAO',
    'REJEITADA_HOMOLOGACAO',
    'ERRO_TRANSMISSAO',
    'LOTE_PROCESSADO_SEM_PROTOCOLO',
    'ERRO_RETORNO_SEFAZ',
    'AGUARDANDO_PROCESSAMENTO',
})


class DocumentoFiscalLike(Protocol):
    """Protocolo mínimo para helpers genéricos."""


def _norm_status(s: str | None) -> str:
    return (s or '').strip().upper()


def _tp_amb_producao(tp_amb: str | None) -> bool:
    if not tp_amb:
        return True  # legado sem tp_amb: tratar como produção na apuração
    return str(tp_amb).strip() == TP_AMB_PRODUCAO


def _tp_amb_homologacao(tp_amb: str | None) -> bool:
    return str(tp_amb or '').strip() == TP_AMB_HOMOLOGACAO


def eh_documento_homologacao(documento: Any) -> bool:
    """True se documento é de ambiente de homologação / sem valor fiscal."""
    if isinstance(documento, NFeSaida):
        if documento.ambiente_emissao == NFeSaida.AmbienteEmissao.HOMOLOGACAO:
            return True
        sefaz = _norm_status(documento.status_emissao_sefaz)
        if sefaz in _STATUS_EMISSAO_HOMOLOG:
            return True
        return False

    if isinstance(documento, (NFeSaidaHistoricaImportada, NFeEntradaHistoricaImportada, CTeHistoricoImportado)):
        return _tp_amb_homologacao(getattr(documento, 'tp_amb', None))

    return False


def eh_documento_producao(documento: Any) -> bool:
    if eh_documento_homologacao(documento):
        return False
    if isinstance(documento, NFeSaida):
        if documento.ambiente_emissao == NFeSaida.AmbienteEmissao.PRODUCAO:
            return True
        sefaz = _norm_status(documento.status_emissao_sefaz)
        if sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
            return False
        if sefaz in _STATUS_EMISSAO_HOMOLOG:
            return False
        return documento.ambiente_emissao != NFeSaida.AmbienteEmissao.HOMOLOGACAO
    if isinstance(documento, (NFeSaidaHistoricaImportada, NFeEntradaHistoricaImportada, CTeHistoricoImportado)):
        return _tp_amb_producao(getattr(documento, 'tp_amb', None))
    if isinstance(documento, (NFeEntrada,)):
        return True
    return True


def eh_documento_autorizado(documento: Any, *, incluir_canceladas: bool = False) -> bool:
    if isinstance(documento, NFeSaida):
        sefaz = _norm_status(documento.status_emissao_sefaz)
        if sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
            return False
        if sefaz in _STATUS_EMISSAO_INVALIDO_APURACAO:
            return False
        st = _norm_status(documento.status)
        if st in {'CANCELADA', 'CANCELADO', 'CANCELADA_INTERNA'}:
            return incluir_canceladas
        if sefaz:
            return True
        return st in {'EMITIDA', 'EMITIDO', 'AUTORIZADA', 'AUTORIZADA_INTERNA'}

    if isinstance(documento, NFeSaidaHistoricaImportada):
        if documento.cancelada and not incluir_canceladas:
            return False
        cstat = (documento.cstat or '').strip()
        if cstat in CSTAT_AUTORIZADO or cstat == '100':
            return True
        st = (documento.status_documento or '').strip().lower()
        return st in {'autorizada', 'autorizado'}

    if isinstance(documento, NFeEntradaHistoricaImportada):
        cstat = (documento.cstat or '').strip()
        return cstat in CSTAT_AUTORIZADO or cstat == '100'

    if isinstance(documento, CTeHistoricoImportado):
        if documento.cancelado and not incluir_canceladas:
            return False
        cstat = (documento.cstat or '').strip()
        if cstat in CSTAT_AUTORIZADO or cstat == '100':
            return True
        st = (documento.status_documento or '').strip().lower()
        return st in {'autorizado', 'autorizada'}

    if isinstance(documento, NFeEntrada):
        return True

    return False


def tem_valor_fiscal(documento: Any) -> bool:
    if eh_documento_homologacao(documento):
        return False
    if isinstance(documento, NFeSaida):
        return _norm_status(documento.status_emissao_sefaz) not in _STATUS_EMISSAO_HOMOLOG
    return True


def categoria_documento(documento: Any) -> str:
    if eh_documento_homologacao(documento):
        return CATEGORIA_HOMOLOGACAO
    if isinstance(documento, (NFeSaidaHistoricaImportada, NFeEntradaHistoricaImportada, CTeHistoricoImportado)):
        return CATEGORIA_BASE_DFE_IMPORTADA
    if isinstance(documento, (NFeSaida, NFeEntrada)):
        return CATEGORIA_OPERACIONAL
    return CATEGORIA_BASE_DFE_IMPORTADA


def pode_entrar_apuracao(
    documento: Any,
    *,
    incluir_canceladas: bool = False,
) -> bool:
    """Documento válido para apuração fiscal gerencial (produção, autorizado, com valor fiscal)."""
    if eh_documento_homologacao(documento):
        return False
    if not eh_documento_producao(documento):
        return False
    if not tem_valor_fiscal(documento):
        return False

    if isinstance(documento, NFeSaida):
        sefaz = _norm_status(documento.status_emissao_sefaz)
        if sefaz in _STATUS_EMISSAO_INVALIDO_APURACAO or sefaz == NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO:
            return False
        st = _norm_status(documento.status)
        if st == 'RASCUNHO':
            return False
        if st in {'CANCELADA', 'CANCELADO', 'CANCELADA_INTERNA'}:
            return incluir_canceladas
        return True

    if isinstance(documento, (NFeSaidaHistoricaImportada, NFeEntradaHistoricaImportada, CTeHistoricoImportado)):
        if getattr(documento, 'cancelada', False) or getattr(documento, 'cancelado', False):
            return incluir_canceladas
        return eh_documento_autorizado(documento, incluir_canceladas=incluir_canceladas)

    if isinstance(documento, NFeEntrada):
        return True

    return eh_documento_autorizado(documento, incluir_canceladas=incluir_canceladas)


def pode_alimentar_precificacao(documento: Any) -> bool:
    if eh_documento_homologacao(documento):
        return False
    if isinstance(documento, NFeSaida):
        if _norm_status(documento.status_emissao_sefaz) in _STATUS_EMISSAO_INVALIDO_APURACAO:
            return False
    return pode_entrar_apuracao(documento) or (
        isinstance(documento, (NFeSaidaHistoricaImportada, NFeEntradaHistoricaImportada, CTeHistoricoImportado))
        and eh_documento_producao(documento)
        and eh_documento_autorizado(documento)
    )


def pode_gerar_efeito_operacional(documento: Any) -> bool:
    if isinstance(documento, (NFeSaidaHistoricaImportada, NFeEntradaHistoricaImportada, CTeHistoricoImportado)):
        return False
    if eh_documento_homologacao(documento):
        return False
    return isinstance(documento, (NFeSaida, NFeEntrada))


# --- Queryset filters (apuração) ---

def q_excluir_homologacao_historica_saida() -> Q:
    return Q(tp_amb=TP_AMB_PRODUCAO) | Q(tp_amb='') | Q(tp_amb__isnull=True)


def q_excluir_homologacao_historica_entrada() -> Q:
    return Q(tp_amb=TP_AMB_PRODUCAO) | Q(tp_amb='') | Q(tp_amb__isnull=True)


def q_excluir_homologacao_cte() -> Q:
    return Q(tp_amb=TP_AMB_PRODUCAO) | Q(tp_amb='') | Q(tp_amb__isnull=True)


def q_excluir_homologacao_nfe_saida_operacional() -> Q:
    """Exclui NF-e Saída ERP em homologação ou sem autorização produção."""
    return ~Q(ambiente_emissao=NFeSaida.AmbienteEmissao.HOMOLOGACAO) & ~Q(
        status_emissao_sefaz__in=[
            NFeSaida.StatusEmissaoSefaz.AUTORIZADA_HOMOLOGACAO,
            NFeSaida.StatusEmissaoSefaz.REJEITADA_HOMOLOGACAO,
            NFeSaida.StatusEmissaoSefaz.ERRO_TRANSMISSAO,
            NFeSaida.StatusEmissaoSefaz.ENVIADA_HOMOLOGACAO,
        ],
    )


def q_nfe_saida_operacional_apuracao() -> Q:
    """NF-e operacional elegível à apuração (emitida legado ou futura produção)."""
    return (
        q_excluir_homologacao_nfe_saida_operacional()
        & ~Q(status__iexact='RASCUNHO')
        & ~Q(status__iexact='CANCELADA')
        & ~Q(status__iexact='CANCELADO')
    )


def filtrar_queryset_apuracao_historica_saida(qs):
    return qs.filter(q_excluir_homologacao_historica_saida())


def filtrar_queryset_apuracao_historica_entrada(qs):
    return qs.filter(q_excluir_homologacao_historica_entrada())


def filtrar_queryset_apuracao_cte(qs):
    return qs.filter(q_excluir_homologacao_cte())


def filtrar_queryset_apuracao_nfe_saida(qs):
    return qs.filter(q_nfe_saida_operacional_apuracao())


def q_historico_autorizado_producao() -> Q:
    """NF/CT-e histórico/XML: produção + cStat 100."""
    return (q_excluir_homologacao_historica_entrada()) & (Q(cstat='100') | Q(cstat__iexact='100'))


def filtrar_queryset_precificacao_historica_saida(qs):
    return qs.filter(q_historico_autorizado_producao()).filter(cancelada=False)


def filtrar_queryset_precificacao_historica_entrada(qs):
    return qs.filter(q_excluir_homologacao_historica_entrada()).filter(Q(cstat='100') | Q(cstat__iexact='100'))


def filtrar_queryset_precificacao_cte(qs):
    return qs.filter(q_excluir_homologacao_cte()).filter(cancelado=False).filter(
        Q(cstat='100') | Q(cstat__iexact='100'),
    )


def metadados_classificacao_dfe(
    documento: Any,
    *,
    conferencia_status: str | None = None,
    incluir_canceladas: bool = False,
) -> dict[str, Any]:
    """Metadados para API/UI: categoria, flags fiscais e tokens de badge."""
    homolog = eh_documento_homologacao(documento)
    cat = categoria_documento(documento)
    apura = pode_entrar_apuracao(documento, incluir_canceladas=incluir_canceladas)
    prec = pode_alimentar_precificacao(documento)
    oper = pode_gerar_efeito_operacional(documento)
    prod = eh_documento_producao(documento)
    autorizado = eh_documento_autorizado(documento, incluir_canceladas=incluir_canceladas)

    badges: list[str] = []
    if cat == CATEGORIA_BASE_DFE_IMPORTADA:
        badges.append('base_importada')
        badges.append('sem_efeito_operacional_automatico')
    elif cat == CATEGORIA_OPERACIONAL:
        badges.append('operacional')
    if homolog:
        badges.extend(['homologacao', 'sem_valor_fiscal', 'fora_apuracao'])
    elif prod and autorizado:
        badges.append('producao')
        if apura:
            badges.extend(['apura', 'alimenta_precificacao'])
        else:
            badges.append('fora_apuracao')
    elif not autorizado:
        badges.append('fora_apuracao')
    if prec and 'alimenta_precificacao' not in badges:
        badges.append('alimenta_precificacao')
    if getattr(documento, 'cancelada', False) or getattr(documento, 'cancelado', False):
        badges.append('cancelada')

    conf_st = (conferencia_status or '').strip().upper()
    if hasattr(documento, 'status_conferencia') and not conf_st:
        conf_st = (getattr(documento, 'status_conferencia', None) or '').strip().upper()
    if conf_st in ESTADOS_CONFERENCIA_BASE_IMPORTADA:
        if conf_st in ('CONFERIDA', 'CONFERIDO'):
            badges.append('conferida')
        elif conf_st in ('PREPARADA', 'PREPARADO'):
            badges.append('preparada')
        elif conf_st == 'DIVERGENTE':
            badges.append('divergente')
        elif conf_st in ('IGNORADA', 'IGNORADO'):
            badges.append('ignorada')
        elif conf_st == 'PROCESSADO':
            badges.append('importada')
        else:
            badges.append('importada')
    if isinstance(documento, CTeHistoricoImportado) and getattr(documento, 'apto_operacional', False):
        if 'conferida' not in badges:
            badges.append('conferida')

    # dedupe preservando ordem
    seen: set[str] = set()
    badges_unique = []
    for b in badges:
        if b not in seen:
            seen.add(b)
            badges_unique.append(b)

    return {
        'categoria': cat,
        'homologacao': homolog,
        'producao': prod and not homolog,
        'autorizado': autorizado,
        'tem_valor_fiscal': tem_valor_fiscal(documento),
        'pode_entrar_apuracao': apura,
        'pode_alimentar_precificacao': prec,
        'pode_gerar_efeito_operacional': oper,
        'conferencia_status': conf_st or None,
        'badges': badges_unique,
    }
