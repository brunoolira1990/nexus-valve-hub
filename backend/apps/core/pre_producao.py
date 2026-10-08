"""Relatório de pré-produção — ERP 4.0.14.9 (somente leitura)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.core.limpeza_dados_teste import ambiente_atual
from apps.core.preparacao_limpeza_producao import (
    CONFIRMACAO_TOKEN,
    executar_dry_run_limpeza_producao,
    validar_execucao_limpeza_permitida,
)
from apps.core.prontidao_producao import executar_verificacao_prontidao

_CHAVES_SENSIVEIS = re.compile(
    r'(senha|password|token|certificado|secret|api_key|private_key)',
    re.I,
)


def _sanitizar(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _CHAVES_SENSIVEIS.search(str(k)):
                continue
            out[k] = _sanitizar(v)
        return out
    if isinstance(obj, list):
        return [_sanitizar(x) for x in obj]
    return obj


def gerar_relatorio_pre_producao(*, usuario_executor: str = '') -> dict[str, Any]:
    prontidao = executar_verificacao_prontidao()
    dry_run = executar_dry_run_limpeza_producao()
    pode_limpar, motivo_bloqueio_limpeza = validar_execucao_limpeza_permitida(
        dry_run,
        prontidao,
        backup_confirmado=False,
        confirmacao='',
    )

    relatorio = {
        'versao': 'ERP 4.0.14.10.1',
        'gerado_em': datetime.now().isoformat(),
        'ambiente': ambiente_atual() or ('debug' if settings.DEBUG else 'nao_informado'),
        'debug': settings.DEBUG,
        'usuario_executor': (usuario_executor or '').strip() or 'sistema',
        'nenhum_dado_alterado': True,
        'prontidao': {
            'pronto': prontidao.get('pronto'),
            'criticos': prontidao.get('criticos', []),
            'avisos': prontidao.get('avisos', []),
            'ok': prontidao.get('ok', []),
            'preservados': prontidao.get('preservados', {}),
            'checklist_producao': prontidao.get('checklist_producao', []),
            'fiscal': prontidao.get('fiscal', {}),
        },
        'dry_run_limpeza': {
            'preservados': dry_run.get('preservados', {}),
            'candidatos_limpeza': dry_run.get('candidatos_limpeza', {}),
            'bloqueios': dry_run.get('bloqueios', {}),
            'produtos_protegidos': dry_run.get('produtos_protegidos', {}),
        },
        'execucao_limpeza': {
            'permitida_agora': pode_limpar,
            'motivo_bloqueio': motivo_bloqueio_limpeza,
            'comando_sugerido': (
                f'python manage.py preparar_limpeza_producao --executar '
                f'--backup-confirmado --confirmar {CONFIRMACAO_TOKEN}'
            ),
            'aviso_execucao': (
                'Esta ação apagará dados operacionais de teste e não poderá ser desfeita sem backup.'
            ),
        },
        'pendencias': _montar_pendencias(prontidao, dry_run, pode_limpar, motivo_bloqueio_limpeza),
    }
    return _sanitizar(relatorio)


def _montar_pendencias(
    prontidao: dict,
    dry_run: dict,
    pode_limpar: bool,
    motivo: str | None,
) -> list[str]:
    pendencias: list[str] = []
    if prontidao.get('criticos'):
        pendencias.append('Corrigir erros críticos da prontidão antes de produção.')
    if not settings.DEBUG:
        pendencias.append('Confirmar DEBUG=False e variáveis de ambiente de produção.')
    else:
        pendencias.append('Ambiente DEBUG=True — conferir antes de produção.')
    if dry_run.get('bloqueios', {}).get('documentos_possivelmente_reais'):
        pendencias.append('Revisar documentos possivelmente reais antes da limpeza.')
    if not pode_limpar and motivo:
        pendencias.append(motivo)
    if not pendencias:
        pendencias.append('Nenhuma pendência bloqueante identificada no dry-run.')
    return pendencias


def _reports_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        d = base_dir / 'reports' if base_dir.name != 'reports' else base_dir
        d.mkdir(parents=True, exist_ok=True)
        return d
    base = Path(settings.BASE_DIR)
    repo = base.parent
    if (repo / 'docker-compose.yml').is_file() or (repo / 'frontend').is_dir():
        d = repo / 'reports'
    else:
        d = base / 'reports'
    d.mkdir(parents=True, exist_ok=True)
    return d


def salvar_relatorio_pre_producao(relatorio: dict[str, Any], *, base_dir: Path | None = None) -> Path:
    reports_dir = _reports_dir(base_dir)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = reports_dir / f'pre_producao_{ts}.json'
    path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')
    return path
