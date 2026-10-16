"""Propaga `FamiliaProduto.material_base` para `Produto.material`.

Substitui apenas produtos cujo material é genérico ou vazio.
Preserva produtos com material específico editado manualmente.

Uso:
    python manage.py propagar_material_produtos            # dry-run (padrão)
    python manage.py propagar_material_produtos --apply    # aplica no banco
"""

from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.produtos.models import FamiliaProduto, Produto

# ---------------------------------------------------------------------------
# Materiais genéricos — elegíveis para substituição.
# São os valores "rasos" (sem grau ASTM) que o sistema atribuía antes
# da migração para o catálogo de materiais.
# ---------------------------------------------------------------------------
MATERIAIS_GENERICOS: frozenset[str] = frozenset({
    'Aço Carbono',
    'Aço Inox',
    'Aço Carbono Galvanizado',
    'Latão',
    'Bronze',
    'PVC',
    'Ferro Fundido',
    '',           # campo em branco
    '(vazio)',    # sentinela legado usado em algumas importações
})


def _eh_generico(material: str | None) -> bool:
    """True se o material deve ser substituído pela propagação."""
    return (material or '') in MATERIAIS_GENERICOS


class Command(BaseCommand):
    help = (
        'Propaga material_base da família para Produto.material '
        'quando o produto tem material genérico ou vazio (dry-run por padrão).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Persiste as alterações no banco via .update() em batch.',
        )

    def handle(self, *args, **opts):
        apply: bool = opts['apply']
        mode = 'APPLY' if apply else 'DRY-RUN'

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'=== propagar_material_produtos [{mode}] ==='
        ))
        self.stdout.write('')

        # ------------------------------------------------------------------
        # Carrega todos os produtos com família, juntando material_base
        # ------------------------------------------------------------------
        produtos = list(
            Produto.objects
            .select_related('familia')
            .only(
                'id',
                'codigo_completo',
                'descricao',
                'material',
                'familia__id',
                'familia__codigo_figura',
                'familia__material_base',
            )
            .order_by('id')
        )
        total = len(produtos)

        # ------------------------------------------------------------------
        # Classificação
        # ------------------------------------------------------------------

        # (material_antigo, material_novo) → lista de (id, codigo, descricao)
        alteracoes: dict[tuple[str, str], list[tuple[int, str, str]]] = defaultdict(list)

        # Contadores de motivo de não-alteração
        sem_familia: list[tuple[int, str, str]] = []          # familia_id=None
        familia_sem_material: list[tuple[int, str, str]] = [] # material_base=''
        material_especifico: list[tuple[int, str, str, str]] = [] # já específico

        for prod in produtos:
            mat_atual = (prod.material or '').strip()
            cod = prod.codigo_completo or f'#{prod.id}'
            desc = prod.descricao or ''

            # Sem família → não toca
            if prod.familia_id is None:
                sem_familia.append((prod.id, cod, desc))
                continue

            mat_base = (prod.familia.material_base or '').strip()

            # Família sem material_base → não toca (não sabemos o material)
            if not mat_base:
                familia_sem_material.append((prod.id, cod, desc))
                continue

            # Material do produto já é específico → preserva
            if not _eh_generico(mat_atual):
                material_especifico.append((prod.id, cod, desc, mat_atual))
                continue

            # Material genérico e mesmo valor da família → já está correto
            if mat_atual == mat_base:
                material_especifico.append((prod.id, cod, desc, mat_atual))
                continue

            # Elegível para substituição
            alteracoes[(mat_atual, mat_base)].append((prod.id, cod, desc))

        # ------------------------------------------------------------------
        # Estatísticas
        # ------------------------------------------------------------------
        total_alterar = sum(len(v) for v in alteracoes.values())
        n_sem_familia = len(sem_familia)
        n_fam_sem_mat = len(familia_sem_material)
        n_especifico  = len(material_especifico)

        # ------------------------------------------------------------------
        # Output — distribuição de mudanças
        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING('── Distribuição das substituições ──'))
        self.stdout.write('')

        if alteracoes:
            C_OLD, C_NEW, C_QTD = 30, 32, 5
            self.stdout.write(
                f"  {'MATERIAL ANTIGO':<{C_OLD}}  {'MATERIAL NOVO':<{C_NEW}}  {'QTD':>{C_QTD}}"
            )
            self.stdout.write('  ' + '─' * (C_OLD + C_NEW + C_QTD + 6))
            # Ordena por quantidade descendente
            for (mat_old, mat_new), rows in sorted(
                alteracoes.items(), key=lambda x: -len(x[1])
            ):
                label_old = repr(mat_old) if mat_old else "'(vazio)'"
                self.stdout.write(
                    f"  {label_old:<{C_OLD}}  {mat_new:<{C_NEW}}  {len(rows):>{C_QTD}}"
                )
        else:
            self.stdout.write('  (nenhuma substituição necessária)')
        self.stdout.write('')

        # ------------------------------------------------------------------
        # Top 5 exemplos de produtos que serão alterados
        # ------------------------------------------------------------------
        if alteracoes:
            self.stdout.write(self.style.MIGRATE_HEADING('── Top 5 exemplos de produtos a alterar ──'))
            self.stdout.write('')
            exemplos: list[tuple[str, str, str, str]] = []
            for (mat_old, mat_new), rows in sorted(
                alteracoes.items(), key=lambda x: -len(x[1])
            ):
                for pid, cod, desc in rows:
                    exemplos.append((cod, desc, mat_old or '(vazio)', mat_new))
                    if len(exemplos) >= 5:
                        break
                if len(exemplos) >= 5:
                    break

            for cod, desc, mat_old, mat_new in exemplos:
                self.stdout.write(
                    f"  {cod:<28}  {mat_old!r} → {mat_new!r}"
                )
                self.stdout.write(
                    f"  {'':28}  desc: {desc[:60]}"
                )
            self.stdout.write('')

        # ------------------------------------------------------------------
        # Não alterados
        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING('── Não alterados ──'))
        self.stdout.write('')
        self.stdout.write(
            f"  Sem família (familia_id=None)          : {n_sem_familia}"
        )
        self.stdout.write(
            f"  Família sem material_base              : {n_fam_sem_mat}"
        )
        self.stdout.write(
            f"  Material específico (preservado)       : {n_especifico}"
        )
        self.stdout.write('')

        # Detalha produtos com material específico notável (primeiros 10)
        if material_especifico:
            self.stdout.write('  Exemplos preservados (até 10):')
            for _id, cod, desc, mat in material_especifico[:10]:
                self.stdout.write(
                    f"    {cod:<28}  material={mat!r}"
                )
            if len(material_especifico) > 10:
                self.stdout.write(f"    … e mais {len(material_especifico) - 10} produtos.")
            self.stdout.write('')

        # ------------------------------------------------------------------
        # Resumo final
        # ------------------------------------------------------------------
        self.stdout.write('─' * 70)
        self.stdout.write(f'  Total de produtos analisados           : {total}')
        self.stdout.write(f'  Elegíveis para substituição            : {total_alterar}')
        self.stdout.write(f'  Sem família                            : {n_sem_familia}')
        self.stdout.write(f'  Família sem material_base              : {n_fam_sem_mat}')
        self.stdout.write(f'  Material específico (preservados)      : {n_especifico}')
        self.stdout.write('')

        if not apply:
            self.stdout.write(self.style.WARNING(
                'Dry-run concluído — nenhuma alteração feita.\n'
                'Execute com --apply para persistir.'
            ))
            return

        # ------------------------------------------------------------------
        # Aplicação — .update() em batch por (mat_old, mat_new)
        # Agrupa por material_novo para minimizar número de queries.
        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING('── Aplicando alterações ──'))
        self.stdout.write('')

        # Reagrupa por material_novo → ids
        por_novo: dict[str, list[int]] = defaultdict(list)
        for (mat_old, mat_new), rows in alteracoes.items():
            por_novo[mat_new].extend(r[0] for r in rows)

        total_updated = 0
        with transaction.atomic():
            for mat_new, ids in sorted(por_novo.items()):
                updated = (
                    Produto.objects
                    .filter(id__in=ids)
                    .update(material=mat_new)
                )
                total_updated += updated
                self.stdout.write(
                    f"  ✔  {mat_new:<38}  → {updated} produto(s)"
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído. {total_updated} produtos atualizados.'
        ))
