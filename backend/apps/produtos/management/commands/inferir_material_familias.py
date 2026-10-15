"""Infere e preenche `FamiliaProduto.material_base` a partir de `descricao_base`.

Aplica um mapa conservador de substrings (case-insensitive) para classificar
apenas casos inequívocos. Ambíguos e sem match são listados mas NÃO alterados.

Lógica de avaliação (por ordem de prioridade):
  1. Regras contextuais para 'ACO CARBONO' genérico:
       VALVULA + ACO CARBONO  → 'Aço Carbono A216 WCB'   (fundido)
       TUBO    + ACO CARBONO  → SEM MATCH intencional     (A-106, não cadastrado)
       ACO CARBONO (fallback) → 'Aço Carbono A105'        (fitting forjado)
  2. Mapa MAPA_INFERENCIA (inox, ferro fundido, não-ferrosos, polímeros).
  3. Nenhum match → sem match real.

Uso:
    python manage.py inferir_material_familias              # dry-run (padrão)
    python manage.py inferir_material_familias --apply      # aplica no banco
    python manage.py inferir_material_familias --apenas-sem-match
"""

from __future__ import annotations

import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.produtos.models import FamiliaProduto

# ---------------------------------------------------------------------------
# Mapa específico (mais específico → genérico, aplicado em ordem)
# As regras contextuais de ACO CARBONO têm prioridade e são tratadas antes.
# ---------------------------------------------------------------------------
MAPA_INFERENCIA: list[tuple[str, str]] = [
    # ── Aços Inox (316L antes de 316, 304L antes de 304, CF3M antes de CF3) ──
    ('AÇO INOX 316L',  'Aço Inox 316L'),
    ('ACO INOX 316L',  'Aço Inox 316L'),
    ('INOX 316L',      'Aço Inox 316L'),
    ('AISI 316L',      'Aço Inox 316L'),
    ('CF3M',           'Aço Inox 316L'),   # CF3M = 316L
    ('AÇO INOX 316',   'Aço Inox 316'),
    ('ACO INOX 316',   'Aço Inox 316'),
    ('INOX 316',       'Aço Inox 316'),
    ('AISI 316',       'Aço Inox 316'),
    ('CF8M',           'Aço Inox 316'),    # CF8M = 316
    ('AÇO INOX 304L',  'Aço Inox 304L'),
    ('ACO INOX 304L',  'Aço Inox 304L'),
    ('INOX 304L',      'Aço Inox 304L'),
    ('AISI 304L',      'Aço Inox 304L'),
    ('CF3',            'Aço Inox 304L'),   # CF3  = 304L (depois de CF3M)
    ('AÇO INOX 304',   'Aço Inox 304'),
    ('ACO INOX 304',   'Aço Inox 304'),
    ('INOX 304',       'Aço Inox 304'),
    ('AISI 304',       'Aço Inox 304'),
    ('CF8',            'Aço Inox 304'),    # CF8  = 304  (depois de CF8M)

    # ── Aços Carbono com grau explícito (WCB/WPB/LF2 antes de A-216/234/350) ──
    ('A-216 WCB',      'Aço Carbono A216 WCB'),
    ('A216 WCB',       'Aço Carbono A216 WCB'),
    ('WCB',            'Aço Carbono A216 WCB'),
    ('A-234 WPB',      'Aço Carbono A234 WPB'),
    ('A234 WPB',       'Aço Carbono A234 WPB'),
    ('WPB',            'Aço Carbono A234 WPB'),
    ('A-350 LF2',      'Aço Carbono A350 LF2'),
    ('A350 LF2',       'Aço Carbono A350 LF2'),
    ('LF2',            'Aço Carbono A350 LF2'),
    ('A-105',          'Aço Carbono A105'),
    ('A105',           'Aço Carbono A105'),
    ('GAVALNIZADO',    'Aço Carbono Galvanizado'),  # typo real no banco
    ('GALVANIZADO',    'Aço Carbono Galvanizado'),

    # ── Ferros Fundidos ───────────────────────────────────────────────────
    ('A-536',          'Ferro Fundido Nodular A536'),
    ('A536',           'Ferro Fundido Nodular A536'),
    ('GG25',           'Ferro Fundido Nodular GG25'),
    ('A-126',          'Ferro Fundido Cinza A126'),
    ('A126',           'Ferro Fundido Cinza A126'),
    ('FERRO FUNDIDO',  'Ferro Fundido Cinza A126'),  # genérico → mais comum no BR

    # ── Não-ferrosos ──────────────────────────────────────────────────────
    ('LATÃO',          'Latão'),
    ('LATAO',          'Latão'),
    ('BRONZE',         'Bronze'),
    ('ALUMÍNIO',       'Alumínio'),
    ('ALUMINIO',       'Alumínio'),

    # ── Polímeros (CPVC/PVDF/PTFE antes de PVC) ───────────────────────────
    ('CPVC',           'CPVC'),
    ('PVDF',           'PVDF'),
    ('PTFE',           'PTFE'),
    ('PVC',            'PVC'),
    ('EPDM',           'Borracha EPDM'),
    ('NBR',            'Borracha NBR'),
    ('SILICONE',       'Silicone'),
]

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

# Regex para detectar "ACO CARBONO" / "AÇO CARBONO" de forma genérica.
_RE_ACO_CARBONO = re.compile(r'\b(?:A[CÇ]O|ACO)\s+CARBONO\b')

# Regex para detectar "PP" como palavra isolada (ambíguo: Polipropileno x Passagem Plena).
_RE_PP = re.compile(r'\bPP\b')

# Sentinela: sem match *intencional* (material conhecido mas não cadastrado).
_SEM_MATCH_INT = '__SEM_MATCH_INTENCIONAL__'


def _inferir_material(descricao: str) -> str | None:
    """Retorna o material canônico, _SEM_MATCH_INT, ou None.

    Prioridade:
      1. Regras contextuais ACO CARBONO (VALVULA → WCB, TUBO → sentinela, genérico → A105).
      2. MAPA_INFERENCIA (busca por substring).
      3. None (sem match).
    """
    upper = descricao.upper()

    # 1. Regras contextuais para "ACO CARBONO" / "AÇO CARBONO" genérico.
    #    Estas têm prioridade sobre o MAPA_INFERENCIA para evitar que
    #    WCB/A-105 presentes na descrição sobrescrevam a lógica contextual.
    if _RE_ACO_CARBONO.search(upper):
        if 'VALVULA' in upper or 'VÁLVULA' in upper:
            return 'Aço Carbono A216 WCB'   # válvula = peça fundida
        if 'TUBO' in upper:
            return _SEM_MATCH_INT           # A-106 — não está no catálogo
        return 'Aço Carbono A105'           # fitting forjado (fallback)

    # 2. Mapa específico.
    for substring, material in MAPA_INFERENCIA:
        if substring in upper:
            return material

    return None


def _tem_pp_ambiguo(descricao: str) -> bool:
    """True se a descrição contém 'PP' como palavra isolada."""
    return bool(_RE_PP.search(descricao.upper()))


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        'Infere FamiliaProduto.material_base a partir de descricao_base '
        '(dry-run por padrão).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Persiste as alterações no banco via .update() em batch.',
        )
        parser.add_argument(
            '--apenas-sem-match',
            action='store_true',
            default=False,
            dest='apenas_sem_match',
            help='Exibe apenas famílias sem match (para revisão manual).',
        )

    def handle(self, *args, **opts):
        apply: bool = opts['apply']
        apenas_sem_match: bool = opts['apenas_sem_match']
        mode = 'APPLY' if apply else 'DRY-RUN'

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'=== inferir_material_familias [{mode}] ==='
        ))
        self.stdout.write('')

        familias = list(
            FamiliaProduto.objects
            .only('id', 'codigo_figura', 'descricao_base', 'material_base')
            .order_by('codigo_figura')
        )
        total = len(familias)

        # ------------------------------------------------------------------
        # Classificação
        # ------------------------------------------------------------------
        por_material: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
        sem_match_real: list[tuple[int, str, str]] = []          # sem padrão
        sem_match_int: list[tuple[int, str, str]] = []           # A-106, etc.
        ambiguos: list[tuple[int, str, str, str]] = []           # PP ambíguo
        ja_preenchidos: list[tuple[int, str, str, str]] = []     # preservar

        for fam in familias:
            desc = (fam.descricao_base or '').strip()
            atual = (fam.material_base or '').strip()

            if atual:
                ja_preenchidos.append((fam.id, fam.codigo_figura or '', desc, atual))
                continue

            # PP ambíguo avaliado primeiro para não mascarar outros matches.
            if _tem_pp_ambiguo(desc):
                resultado = _inferir_material(desc)
                if resultado and resultado != _SEM_MATCH_INT:
                    # Tem match claro + PP presente → aceita o match, avisa sobre PP
                    por_material[resultado].append((fam.id, fam.codigo_figura or '', desc))
                else:
                    ambiguos.append((fam.id, fam.codigo_figura or '', desc, 'PP ambíguo'))
                continue

            resultado = _inferir_material(desc)
            if resultado is None:
                sem_match_real.append((fam.id, fam.codigo_figura or '', desc))
            elif resultado == _SEM_MATCH_INT:
                sem_match_int.append((fam.id, fam.codigo_figura or '', desc))
            else:
                por_material[resultado].append((fam.id, fam.codigo_figura or '', desc))

        # ------------------------------------------------------------------
        # Contagens
        # ------------------------------------------------------------------
        total_alterar   = sum(len(v) for v in por_material.values())
        n_sem_match     = len(sem_match_real)
        n_sem_match_int = len(sem_match_int)
        n_ambiguos      = len(ambiguos)
        n_ja            = len(ja_preenchidos)
        pct_sem_match   = (n_sem_match / total * 100) if total else 0

        # ------------------------------------------------------------------
        # Output
        # ------------------------------------------------------------------
        if not apenas_sem_match:
            # Materiais inferidos
            self.stdout.write(self.style.MIGRATE_HEADING('── Materiais inferidos ──'))
            self.stdout.write('')
            C_MAT, C_QTD = 32, 5
            self.stdout.write(
                f"  {'MATERIAL':<{C_MAT}}  {'QTD':>{C_QTD}}  EXEMPLOS (até 2 famílias)"
            )
            self.stdout.write('  ' + '─' * 90)
            for mat in sorted(por_material):
                rows = por_material[mat]
                ex = ' | '.join(
                    f'{r[1]}: "{r[2][:42]}{"…" if len(r[2])>42 else ""}"'
                    for r in rows[:2]
                )
                self.stdout.write(f"  {mat:<{C_MAT}}  {len(rows):>{C_QTD}}  {ex}")
            self.stdout.write('')

            # Casos a revisar (sem match intencional)
            if sem_match_int:
                self.stdout.write(self.style.WARNING(
                    f'── Casos a revisar — material não cadastrado ({n_sem_match_int}) ──'
                ))
                self.stdout.write(
                    '  (ex: tubos ACO CARBONO → A-106, que não está no catálogo)'
                )
                for _id, cod, desc in sem_match_int:
                    self.stdout.write(f"  {cod:<14}  {desc}")
                self.stdout.write('')

            # Já preenchidos
            if ja_preenchidos:
                self.stdout.write(self.style.WARNING(
                    f'── Já preenchidos (preservados — {n_ja}) ──'
                ))
                for _id, cod, desc, atual in ja_preenchidos[:20]:
                    self.stdout.write(
                        f"  {cod:<14}  atual={atual!r:<28}  {desc[:48]}"
                    )
                if n_ja > 20:
                    self.stdout.write(f"  … e mais {n_ja - 20} famílias.")
                self.stdout.write('')

            # Ambíguos
            if ambiguos:
                self.stdout.write(self.style.WARNING(
                    f'── Ambíguos (não alterados — {n_ambiguos}) ──'
                ))
                for _id, cod, desc, motivo in ambiguos:
                    self.stdout.write(f"  {cod:<14}  [{motivo}]  {desc[:60]}")
                self.stdout.write('')

        # Sem match real
        self.stdout.write(self.style.WARNING(
            f'── Sem match real (não alterados — {n_sem_match}) ──'
        ))
        if sem_match_real:
            for _id, cod, desc in sem_match_real:
                self.stdout.write(f"  {cod:<14}  {desc}")
        else:
            self.stdout.write('  (nenhuma) ✅')
        self.stdout.write('')

        # Resumo
        self.stdout.write('─' * 70)
        self.stdout.write(f'  Total famílias                   : {total}')
        self.stdout.write(f'  Já preenchidos (preservados)     : {n_ja}')
        self.stdout.write(f'  Serão preenchidos                : {total_alterar}')
        self.stdout.write(f'  Casos a revisar (mat. s/ cadastro): {n_sem_match_int}')
        self.stdout.write(f'  Ambíguos — PP                    : {n_ambiguos}')
        self.stdout.write(f'  Sem match real                   : {n_sem_match}  ({pct_sem_match:.1f}%)')
        self.stdout.write('')

        # ------------------------------------------------------------------
        # Guarda de segurança: >10% sem match real
        # ------------------------------------------------------------------
        if pct_sem_match > 10:
            self.stdout.write(self.style.ERROR(
                f'⚠  ALERTA: {pct_sem_match:.1f}% sem match real (> 10%).\n'
                '   Revise o mapa antes de aplicar.'
            ))
            if not apply:
                return

        if not apply:
            self.stdout.write(self.style.WARNING(
                'Dry-run concluído — nenhuma alteração feita.\n'
                'Execute com --apply para persistir.'
            ))
            return

        # ------------------------------------------------------------------
        # Aplicação — .update() em batch, sem disparar signals de auditoria
        # ------------------------------------------------------------------
        self.stdout.write(self.style.MIGRATE_HEADING('── Aplicando alterações ──'))
        self.stdout.write('')
        total_updated = 0
        with transaction.atomic():
            for mat, rows in sorted(por_material.items()):
                ids = [r[0] for r in rows]
                updated = (
                    FamiliaProduto.objects
                    .filter(id__in=ids)
                    .update(material_base=mat)
                )
                total_updated += updated
                self.stdout.write(f"  ✔  {mat:<35} → {updated} família(s)")

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído. {total_updated} famílias atualizadas.'
        ))
