"""Popula os campos FK `material_ref` e `material_base_ref` a partir dos
CharFields legados `material` e `material_base`.

Faz match exato por nome no catálogo `Material`.
Usa .update() em batch — não dispara signals de auditoria.

Uso:
    python manage.py migrar_material_para_fk            # dry-run (padrão)
    python manage.py migrar_material_para_fk --apply    # persiste no banco
"""

from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.produtos.material_models import Material
from apps.produtos.models import FamiliaProduto, Produto


class Command(BaseCommand):
    help = 'Popula material_ref e material_base_ref a partir dos charfields legados (dry-run por padrão).'

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
            f'=== migrar_material_para_fk [{mode}] ==='
        ))
        self.stdout.write('')

        # ------------------------------------------------------------------
        # Índice em memória: nome → Material.id  (evita N+1 queries)
        # ------------------------------------------------------------------
        catalogo: dict[str, int] = {
            m.nome: m.id
            for m in Material.objects.only('id', 'nome')
        }
        self.stdout.write(f'  Catálogo carregado: {len(catalogo)} materiais\n')

        # ==================================================================
        # PRODUTOS
        # ==================================================================
        self.stdout.write(self.style.MIGRATE_HEADING('── Produtos ──'))
        self.stdout.write('')

        produtos = list(
            Produto.objects
            .filter(material_ref__isnull=True)   # já migrados ficam de fora
            .exclude(material='')                 # sem material legado = nada a fazer
            .only('id', 'codigo_completo', 'material')
            .order_by('id')
        )

        # material_id → lista de produto_id
        prod_por_mat: dict[int, list[int]] = defaultdict(list)
        prod_sem_match: list[tuple[int, str, str]] = []  # (id, codigo, material_legado)

        for prod in produtos:
            mat_nome = (prod.material or '').strip()
            mat_id   = catalogo.get(mat_nome)
            cod      = prod.codigo_completo or f'#{prod.id}'
            if mat_id:
                prod_por_mat[mat_id].append(prod.id)
            else:
                prod_sem_match.append((prod.id, cod, mat_nome))

        total_prod_match  = sum(len(v) for v in prod_por_mat.values())
        total_prod_no_mat = len(prod_sem_match)

        # Tabela de matches por material
        C_MAT, C_QTD = 35, 5
        self.stdout.write(
            f"  {'MATERIAL':<{C_MAT}}  {'PRODUTOS':>{C_QTD}}"
        )
        self.stdout.write('  ' + '─' * (C_MAT + C_QTD + 4))
        # Índice inverso id → nome para exibição
        id_to_nome = {v: k for k, v in catalogo.items()}
        for mat_id, ids in sorted(prod_por_mat.items(), key=lambda x: -len(x[1])):
            self.stdout.write(
                f"  {id_to_nome.get(mat_id, f'id={mat_id}'):<{C_MAT}}  {len(ids):>{C_QTD}}"
            )

        self.stdout.write('')
        self.stdout.write(f'  Com match    : {total_prod_match}')
        self.stdout.write(f'  Sem match    : {total_prod_no_mat}')

        if prod_sem_match:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'  ── Produtos SEM match ({total_prod_no_mat}) ──'
            ))
            for pid, cod, mat in prod_sem_match:
                self.stdout.write(f"    #{pid:<6}  {cod:<28}  material={mat!r}")

        self.stdout.write('')

        # Guarda: >5 sem match em produtos → PARE
        if total_prod_no_mat > 5:
            self.stdout.write(self.style.ERROR(
                f'⚠  ALERTA: {total_prod_no_mat} produtos sem match (> 5).\n'
                '   Revise o catálogo antes de aplicar.'
            ))
            if not apply:
                return

        # ==================================================================
        # FAMÍLIAS
        # ==================================================================
        self.stdout.write(self.style.MIGRATE_HEADING('── Famílias ──'))
        self.stdout.write('')

        familias = list(
            FamiliaProduto.objects
            .filter(material_base_ref__isnull=True)  # já migradas ficam de fora
            .exclude(material_base='')               # sem material = nada a fazer
            .only('id', 'codigo_figura', 'material_base')
            .order_by('id')
        )

        # material_id → lista de familia_id
        fam_por_mat: dict[int, list[int]] = defaultdict(list)
        fam_sem_match: list[tuple[int, str, str]] = []  # (id, codigo_figura, material_legado)

        for fam in familias:
            mat_nome = (fam.material_base or '').strip()
            mat_id   = catalogo.get(mat_nome)
            cod      = fam.codigo_figura or f'#{fam.id}'
            if mat_id:
                fam_por_mat[mat_id].append(fam.id)
            else:
                fam_sem_match.append((fam.id, cod, mat_nome))

        total_fam_match  = sum(len(v) for v in fam_por_mat.values())
        total_fam_no_mat = len(fam_sem_match)

        self.stdout.write(
            f"  {'MATERIAL':<{C_MAT}}  {'FAMÍLIAS':>{C_QTD}}"
        )
        self.stdout.write('  ' + '─' * (C_MAT + C_QTD + 4))
        for mat_id, ids in sorted(fam_por_mat.items(), key=lambda x: -len(x[1])):
            self.stdout.write(
                f"  {id_to_nome.get(mat_id, f'id={mat_id}'):<{C_MAT}}  {len(ids):>{C_QTD}}"
            )

        self.stdout.write('')
        self.stdout.write(f'  Com match    : {total_fam_match}')
        self.stdout.write(f'  Sem match    : {total_fam_no_mat}')

        if fam_sem_match:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'  ── Famílias SEM match ({total_fam_no_mat}) ──'
            ))
            for fid, cod, mat in fam_sem_match:
                self.stdout.write(f"    #{fid:<6}  {cod:<16}  material_base={mat!r}")

        self.stdout.write('')

        # ==================================================================
        # Resumo final
        # ==================================================================
        self.stdout.write('─' * 70)
        self.stdout.write(f'  Produtos: {total_prod_match} com match / {total_prod_no_mat} sem match')
        self.stdout.write(f'  Famílias: {total_fam_match} com match / {total_fam_no_mat} sem match')
        self.stdout.write('')

        if not apply:
            self.stdout.write(self.style.WARNING(
                'Dry-run concluído — nenhuma alteração feita.\n'
                'Execute com --apply para persistir.'
            ))
            return

        # ==================================================================
        # Aplicação — .update() em batch agrupado por material
        # ==================================================================
        self.stdout.write(self.style.MIGRATE_HEADING('── Aplicando ──'))
        self.stdout.write('')

        total_prod_updated = 0
        total_fam_updated  = 0

        with transaction.atomic():
            # Produtos
            for mat_id, ids in prod_por_mat.items():
                updated = Produto.objects.filter(id__in=ids).update(material_ref_id=mat_id)
                total_prod_updated += updated
                self.stdout.write(
                    f"  Produto  ✔  {id_to_nome.get(mat_id):<35} → {updated} registro(s)"
                )
            # Famílias
            for mat_id, ids in fam_por_mat.items():
                updated = FamiliaProduto.objects.filter(id__in=ids).update(material_base_ref_id=mat_id)
                total_fam_updated += updated
                self.stdout.write(
                    f"  Família  ✔  {id_to_nome.get(mat_id):<35} → {updated} registro(s)"
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído.\n'
            f'  Produtos atualizados : {total_prod_updated}\n'
            f'  Famílias atualizadas : {total_fam_updated}'
        ))
