"""Limpeza segura de dados Cursor/teste com confirmação e backup prévio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.db import transaction

from apps.cadastros.models import Cliente, Empresa
from apps.comercial.models import FaturamentoPedidoVenda, ItemPedidoVenda, PedidoVenda
from apps.fiscal.limpeza_cursor.criterios import avaliar_produto, nfe_deve_preservar
from apps.fiscal.models import AlocacaoAtendimento, NFeSaida
from apps.produtos.models import Produto


from django.conf import settings


class LimpezaCursorError(Exception):
    pass


def _ids_candidatos(relatorio: dict[str, Any], chave: str) -> list[int]:
    return [int(r['id']) for r in relatorio.get(chave, []) if r.get('candidato') and r.get('id')]


def verificar_backup_existe() -> Path | None:
    base = Path(settings.MEDIA_ROOT) / 'backups' / 'limpeza_cursor'
    if not base.exists():
        return None
    dirs = sorted([p for p in base.iterdir() if p.is_dir()], reverse=True)
    for d in dirs:
        if (d / 'resumo.json').exists():
            return d
    return None


@transaction.atomic
def executar_limpeza_cursor(relatorio: dict[str, Any]) -> dict[str, int]:
    nfe_ids = _ids_candidatos(relatorio, 'nfe_candidatas')
    fat_ids = _ids_candidatos(relatorio, 'faturamentos_candidatos')
    pedido_ids = _ids_candidatos(relatorio, 'pedidos_candidatos')
    cliente_ids = _ids_candidatos(relatorio, 'clientes_candidatos')
    empresa_ids = _ids_candidatos(relatorio, 'empresas_candidatas')

    produto_ids = _ids_candidatos(relatorio, 'produtos_candidatos')

    removidos = {
        'alocacao': 0,
        'nfe': 0,
        'faturamento': 0,
        'pedido': 0,
        'produto': 0,
        'cliente': 0,
        'empresa': 0,
    }

    for nf_id in nfe_ids:
        nf = NFeSaida.objects.filter(pk=nf_id).first()
        if not nf:
            continue
        pres, _ = nfe_deve_preservar(nf)
        if pres:
            raise LimpezaCursorError(f'NF-e id={nf_id} deve ser preservada — abortado.')
        FaturamentoPedidoVenda.objects.filter(nfe_saida_id=nf_id).update(
            nfe_saida_id=None,
            nfe_saida_gerada_em=None,
            status=FaturamentoPedidoVenda.Status.PRONTO_PARA_NFE,
        )
        nf.delete()
        removidos['nfe'] += 1

    for fat_id in fat_ids:
        fat = FaturamentoPedidoVenda.objects.filter(pk=fat_id).first()
        if not fat:
            continue
        if fat.nfe_saida_id and NFeSaida.objects.filter(pk=fat.nfe_saida_id).exists():
            continue
        fat.delete()
        removidos['faturamento'] += 1

    for pedido_id in pedido_ids:
        ped = PedidoVenda.objects.filter(pk=pedido_id).first()
        if not ped:
            continue
        if FaturamentoPedidoVenda.objects.filter(pedido=ped).exists():
            continue
        if NFeSaida.objects.filter(pedido_venda=ped).exists():
            continue
        AlocacaoAtendimento.objects.filter(pedido_venda_item__pedido=ped).delete()
        ped.delete()
        removidos['pedido'] += 1

    for produto_id in produto_ids:
        prod = Produto.objects.filter(pk=produto_id).first()
        if not prod:
            continue
        aval = avaliar_produto(prod)
        if not aval.get('candidato'):
            continue
        if ItemPedidoVenda.objects.filter(produto=prod).exists():
            continue
        if NFeSaida.objects.filter(itens__produto=prod).exists():
            continue
        prod.delete()
        removidos['produto'] += 1

    for cliente_id in cliente_ids:
        cli = Cliente.objects.filter(pk=cliente_id).first()
        if not cli:
            continue
        if NFeSaida.objects.filter(cliente=cli).exists():
            continue
        if PedidoVenda.objects.filter(cliente=cli).exists():
            continue
        cli.delete()
        removidos['cliente'] += 1

    for empresa_id in empresa_ids:
        emp = Empresa.objects.filter(pk=empresa_id).first()
        if not emp:
            continue
        if PedidoVenda.objects.filter(empresa_emitente=emp).exists():
            continue
        emp.delete()
        removidos['empresa'] += 1

    return removidos


def carregar_relatorio_auditoria(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise LimpezaCursorError(f'Arquivo de auditoria não encontrado: {path}')
    return json.loads(path.read_text(encoding='utf-8'))
