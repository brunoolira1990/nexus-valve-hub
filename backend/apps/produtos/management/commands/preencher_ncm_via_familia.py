"""Preenche o NCM dos produtos legados copiando o ncm_padrao da família."""

from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.produtos.models import Produto


def _listar_preenchiveis():
    """Produtos com NCM vazio cuja família tenha ncm_padrao; ignora o resto.

    Retorna (linhas, total_sem_ncm, orfaos) onde linhas são (produto, codigo_ncm).
    """
    linhas: list[tuple[Produto, str]] = []
    total_sem_ncm = 0
    orfaos = 0
    for produto in (
        Produto.objects.select_related('familia', 'familia__ncm_padrao')
        .filter(Q(ncm='') | Q(ncm__isnull=True))
        .order_by('id')
        .iterator(chunk_size=500)
    ):
        if (produto.ncm or '').strip():
            continue
        total_sem_ncm += 1
        familia = produto.familia
        ncm_familia = getattr(familia, 'ncm_padrao', None) if familia else None
        codigo = (getattr(ncm_familia, 'codigo', '') or '').strip()
        if not codigo:
            orfaos += 1
            continue
        linhas.append((produto, codigo))
    return linhas, total_sem_ncm, orfaos


def _aplicar(linhas, batch_size: int) -> int:
    """Grava em lotes via bulk_update — save() do Produto não é chamado de propósito
    (ele regrava código/sequência de manômetro)."""
    gravados = 0
    with transaction.atomic():
        batch: list[Produto] = []
        for produto, codigo in linhas:
            produto.ncm = codigo
            batch.append(produto)
            if len(batch) >= batch_size:
                Produto.objects.bulk_update(batch, ['ncm'])
                gravados += len(batch)
                batch = []
        if batch:
            Produto.objects.bulk_update(batch, ['ncm'])
            gravados += len(batch)
    return gravados


class Command(BaseCommand):
    help = (
        'Copia o ncm_padrao da família para os produtos com ncm vazio. '
        'Sem --apply, apenas simula (dry-run). Não toca ncm_especifico nem em códigos.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula o preenchimento (é o padrão quando --apply não é informado).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Persiste os NCMs em uma única transação.',
        )
        parser.add_argument(
            '--examples',
            type=int,
            default=8,
            help='Máximo de exemplos id | código | família | NCM no dry-run (default: 8).',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Tamanho do lote em bulk_update (default: 500).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        if apply and options.get('dry_run'):
            raise CommandError('Não use --dry-run junto com --apply.')
        max_ex = max(1, min(options['examples'], 50))
        batch_size = max(50, min(options['batch_size'], 2000))

        linhas, total_sem_ncm, orfaos = _listar_preenchiveis()

        self.stdout.write(self.style.WARNING('Escopo: produtos com ncm vazio que têm família com ncm_padrao.'))
        self.stdout.write(self.style.WARNING('ncm_especifico, dimensoes_json e codigo_completo ficam intactos.\n'))
        self.stdout.write(f'Produtos sem NCM: {total_sem_ncm}')
        self.stdout.write(f'  → preenchíveis via família: {len(linhas)}')
        self.stdout.write(f'  → sem família ou sem ncm_padrao: {orfaos}')

        if not linhas:
            self.stdout.write(self.style.SUCCESS('Nada a preencher.'))
            return

        por_ncm = Counter(codigo for _, codigo in linhas)
        self.stdout.write(f'\nNCMs de destino ({len(por_ncm)} distintos):')
        for codigo, quantidade in por_ncm.most_common():
            self.stdout.write(f'  {codigo}: {quantidade}')

        self.stdout.write('\nExemplos:')
        for produto, codigo in linhas[:max_ex]:
            self.stdout.write(f'  #{produto.id} | {produto.codigo_completo or "—"} | fam={produto.familia_id} | ncm → {codigo}')
        if len(linhas) > max_ex:
            self.stdout.write(f'  … (+{len(linhas) - max_ex} não amostrados)')

        if not apply:
            self.stdout.write(self.style.SUCCESS(f'\nDry-run concluído. {len(linhas)} produto(s) seriam preenchidos.'))
            self.stdout.write(self.style.NOTICE('Nada foi gravado. Execute com --apply para persistir.'))
            return

        self.stdout.write(self.style.WARNING(f'\nAplicando {len(linhas)} NCM(s) em transação única…'))
        gravados = _aplicar(linhas, batch_size)
        self.stdout.write(self.style.SUCCESS(f'NCMs gravados: {gravados}'))
