"""Higienização segura de dados de teste/dev (ERP 4.0.13.5.2)."""

from __future__ import annotations

import os
from typing import Any

from django.conf import settings

from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor, salvar_relatorio_auditoria
from apps.fiscal.limpeza_cursor.limpeza import LimpezaCursorError, executar_limpeza_cursor

CONFIRMACAO_TOKEN = 'LIMPAR_DADOS_TESTE_NEXUS'

_AMBIENTES_PERMITIDOS = frozenset(
    {
        'local',
        'development',
        'dev',
        'homologacao',
        'homologação',
        'homolog',
        'test',
        'testing',
    },
)
_AMBIENTES_BLOQUEADOS = frozenset({'production', 'producao', 'prod'})


class LimpezaDadosTesteError(Exception):
    pass


def ambiente_atual() -> str:
    return (
        os.environ.get('NEXUS_ENV')
        or os.environ.get('DJANGO_ENV')
        or os.environ.get('ENVIRONMENT')
        or ''
    ).strip().lower()


def ambiente_permite_limpeza_teste() -> bool:
    env = ambiente_atual()
    if env in _AMBIENTES_BLOQUEADOS:
        return False
    if env in _AMBIENTES_PERMITIDOS:
        return True
    if not env:
        return bool(settings.DEBUG)
    return bool(settings.DEBUG) and env not in _AMBIENTES_BLOQUEADOS


def verificar_ambiente_seguro() -> None:
    if not ambiente_permite_limpeza_teste():
        raise LimpezaDadosTesteError('Limpeza de dados de teste bloqueada em produção.')


def executar_dry_run() -> dict[str, Any]:
    return executar_auditoria_limpeza_cursor()


def executar_limpeza_confirmada(relatorio: dict[str, Any]) -> dict[str, int]:
    verificar_ambiente_seguro()
    try:
        return executar_limpeza_cursor(relatorio)
    except LimpezaCursorError as exc:
        raise LimpezaDadosTesteError(str(exc)) from exc


def formatar_linha_candidato(identificador: str, motivos: list[str] | None, motivo_unico: str | None = None) -> str:
    if motivos:
        motivo_txt = '; '.join(motivos)
    elif motivo_unico:
        motivo_txt = motivo_unico
    else:
        motivo_txt = 'critério de teste'
    return f'- {identificador} — motivo: {motivo_txt}'


def imprimir_relatorio_dry_run(relatorio: dict[str, Any], writer) -> None:
    res = relatorio.get('resumo', {})
    writer('[DRY-RUN] Resumo:')
    writer(f"  Pedidos candidatos: {res.get('pedidos_candidatos', 0)}")
    writer(f"  Clientes candidatos: {res.get('clientes_candidatos', 0)}")
    writer(f"  Produtos candidatos: {res.get('produtos_candidatos', 0)}")
    writer(f"  NF-e candidatas: {res.get('nfe_candidatas', 0)}")
    writer(f"  Faturamentos candidatos: {res.get('faturamentos_candidatos', 0)}")
    writer(f"  NF-e preservadas: {res.get('preservados_nfe', 0)}")

    writer('')
    writer('[DRY-RUN] Pedidos de venda candidatos:')
    for item in relatorio.get('pedidos_candidatos', []):
        writer(formatar_linha_candidato(item.get('numero', f"id={item.get('id')}"), item.get('motivos')))

    writer('')
    writer('[DRY-RUN] Clientes candidatos:')
    for item in relatorio.get('clientes_candidatos', []):
        writer(formatar_linha_candidato(item.get('razao_social', f"id={item.get('id')}"), item.get('motivos')))

    writer('')
    writer('[DRY-RUN] Produtos candidatos:')
    for item in relatorio.get('produtos_candidatos', []):
        ident = item.get('descricao') or item.get('codigo') or f"id={item.get('id')}"
        writer(formatar_linha_candidato(ident, item.get('motivos')))

    writer('')
    writer('[DRY-RUN] NF-e candidatas (não autorizadas / teste):')
    for item in relatorio.get('nfe_candidatas', []):
        writer(formatar_linha_candidato(item.get('numero', f"id={item.get('id')}"), item.get('motivos')))

    writer('')
    writer('[DRY-RUN] Faturamentos candidatos:')
    for item in relatorio.get('faturamentos_candidatos', []):
        writer(
            formatar_linha_candidato(
                item.get('numero_faturamento', f"id={item.get('id')}"),
                item.get('motivos'),
            ),
        )

    writer('')
    writer('Nenhum registro foi apagado (dry-run).')


def salvar_relatorio_dry_run(relatorio: dict[str, Any]) -> tuple[Any, Any]:
    return salvar_relatorio_auditoria(relatorio)
