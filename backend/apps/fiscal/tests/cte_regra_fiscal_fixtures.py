"""Helpers de regra fiscal FRETE_TRANSPORTE para testes de CT-e."""

from __future__ import annotations

from apps.regras_fiscais.models import RegraFiscalEntrada

CFOP_CTE_TESTE = '5353'


def garantir_regra_frete_cte(
    *,
    cfop: str = CFOP_CTE_TESTE,
    severidade: str = RegraFiscalEntrada.Severidade.INFORMATIVO,
    nome: str | None = None,
) -> RegraFiscalEntrada:
    cfop_n = ''.join(c for c in (cfop or '') if c.isdigit())[:4]
    regra, _ = RegraFiscalEntrada.objects.update_or_create(
        nome=nome or f'Frete CT-e {cfop_n}',
        defaults={
            'ativo': True,
            'prioridade': 10,
            'cfop': cfop_n,
            'cfop_origem': cfop_n,
            'cfop_entrada': cfop_n,
            'tipo_operacao_fiscal': RegraFiscalEntrada.TipoOperacaoFiscal.FRETE_TRANSPORTE,
            'movimenta_estoque': False,
            'severidade': severidade,
            'mensagem_padrao': f'Regra frete CFOP {cfop_n}',
        },
    )
    return regra
