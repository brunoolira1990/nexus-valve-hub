"""ERP 4.0.13.6.13A — DANFE oficial exclusivamente via BrazilFiscalReport (BFR)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.fiscal.danfe_bfr_log import log_danfe_bfr_erro, log_danfe_fallback_bloqueado, novo_trace_id
from apps.fiscal.models import NFeSaida

logger = logging.getLogger(__name__)

RENDERER_OFICIAL = 'BFR'
RENDER_ENGINES_OFICIAIS = frozenset(
    {
        'brazil_fiscal_report',
        'brazil_fiscal_report_legacy',
    },
)

MSG_BFR_FALHA_USUARIO = (
    'Não foi possível gerar o DANFE pelo renderizador oficial BFR. '
    'O fallback HTML foi bloqueado para evitar layout divergente.'
)
MSG_BFR_INDISPONIVEL = (
    'Renderizador oficial BFR (BrazilFiscalReport) indisponível neste ambiente. '
    'Instale a dependência ou contate o suporte.'
)


class DanfeBfrRenderError(Exception):
    """Falha no renderizador oficial BFR; fallback HTML/ReportLab bloqueado."""

    def __init__(
        self,
        message: str,
        *,
        nfe_saida_id: int | None = None,
        numero: str | None = None,
        status: str | None = None,
        ambiente: str | None = None,
        erro_tipo: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.nfe_saida_id = nfe_saida_id
        self.numero = numero
        self.status = status
        self.ambiente = ambiente
        self.erro_tipo = erro_tipo or type(self).__name__
        self.trace_id = trace_id or novo_trace_id()


def renderer_oficial() -> str:
    return getattr(settings, 'DANFE_RENDERER_OFICIAL', RENDERER_OFICIAL)


def html_fallback_permitido() -> bool:
    return bool(getattr(settings, 'DANFE_ALLOW_HTML_FALLBACK', False))


def html_diagnostico_permitido() -> bool:
    return bool(getattr(settings, 'DANFE_ALLOW_HTML_DIAGNOSTIC', False)) and bool(settings.DEBUG)


def emissao_bloqueada_se_bfr_falhar() -> bool:
    return bool(getattr(settings, 'DANFE_BLOCK_EMISSION_IF_BFR_FAILS', True))


def render_engine_oficial(meta: dict[str, Any] | None) -> bool:
    engine = (meta or {}).get('render_engine') or ''
    return engine in RENDER_ENGINES_OFICIAIS


def _ambiente_log_para_nfe(nf: NFeSaida) -> str:
    """tpAmb para logs BFR — produção=1, homologação=2."""
    from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_producao

    if nf_autorizada_producao(nf):
        return '1'
    if (nf.ambiente_emissao or '').strip() == NFeSaida.AmbienteEmissao.PRODUCAO:
        return '1'
    return '2'


def _meta_erro_bfr(
    nf: NFeSaida,
    *,
    mensagens: list[str],
    erro_tipo: str,
    trace_id: str,
) -> dict[str, Any]:
    return {
        'nfe_saida_id': nf.pk,
        'numero': nf.numero,
        'status': nf.status,
        'preview': True,
        'bloqueado': True,
        'conferencia': True,
        'modelo': '55',
        'render_engine': 'brazil_fiscal_report_erro',
        'danfe_origem': 'bfr_erro',
        'danfe_renderer_label': 'DANFE — BFR (falha)',
        'renderer_oficial': renderer_oficial(),
        'mensagens': mensagens,
        'trace_id': trace_id,
        'filename': f'danfe-conferencia-nfe-{nf.pk}-erro.pdf',
        'content_type': 'application/pdf',
    }


def _levantar_erro_bfr(
    nf: NFeSaida,
    exc: BaseException,
    *,
    ambiente: str | None = None,
) -> None:
    amb_log = ambiente if ambiente in ('1', '2') else _ambiente_log_para_nfe(nf)
    trace_id = log_danfe_bfr_erro(
        nfe_id=nf.pk,
        numero=nf.numero,
        status=nf.status,
        ambiente=amb_log,
        erro_tipo=type(exc).__name__,
        erro_mensagem=str(exc).strip() or type(exc).__name__,
    )
    if not html_fallback_permitido():
        log_danfe_fallback_bloqueado(nfe_id=nf.pk, motivo=str(exc), trace_id=trace_id)
    raise DanfeBfrRenderError(
        MSG_BFR_FALHA_USUARIO,
        nfe_saida_id=nf.pk,
        numero=nf.numero,
        status=nf.status,
        ambiente=amb_log,
        erro_tipo=type(exc).__name__,
        trace_id=trace_id,
    ) from exc


def gerar_danfe_bfr_oficial(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    """Gera PDF DANFE via BFR (único renderer oficial)."""
    from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
        DanfeBfrError,
        DanfeBfrIndisponivelError,
        brazil_fiscal_report_disponivel,
        gerar_danfe_bfr_de_nfe_saida_preview,
    )

    nf = nfe_saida
    amb_log = _ambiente_log_para_nfe(nf)
    if not brazil_fiscal_report_disponivel():
        exc = DanfeBfrIndisponivelError(MSG_BFR_INDISPONIVEL)
        trace_id = log_danfe_bfr_erro(
            nfe_id=nf.pk,
            numero=nf.numero,
            status=nf.status,
            ambiente=amb_log,
            erro_tipo=type(exc).__name__,
            erro_mensagem=str(exc),
        )
        log_danfe_fallback_bloqueado(
            nfe_id=nf.pk,
            motivo='BrazilFiscalReport indisponível',
            trace_id=trace_id,
        )
        raise DanfeBfrRenderError(
            MSG_BFR_INDISPONIVEL,
            nfe_saida_id=nf.pk,
            numero=nf.numero,
            status=nf.status,
            ambiente=amb_log,
            erro_tipo=type(exc).__name__,
            trace_id=trace_id,
        ) from exc

    try:
        pdf, meta = gerar_danfe_bfr_de_nfe_saida_preview(nf)
    except DanfeBfrIndisponivelError as exc:
        _levantar_erro_bfr(nf, exc)
        raise  # pragma: no cover
    except DanfeBfrError as exc:
        _levantar_erro_bfr(nf, exc)
        raise  # pragma: no cover
    except Exception as exc:
        _levantar_erro_bfr(nf, exc)
        raise  # pragma: no cover

    if meta.get('bloqueado'):
        msg = (meta.get('mensagens') or ['DANFE bloqueado pelo BFR.'])[0]
        trace_id = log_danfe_bfr_erro(
            nfe_id=nf.pk,
            numero=nf.numero,
            status=nf.status,
            ambiente=amb_log,
            erro_tipo='DanfeBfrBloqueado',
            erro_mensagem=msg,
        )
        log_danfe_fallback_bloqueado(nfe_id=nf.pk, motivo=msg, trace_id=trace_id)
        raise DanfeBfrRenderError(
            MSG_BFR_FALHA_USUARIO,
            nfe_saida_id=nf.pk,
            numero=nf.numero,
            status=nf.status,
            ambiente=amb_log,
            erro_tipo='DanfeBfrBloqueado',
            trace_id=trace_id,
        )

    if not pdf or len(pdf) < 100:
        exc = ValueError('PDF vazio retornado pelo BFR.')
        _levantar_erro_bfr(nf, exc)
        raise  # pragma: no cover

    engine = meta.get('render_engine') or ''
    if engine not in RENDER_ENGINES_OFICIAIS:
        exc = ValueError(f'Render engine não oficial: {engine}')
        _levantar_erro_bfr(nf, exc)
        raise  # pragma: no cover

    meta.setdefault('filename', f'danfe-conferencia-bfr-nfe-{nf.pk}.pdf')
    meta['conferencia'] = True
    meta['preview'] = True
    meta['renderer_oficial'] = renderer_oficial()
    meta.setdefault('danfe_renderer_label', 'DANFE — Renderer oficial BFR')
    if getattr(settings, 'DANFE_LOG_RENDERER', True):
        logger.info(
            'DANFE BFR ok nfe_id=%s engine=%s origem=%s bytes=%s',
            nf.pk,
            meta.get('render_engine'),
            meta.get('danfe_origem'),
            len(pdf),
        )
    return pdf, meta


def validar_danfe_bfr_para_emissao(nfe_saida: NFeSaida) -> None:
    """Levanta DanfeBfrRenderError se o DANFE oficial não puder ser gerado."""
    if not emissao_bloqueada_se_bfr_falhar():
        return
    pdf, meta = gerar_danfe_bfr_oficial(nfe_saida)
    if not render_engine_oficial(meta) or not pdf:
        raise DanfeBfrRenderError(MSG_BFR_FALHA_USUARIO, nfe_saida_id=nfe_saida.pk)


def render_danfe_conferencia_pdf(
    dados: dict[str, Any],
    *,
    nfe_saida_id: int | None = None,
    **_kwargs: Any,
) -> tuple[bytes, dict[str, Any]]:
    """Compatibilidade: delega ao BFR usando o pk da NF-e."""
    if dados.get('bloqueado'):
        pk = dados.get('nfe_saida_id') or nfe_saida_id
        raise DanfeBfrRenderError(
            MSG_BFR_FALHA_USUARIO,
            nfe_saida_id=pk,
            erro_tipo='DadosBloqueados',
        )
    pk = dados.get('nfe_saida_id') or nfe_saida_id
    if not pk:
        raise DanfeBfrRenderError(MSG_BFR_FALHA_USUARIO, erro_tipo='SemNfeId')
    nf = NFeSaida.objects.get(pk=pk)
    return gerar_danfe_bfr_oficial(nf)


def gerar_danfe_modelo55_conferencia_pdf(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    return gerar_danfe_bfr_oficial(nfe_saida)
