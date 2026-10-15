"""Normaliza o campo `material` dos produtos.

Dry-run por padrão — não altera nada sem --apply.

Uso:
    python manage.py normalizar_materiais            # dry-run
    python manage.py normalizar_materiais --apply    # aplica
    python manage.py normalizar_materiais --reverse  # reverte para valores anteriores
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.produtos.models import Produto

# ---------------------------------------------------------------------------
# Mapa canônico: valor-origem → valor-canônico
# Canônicos finais batem com frontend/src/pages/Produtos/tabs/constants.ts
# ---------------------------------------------------------------------------
MAPA: Dict[str, str] = {
    # Aço Carbono — variantes sem acento / todo maiúsculo
    'ACO CARBONO':    'Aço Carbono',
    'AÇO CARBONO':    'Aço Carbono',
    # Aço Inox — variantes
    'AÇO INOX':       'Aço Inox',
    'AÇO INOXIDÁVEL': 'Aço Inox',
    'ACO INOXIDAVEL': 'Aço Inox',
    # Demais materiais com grafia inconsistente
    'LATAO':          'Latão',
    'FERRO FUNDIDO':  'Ferro Fundido',
    'OUTRO':          'Outro',
}

# Valores já canônicos — não precisam de conversão.
# Listados aqui apenas para fins de documentação e validação de output.
CANONICOS_CONHECIDOS = {
    'Aço Carbono',
    'Aço Inox',
    'Alumínio',
    'Bronze',
    'Ferro Fundido',
    'Latão',
    'PVC',
    'PTFE',
    'Borracha',
    'Outro',
    '',  # campo em branco é permitido
}


class Command(BaseCommand):
    help = 'Normaliza o campo material dos produtos (dry-run por padrão)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Aplica as alterações no banco. Sem esta flag, executa apenas dry-run.',
        )
        parser.add_argument(
            '--reverse',
            action='store_true',
            default=False,
            help='Reverte: usa o mapa invertido (canônico → primeira origem mapeada).',
        )

    def handle(self, *args, **opts):
        apply: bool = opts['apply']
        reverse: bool = opts['reverse']

        # ------------------------------------------------------------------
        # Monta o mapa efetivo
        # ------------------------------------------------------------------
        if reverse:
            # Inverte MAPA: canônico → conjunto de origens.
            # Para o update usamos canônico → primeira origem listada.
            mapa_reverso: Dict[str, str] = {}
            for origem, canon in MAPA.items():
                if canon not in mapa_reverso:
                    mapa_reverso[canon] = origem
            mapa_efetivo = mapa_reverso
            self.stdout.write(self.style.WARNING(
                '\n⚠  Modo REVERSE — revertendo para valores originais (antes da normalização).'
            ))
        else:
            mapa_efetivo = MAPA

        mode_label = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.HTTP_INFO(
            f'\n=== normalizar_materiais [{mode_label}] ===\n'
        ))

        # ------------------------------------------------------------------
        # Levantamento: agrupa produtos por valor-de do campo material
        # ------------------------------------------------------------------
        # Somente produtos cujo material esteja no mapa (há algo a converter)
        produtos_por_origem: Dict[str, list] = defaultdict(list)
        nao_reconhecidos: Dict[str, int] = defaultdict(int)

        qs = Produto.objects.only('id', 'material')

        for prod in qs.iterator(chunk_size=500):
            val = prod.material or ''

            if val in mapa_efetivo:
                produtos_por_origem[val].append(prod.id)
            elif val not in CANONICOS_CONHECIDOS:
                # Valor desconhecido — não está no mapa nem é canônico
                nao_reconhecidos[val] += 1

        # ------------------------------------------------------------------
        # Relatório: o que será alterado
        # ------------------------------------------------------------------
        total_a_alterar = sum(len(ids) for ids in produtos_por_origem.values())

        if not produtos_por_origem:
            self.stdout.write(self.style.SUCCESS(
                'Nenhum produto precisa de normalização. Banco já está limpo.'
            ))
        else:
            self.stdout.write('Alterações planejadas:\n')
            self.stdout.write(
                f"  {'ORIGEM':<25} {'→':^3} {'CANÔNICO':<20} {'QTD':>6}"
            )
            self.stdout.write('  ' + '-' * 60)

            for origem, ids in sorted(produtos_por_origem.items(), key=lambda x: -len(x[1])):
                canon = mapa_efetivo[origem]
                self.stdout.write(
                    f"  {origem!r:<25} {'→':^3} {canon!r:<20} {len(ids):>6}"
                )

            self.stdout.write(f'\n  Total de produtos a alterar: {total_a_alterar}')

            # Detalhe por produto
            self.stdout.write('\nDetalhe por produto:')
            for origem, ids in sorted(produtos_por_origem.items()):
                canon = mapa_efetivo[origem]
                for pid in ids:
                    self.stdout.write(f"  produto #{pid}: {origem!r} -> {canon!r}")

        # ------------------------------------------------------------------
        # Valores não reconhecidos
        # ------------------------------------------------------------------
        if nao_reconhecidos:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '⚠  Valores NÃO reconhecidos (não alterados — requer revisão manual):'
            ))
            for val, count in sorted(nao_reconhecidos.items(), key=lambda x: -x[1]):
                self.stdout.write(self.style.WARNING(
                    f"     {val!r:<30}  {count} produto(s)"
                ))

        # ------------------------------------------------------------------
        # Execução (apenas com --apply)
        # ------------------------------------------------------------------
        if not apply:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Dry-run concluído — nenhuma alteração foi feita.\n'
                'Execute com --apply para aplicar.'
            ))
            return

        if not produtos_por_origem:
            return

        # Aplica em batch por valor-de, dentro de uma transação única.
        # Usamos .filter().update() para evitar salvar produto a produto
        # e não poluir RegistroAuditoria com centenas de signals.
        self.stdout.write('')
        with transaction.atomic():
            for origem, ids in sorted(produtos_por_origem.items()):
                canon = mapa_efetivo[origem]
                updated = (
                    Produto.objects
                    .filter(id__in=ids)
                    .update(material=canon)
                )
                self.stdout.write(
                    f"  ✔  {origem!r} → {canon!r}  ({updated} produto(s) atualizados)"
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n✔  Normalização concluída. {total_a_alterar} produto(s) atualizados.'
        ))
