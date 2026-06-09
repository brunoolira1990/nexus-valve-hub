"""Preparação segura para limpeza de dados operacionais de teste — ERP 4.0.14.8/4.0.14.9."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from apps.cadastros.models import Colaborador, Empresa
from apps.comercial.models import FaturamentoPedidoVenda, PedidoCompra, PedidoVenda, Proposta
from apps.core.limpeza_dados_teste import verificar_ambiente_seguro
from apps.financeiro.models import (
    BaixaFinanceira,
    CategoriaFinanceira,
    CentroCusto,
    ContaFinanceira,
    CreditoFinanceiro,
    CreditoFinanceiroEvento,
    FinanceiroEvento,
    ParcelaFinanceira,
    TituloFinanceiro,
)
from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor
from apps.fiscal.limpeza_cursor.criterios import nfe_deve_preservar
from apps.fiscal.models import AtendimentoEstoque, EstoqueCorrida, NFeEntrada, NFeEntradaConferencia, NFeSaida
from apps.produtos.models import FamiliaProduto, Ncm, Produto
from apps.regras_fiscais.models import RegraFiscal, RegraFiscalEntrada, RegraFiscalSaida

User = get_user_model()
CONFIRMACAO_TOKEN = 'APAGAR_DADOS_TESTE'
MSG_PRODUTOS_BLOQUEIO = 'Produtos não podem ser removidos na limpeza de pré-produção.'
MSG_AVISO_EXECUCAO = (
    'Esta ação apagará dados operacionais de teste e não poderá ser desfeita sem backup.'
)


class PreparacaoLimpezaError(Exception):
    pass


def _contar_preservados() -> dict[str, int]:
    return {
        'produtos': Produto.objects.count(),
        'familias_figuras': FamiliaProduto.objects.count(),
        'ncm': Ncm.objects.count(),
        'regras_fiscais': RegraFiscal.objects.count(),
        'regras_fiscais_saida': RegraFiscalSaida.objects.count(),
        'regras_fiscais_entrada': RegraFiscalEntrada.objects.count(),
        'empresa_emitente': Empresa.objects.count(),
        'colaboradores': Colaborador.objects.count(),
        'usuarios': User.objects.count(),
        'grupos_perfis': Group.objects.count(),
        'categorias_financeiras': CategoriaFinanceira.objects.count(),
        'centros_custo': CentroCusto.objects.count(),
        'contas_caixas': ContaFinanceira.objects.count(),
    }


def _contar_candidatos_financeiro() -> dict[str, int]:
    return {
        'contas_receber': TituloFinanceiro.objects.filter(tipo=TituloFinanceiro.Tipo.RECEBER).count(),
        'contas_pagar': TituloFinanceiro.objects.filter(tipo=TituloFinanceiro.Tipo.PAGAR).count(),
        'baixas': BaixaFinanceira.objects.count(),
        'creditos': CreditoFinanceiro.objects.count(),
        'parcelas': ParcelaFinanceira.objects.count(),
        'eventos_financeiros': FinanceiroEvento.objects.count(),
    }


def _contar_candidatos_estoque() -> dict[str, int]:
    return {
        'atendimentos_estoque': AtendimentoEstoque.objects.count(),
        'estoques_corrida': EstoqueCorrida.objects.count(),
        'conferencias_nfe_entrada': NFeEntradaConferencia.objects.count(),
    }


def _documentos_possivelmente_reais() -> list[str]:
    bloqueios: list[str] = []
    for nf in NFeSaida.objects.all().iterator():
        preservar, motivo = nfe_deve_preservar(nf)
        if preservar and motivo not in ('autorizada_homologacao',):
            bloqueios.append(f'NF-e Saída #{nf.pk} ({motivo})')
    return bloqueios[:50]


def _produtos_candidatos_auditoria(base: dict[str, Any]) -> list[dict]:
    return list(base.get('produtos_candidatos') or [])


def validar_execucao_limpeza_permitida(
    relatorio_dry_run: dict[str, Any],
    prontidao: dict[str, Any] | None,
    *,
    backup_confirmado: bool,
    confirmacao: str,
    executar: bool = True,
) -> tuple[bool, str | None]:
    if not executar:
        return True, None

    if confirmacao != CONFIRMACAO_TOKEN:
        return False, f'Confirmação inválida. Use --confirmar {CONFIRMACAO_TOKEN}'

    if not backup_confirmado:
        return False, 'Faça backup do banco e arquivos antes de executar a limpeza.'

    if prontidao and prontidao.get('criticos'):
        return False, 'Prontidão com erros críticos. Corrija antes da limpeza.'

    prod_cand = relatorio_dry_run.get('produtos_protegidos', {}).get('candidatos_auditoria', 0)
    if prod_cand:
        return False, MSG_PRODUTOS_BLOQUEIO

    bloqueios = relatorio_dry_run.get('bloqueios', {}).get('documentos_possivelmente_reais') or []
    if bloqueios:
        return False, 'Foram encontrados documentos que podem ser reais. A limpeza foi bloqueada para revisão.'

    return True, None


def executar_dry_run_limpeza_producao() -> dict[str, Any]:
    base = executar_auditoria_limpeza_cursor()
    preservados = _contar_preservados()
    financeiro = _contar_candidatos_financeiro()
    estoque = _contar_candidatos_estoque()
    bloqueios_reais = _documentos_possivelmente_reais()
    produtos_candidatos = _produtos_candidatos_auditoria(base)

    candidatos = {
        'nfe_saida': len(base.get('nfe_candidatas') or []),
        'pedidos_venda': len(base.get('pedidos_candidatos') or []),
        'faturamentos': len(base.get('faturamentos_candidatos') or []),
        'nfe_entrada': NFeEntrada.objects.count(),
        'pedidos_compra': PedidoCompra.objects.count(),
        'propostas': Proposta.objects.count(),
        'pedidos_venda_total': PedidoVenda.objects.count(),
        'faturamentos_total': FaturamentoPedidoVenda.objects.count(),
        **financeiro,
        **estoque,
    }

    bloqueios: dict[str, Any] = {
        'documentos_possivelmente_reais': bloqueios_reais,
        'produtos_exclusao_automatica': True,
        'produtos_candidatos_bloqueiam_execucao': len(produtos_candidatos) > 0,
    }
    if produtos_candidatos:
        bloqueios['produtos_candidatos_motivo'] = MSG_PRODUTOS_BLOQUEIO

    return {
        'gerado_em': datetime.now().isoformat(),
        'modo': 'dry_run',
        'preservados': preservados,
        'candidatos_limpeza': candidatos,
        'produtos_protegidos': {
            'total_preservados': preservados['produtos'],
            'candidatos_auditoria': len(produtos_candidatos),
            'nunca_removidos': True,
        },
        'bloqueios': bloqueios,
        'auditoria_cursor': base,
        'nenhum_dado_alterado': True,
    }


def _limpar_financeiro_operacional() -> dict[str, int]:
    removidos = {
        'eventos_credito': CreditoFinanceiroEvento.objects.all().delete()[0],
        'eventos_financeiros': FinanceiroEvento.objects.all().delete()[0],
        'baixas': BaixaFinanceira.objects.all().delete()[0],
        'creditos': CreditoFinanceiro.objects.all().delete()[0],
        'parcelas': ParcelaFinanceira.objects.all().delete()[0],
        'titulos': TituloFinanceiro.objects.all().delete()[0],
    }
    return removidos


@transaction.atomic
def executar_limpeza_producao(
    relatorio: dict[str, Any],
    *,
    prontidao: dict[str, Any] | None = None,
) -> dict[str, int]:
    verificar_ambiente_seguro()

    permitido, motivo = validar_execucao_limpeza_permitida(
        relatorio,
        prontidao,
        backup_confirmado=True,
        confirmacao=CONFIRMACAO_TOKEN,
    )
    if not permitido:
        raise PreparacaoLimpezaError(motivo or 'Limpeza bloqueada.')

    from apps.core.limpeza_dados_teste import executar_limpeza_confirmada

    removidos: dict[str, int] = {}
    removidos.update(_limpar_financeiro_operacional())
    cursor_removidos = executar_limpeza_confirmada(relatorio.get('auditoria_cursor') or {})
    removidos.update(cursor_removidos)
    return removidos
