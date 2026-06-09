"""Export/backup antes da limpeza de dados Cursor."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.fiscal.limpeza_cursor.auditoria import executar_auditoria_limpeza_cursor


def exportar_backup_limpeza_cursor(relatorio: dict[str, Any] | None = None) -> Path:
    rel = relatorio or executar_auditoria_limpeza_cursor()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = Path(settings.MEDIA_ROOT) / 'backups' / 'limpeza_cursor' / ts
    base.mkdir(parents=True, exist_ok=True)

    mapas = {
        'empresas_candidatas.csv': rel.get('empresas_candidatas', []),
        'clientes_candidatos.csv': rel.get('clientes_candidatos', []),
        'pedidos_candidatos.csv': rel.get('pedidos_candidatos', []),
        'faturamentos_candidatos.csv': rel.get('faturamentos_candidatos', []),
        'nfe_candidatas.csv': rel.get('nfe_candidatas', []),
        'produtos_revisao.csv': rel.get('produtos_revisao', []),
    }

    for nome, rows in mapas.items():
        if not rows:
            continue
        path = base / nome
        keys = sorted({k for r in rows for k in r.keys()})
        with path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=keys, extrasaction='ignore')
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, '') for k in keys})

    resumo_path = base / 'resumo.json'
    resumo_path.write_text(
        json.dumps({'gerado_em': rel.get('gerado_em'), 'resumo': rel.get('resumo'), 'modo': 'backup'}, indent=2),
        encoding='utf-8',
    )
    (base / 'auditoria_completa.json').write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding='utf-8')
    return base
