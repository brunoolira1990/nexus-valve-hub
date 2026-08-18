"""
Remove registos duplicados por CNPJ (apenas dígitos iguais), mantendo o menor id.
Reatribui FKs conhecidas antes de apagar. Executar ANTES de migrate se unique=True falhar.

Uso (no container):
  python manage.py deduplicar_cnpj_cadastros --dry-run
  python manage.py deduplicar_cnpj_cadastros
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cadastros.models import Cliente, Empresa, Fornecedor, Transportadora
from apps.cadastros.utils import normalizar_cnpj


def _canonical_cnpj(cnpj: str) -> str:
    """Retorna a chave canônica sem separadores, para CNPJ numérico ou alfanumérico."""
    return normalizar_cnpj(cnpj)


class Command(BaseCommand):
    help = 'Remove duplicatas de CNPJ nos cadastros, mantendo o registro com menor id.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas lista o que seria feito, sem gravar.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']

        with transaction.atomic():
            n = 0
            n += self._dedupe_empresa(dry)
            n += self._dedupe_cliente(dry)
            n += self._dedupe_fornecedor(dry)
            n += self._dedupe_transportadora(dry)
            if dry:
                self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração gravada.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Concluído. Registos removidos ou reatribuídos: {n}.'))

    def _groups(self, qs, model_name: str):
        by_key = defaultdict(list)
        for obj in qs.only('id', 'cnpj'):
            chave = _canonical_cnpj(obj.cnpj)
            if not chave:
                continue
            by_key[chave].append(obj.id)
        dupes = {k: sorted(ids) for k, ids in by_key.items() if len(ids) > 1}
        if dupes:
            self.stdout.write(f'[{model_name}] CNPJs duplicados: {len(dupes)} grupos')
        return dupes

    def _dedupe_empresa(self, dry: bool) -> int:
        from apps.fiscal.models import CTeEntrada

        removed = 0
        dupes = self._groups(Empresa.objects.all(), 'Empresa')
        for _key, ids in dupes.items():
            keep, *rest = ids
            for rid in rest:
                if dry:
                    self.stdout.write(f'  Empresa id={rid} -> remover (mantém id={keep})')
                    continue
                Empresa.objects.filter(empresa_pai_id=rid).update(empresa_pai_id=keep)
                CTeEntrada.objects.filter(tomador_id=rid).update(tomador_id=keep)
                Empresa.objects.filter(pk=rid).delete()
                removed += 1
        return removed

    def _dedupe_cliente(self, dry: bool) -> int:
        from apps.comercial.models import PedidoVenda, Proposta
        from apps.fiscal.models import NFeSaida

        removed = 0
        dupes = self._groups(Cliente.objects.all(), 'Cliente')
        for _key, ids in dupes.items():
            keep, *rest = ids
            for rid in rest:
                if dry:
                    self.stdout.write(f'  Cliente id={rid} -> remover (mantém id={keep})')
                    continue
                Proposta.objects.filter(cliente_id=rid).update(cliente_id=keep)
                PedidoVenda.objects.filter(cliente_id=rid).update(cliente_id=keep)
                NFeSaida.objects.filter(cliente_id=rid).update(cliente_id=keep)
                Cliente.objects.filter(pk=rid).delete()
                removed += 1
        return removed

    def _dedupe_fornecedor(self, dry: bool) -> int:
        from apps.comercial.models import PedidoCompra
        from apps.corridas.models import Corrida
        from apps.fiscal.models import NFeEntrada

        removed = 0
        dupes = self._groups(Fornecedor.objects.all(), 'Fornecedor')
        for _key, ids in dupes.items():
            keep, *rest = ids
            for rid in rest:
                if dry:
                    self.stdout.write(f'  Fornecedor id={rid} -> remover (mantém id={keep})')
                    continue
                Corrida.objects.filter(fornecedor_id=rid).update(fornecedor_id=keep)
                PedidoCompra.objects.filter(fornecedor_id=rid).update(fornecedor_id=keep)
                NFeEntrada.objects.filter(fornecedor_id=rid).update(fornecedor_id=keep)
                Fornecedor.objects.filter(pk=rid).delete()
                removed += 1
        return removed

    def _dedupe_transportadora(self, dry: bool) -> int:
        from apps.fiscal.models import CTeEntrada

        removed = 0
        dupes = self._groups(Transportadora.objects.all(), 'Transportadora')
        for _key, ids in dupes.items():
            keep, *rest = ids
            for rid in rest:
                if dry:
                    self.stdout.write(f'  Transportadora id={rid} -> remover (mantém id={keep})')
                    continue
                CTeEntrada.objects.filter(transportadora_id=rid).update(transportadora_id=keep)
                Transportadora.objects.filter(pk=rid).delete()
                removed += 1
        return removed
