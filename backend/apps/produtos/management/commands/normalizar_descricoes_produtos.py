"""Normaliza descrições antigas (maiúsculo sem acento) em Família e Produto."""

from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.produtos.descricao_norm import normalizar_descricao_produto
from apps.produtos.models import FamiliaProduto, Produto


def _iter_changes(qs, field: str, max_examples: int) -> tuple[int, list[tuple[str, str]]]:
    changed = 0
    examples: list[tuple[str, str]] = []
    for obj in qs.iterator(chunk_size=500):
        raw = getattr(obj, field) or ''
        if not raw.strip():
            continue
        new_val = normalizar_descricao_produto(raw)
        if new_val != raw:
            changed += 1
            if len(examples) < max_examples:
                examples.append((raw, new_val))
    return changed, examples


def _bulk_apply(model, field: str, batch_size: int) -> int:
    """Atualiza em lotes dentro da transação do caller."""
    updated = 0
    batch: list = []
    for obj in model.objects.all().iterator(chunk_size=500):
        raw = getattr(obj, field) or ''
        if not raw.strip():
            continue
        new_val = normalizar_descricao_produto(raw)
        if new_val != raw:
            setattr(obj, field, new_val)
            batch.append(obj)
        if len(batch) >= batch_size:
            model.objects.bulk_update(batch, [field])
            updated += len(batch)
            batch.clear()
    if batch:
        model.objects.bulk_update(batch, [field])
        updated += len(batch)
    return updated


class Command(BaseCommand):
    help = (
        'Normaliza descricao_base (família) e descricao / dimensao_descricao (produto) '
        'com normalizar_descricao_produto. Sem --apply, apenas simula (dry-run).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula alterações (é o padrão quando --apply não é informado).',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Persiste alterações em uma única transação.',
        )
        parser.add_argument(
            '--examples',
            type=int,
            default=8,
            help='Máximo de exemplos antes/depois por campo no dry-run (default: 8).',
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

        specs: list[tuple[str, type, str]] = [
            ('FamiliaProduto', FamiliaProduto, 'descricao_base'),
            ('Produto', Produto, 'descricao'),
            ('Produto', Produto, 'dimensao_descricao'),
        ]

        totals: dict[str, int] = defaultdict(int)
        all_examples: dict[str, list[tuple[str, str]]] = {}

        self.stdout.write(self.style.WARNING('Campos: descricao_base (família), descricao e dimensao_descricao (produto).'))
        self.stdout.write(self.style.WARNING('Códigos internos / codigo_figura não são alterados.\n'))

        for model_name, model, fld in specs:
            key = f'{model_name}.{fld}'
            cnt, ex = _iter_changes(model.objects.all(), fld, max_ex)
            totals[key] = cnt
            all_examples[key] = ex
            self.stdout.write(f'[{key}] registros a normalizar: {cnt}')
            for i, (before, after) in enumerate(ex, 1):
                self.stdout.write(f'  Exemplo {i}:')
                self.stdout.write(f'    ANTES: {before[:240]}{"…" if len(before) > 240 else ""}')
                self.stdout.write(f'    DEPOIS: {after[:240]}{"…" if len(after) > 240 else ""}')
            if cnt > len(ex):
                self.stdout.write(f'  … (+{cnt - len(ex)} sem amostra extra)\n')
            else:
                self.stdout.write('')

        total_rows = sum(totals.values())
        if not apply:
            self.stdout.write(self.style.SUCCESS(f'Dry-run concluído. Total de linhas que seriam alteradas: {total_rows}'))
            self.stdout.write(self.style.NOTICE('Nada foi gravado. Execute com --apply para persistir.'))
            return

        if total_rows == 0:
            self.stdout.write(self.style.SUCCESS('Nada a alterar (--apply ignorado).'))
            return

        self.stdout.write(self.style.WARNING(f'Aplicando {total_rows} alteração(ões) em transação única…'))

        applied: dict[str, int] = {}
        with transaction.atomic():
            for model_name, model, fld in specs:
                key = f'{model_name}.{fld}'
                n = _bulk_apply(model, fld, batch_size)
                applied[key] = n

        self.stdout.write(self.style.SUCCESS('\nAlterações gravadas (por campo):'))
        for k, n in applied.items():
            self.stdout.write(self.style.SUCCESS(f'  {k}: {n}'))
        self.stdout.write(self.style.SUCCESS(f'Total gravado: {sum(applied.values())}'))
