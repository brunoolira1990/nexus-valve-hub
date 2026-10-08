"""Auditoria dry-run de dados Cursor/teste."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import FaturamentoPedidoVenda, PedidoVenda
from apps.fiscal.limpeza_cursor.criterios import (
    avaliar_cliente,
    avaliar_empresa,
    avaliar_faturamento,
    avaliar_nfe,
    avaliar_pedido,
    avaliar_produto,
)
from apps.fiscal.models import NFeSaida
from apps.produtos.models import Produto


def executar_auditoria_limpeza_cursor() -> dict[str, Any]:
    empresas = [avaliar_empresa(e) for e in Empresa.objects.all().order_by('id')]
    clientes = [avaliar_cliente(c) for c in Cliente.objects.all().order_by('id')]
    pedidos = [avaliar_pedido(p) for p in PedidoVenda.objects.select_related('cliente').order_by('id')]
    nfes = [
        avaliar_nfe(n)
        for n in NFeSaida.objects.select_related('cliente', 'pedido_venda').order_by('id')
    ]
    faturamentos = [
        avaliar_faturamento(f)
        for f in FaturamentoPedidoVenda.objects.select_related('pedido', 'pedido__cliente', 'nfe_saida').order_by('id')
    ]
    produtos = [avaliar_produto(p) for p in Produto.objects.all().order_by('id')[:5000]]

    def _candidatos(rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get('candidato')]

    def _preservados(rows: list[dict]) -> list[dict]:
        return [r for r in rows if not r.get('candidato') and r.get('motivo')]

    relatorio = {
        'gerado_em': datetime.now().isoformat(),
        'modo': 'dry_run',
        'resumo': {
            'empresas_candidatas': len(_candidatos(empresas)),
            'clientes_candidatos': len(_candidatos(clientes)),
            'pedidos_candidatos': len(_candidatos(pedidos)),
            'nfe_candidatas': len(_candidatos(nfes)),
            'faturamentos_candidatos': len(_candidatos(faturamentos)),
            'produtos_candidatos': len(_candidatos(produtos)),
            'produtos_revisao': len([p for p in produtos if p.get('classificacao') != 'provavelmente_real']),
            'preservados_nfe': len(_preservados(nfes)),
        },
        'empresas_candidatas': _candidatos(empresas),
        'clientes_candidatos': _candidatos(clientes),
        'pedidos_candidatos': _candidatos(pedidos),
        'nfe_candidatas': _candidatos(nfes),
        'faturamentos_candidatos': _candidatos(faturamentos),
        'produtos_candidatos': _candidatos(produtos),
        'produtos_revisao': produtos,
        'preservados': {
            'empresas': _preservados(empresas),
            'clientes': _preservados(clientes),
            'pedidos': _preservados(pedidos),
            'nfes': _preservados(nfes),
            'faturamentos': _preservados(faturamentos),
        },
        'bloqueios': {
            'produtos_exclusao_automatica': True,
            'nfe_com_xml_autorizado': 'nunca_excluir',
            'nfe_cstat_100': 'nunca_excluir',
        },
    }
    return relatorio


def salvar_relatorio_auditoria(relatorio: dict[str, Any]) -> tuple[Path, Path | None]:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    debug_dir = Path(settings.MEDIA_ROOT) / 'debug'
    debug_dir.mkdir(parents=True, exist_ok=True)
    json_path = debug_dir / f'limpeza_cursor_dry_run_{ts}.json'
    json_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')

    csv_path = debug_dir / f'limpeza_cursor_dry_run_{ts}.csv'
    rows: list[dict[str, str]] = []
    for tipo, chave in (
        ('empresa', 'empresas_candidatas'),
        ('cliente', 'clientes_candidatos'),
        ('pedido', 'pedidos_candidatos'),
        ('nfe', 'nfe_candidatas'),
        ('faturamento', 'faturamentos_candidatos'),
    ):
        for item in relatorio.get(chave, []):
            rows.append({
                'tipo': tipo,
                'id': str(item.get('id', '')),
                'identificador': str(
                    item.get('razao_social')
                    or item.get('numero')
                    or item.get('numero_faturamento')
                    or '',
                ),
                'motivos': ','.join(item.get('motivos') or []),
            })
    if rows:
        with csv_path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=['tipo', 'id', 'identificador', 'motivos'])
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path = None

    return json_path, csv_path
