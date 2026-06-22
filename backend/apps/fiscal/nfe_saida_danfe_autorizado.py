"""DANFE final NF-e Saída autorizada (produção/homologação)."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import NFeSaida


def gerar_danfe_autorizado_nfe_saida(nfe_saida: NFeSaida) -> tuple[bytes, dict[str, Any]]:
    """Gera DANFE final a partir do XML autorizado/protocolado — sem alterar a NF-e."""
    from apps.fiscal.danfe_render import DanfeBfrRenderError
    from apps.fiscal.nfe_integracao.danfe_brazil_fiscal_report import (
        DanfeBfrError,
        DanfeBfrIndisponivelError,
        brazil_fiscal_report_disponivel,
        gerar_danfe_bfr_autorizada,
    )
    from apps.fiscal.nfe_saida_bloqueio import pode_visualizar_danfe_xml_autorizado

    if not pode_visualizar_danfe_xml_autorizado(nfe_saida):
        raise DanfeBfrRenderError(
            'DANFE autorizado disponível apenas após autorização SEFAZ ou cancelamento com XML local.',
            nfe_saida_id=nfe_saida.pk,
            erro_tipo='NfeNaoAutorizada',
        )
    if not brazil_fiscal_report_disponivel():
        raise DanfeBfrRenderError(
            'Renderizador oficial BFR (BrazilFiscalReport) indisponível neste ambiente.',
            nfe_saida_id=nfe_saida.pk,
        )
    try:
        pdf, meta = gerar_danfe_bfr_autorizada(nfe_saida)
    except (DanfeBfrError, DanfeBfrIndisponivelError) as exc:
        from apps.fiscal.nfe_saida_bloqueio import nf_autorizada_homologacao, nf_autorizada_producao

        ambiente = '1' if nf_autorizada_producao(nfe_saida) else '2'
        if nf_autorizada_homologacao(nfe_saida):
            ambiente = '2'
        raise DanfeBfrRenderError(
            str(exc),
            nfe_saida_id=nfe_saida.pk,
            numero=nfe_saida.numero,
            status=nfe_saida.status,
            ambiente=ambiente,
            erro_tipo=type(exc).__name__,
        ) from exc
    if not pdf or meta.get('bloqueado'):
        raise DanfeBfrRenderError(
            'Não foi possível gerar o DANFE a partir do XML autorizado.',
            nfe_saida_id=nfe_saida.pk,
        )
    return pdf, meta
