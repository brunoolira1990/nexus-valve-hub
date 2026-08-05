"""Match de RegraFiscalEntrada (tipo FRETE_TRANSPORTE) para CT-e importado."""

from __future__ import annotations

from typing import Any

from apps.fiscal.models import CTeHistoricoImportado
from apps.regras_fiscais.entrada_fiscal import (
    ContextoFiscalEntrada,
    carregar_regras_fiscais_entrada_ativas,
    encontrar_regra_fiscal_entrada,
)
from apps.regras_fiscais.models import RegraFiscalEntrada

MSG_SEM_REGRA_CTE = (
    'Não há regra fiscal de entrada do tipo «Frete / transporte (CT-e)» '
    'para o CFOP deste documento. Cadastre a configuração em Regras Fiscais → Entrada '
    '(CFOP origem = CFOP do CT-e, tipo Frete/transporte, sem NCM, movimenta estoque = Não).'
)
MSG_REGRA_BLOQUEIO = 'A regra fiscal de frete/transporte está com severidade BLOQUEIO.'


def avaliar_regra_fiscal_cte(cte: CTeHistoricoImportado) -> dict[str, Any]:
    """Avalia regra fiscal para o CFOP do CT-e (tomador)."""
    cfop = ''.join(c for c in (cte.cfop or '') if c.isdigit())[:4]
    ctx = ContextoFiscalEntrada(
        uf_origem=(cte.uf_inicio or '').strip().upper()[:2],
        uf_destino=(cte.uf_fim or '').strip().upper()[:2],
        fornecedor_id=None,
        tipo_operacao_fiscal=RegraFiscalEntrada.TipoOperacaoFiscal.FRETE_TRANSPORTE,
    )
    regras = carregar_regras_fiscais_entrada_ativas()
    pool = [
        r
        for r in regras
        if r.tipo_operacao_fiscal == RegraFiscalEntrada.TipoOperacaoFiscal.FRETE_TRANSPORTE
    ]

    if not cfop:
        return {
            'status': 'SEM_REGRA',
            'mensagem': 'CT-e sem CFOP no XML — não é possível casar regra fiscal de frete.',
            'cfop_cte': '',
            'regra_id': None,
            'regra_nome': '',
            'cfop_entrada': '',
            'severidade': None,
            'movimenta_estoque': False,
            'pode_conferir': False,
            'pode_gerar_financeiro': False,
        }

    match = encontrar_regra_fiscal_entrada(
        pool,
        cfop_nf=cfop,
        ncm_nf='',
        contexto=ctx,
        produto_id=None,
        trib=None,
    )
    if not match:
        return {
            'status': 'SEM_REGRA',
            'mensagem': MSG_SEM_REGRA_CTE,
            'cfop_cte': cfop,
            'regra_id': None,
            'regra_nome': '',
            'cfop_entrada': '',
            'severidade': None,
            'movimenta_estoque': False,
            'pode_conferir': False,
            'pode_gerar_financeiro': False,
        }

    regra, esp = match
    if regra.severidade == RegraFiscalEntrada.Severidade.BLOQUEIO:
        status = 'BLOQUEADO'
        pode = False
        msg = MSG_REGRA_BLOQUEIO
    elif regra.severidade == RegraFiscalEntrada.Severidade.ALERTA:
        status = 'ALERTA'
        pode = True
        msg = (regra.mensagem_padrao or '').strip() or 'Regra de frete com alerta.'
    else:
        status = 'OK'
        pode = True
        msg = (regra.mensagem_padrao or '').strip() or f'Regra «{regra.nome}» aplicada.'

    return {
        'status': status,
        'mensagem': msg,
        'cfop_cte': cfop,
        'regra_id': regra.pk,
        'regra_nome': regra.nome,
        'cfop_entrada': (regra.cfop_entrada or '').strip() or cfop,
        'severidade': regra.severidade,
        'movimenta_estoque': bool(regra.movimenta_estoque),
        'especificidade_score': esp.score,
        'especificidade_motivos': list(esp.motivos),
        'pode_conferir': pode,
        'pode_gerar_financeiro': pode,
    }


def exigir_regra_fiscal_cte_ok(cte: CTeHistoricoImportado) -> dict[str, Any]:
    """Retorna avaliação; levanta ValueError se não pode seguir (conferir/CP)."""
    av = avaliar_regra_fiscal_cte(cte)
    if not av.get('pode_conferir'):
        raise ValueError(av.get('mensagem') or MSG_SEM_REGRA_CTE)
    return av
