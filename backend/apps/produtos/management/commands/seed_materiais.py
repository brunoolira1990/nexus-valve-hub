"""Popula o catálogo inicial de materiais (idempotente).

Usa get_or_create por `nome` — seguro para rodar múltiplas vezes.

Uso:
    python manage.py seed_materiais            # dry-run
    python manage.py seed_materiais --apply    # insere/atualiza no banco
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.produtos.material_models import Material

# ---------------------------------------------------------------------------
# Catálogo seed — 29 materiais
# Formato: (ordem, nome, nome_curto, categoria, norma_astm, ncm_sugerido, aliases)
# ---------------------------------------------------------------------------
SEED: list[tuple[int, str, str, str, str, str, list[str]]] = [
    # ── Aços Carbono ────────────────────────────────────────────────────────
    (1,  'Aço Carbono A105',        'A105',          'ACO_CARBONO', 'ASTM A105',          '7307.99.00', ['A105', 'A-105', 'SA105']),
    (2,  'Aço Carbono A216 WCB',    'WCB',           'ACO_CARBONO', 'ASTM A216 WCB',      '8481.80.99', ['WCB', 'A-216 WCB', 'A216-WCB']),
    (3,  'Aço Carbono A234 WPB',    'WPB',           'ACO_CARBONO', 'ASTM A234 WPB',      '7307.19.90', ['WPB', 'A234 WPB']),
    (4,  'Aço Carbono A350 LF2',    'LF2',           'ACO_CARBONO', 'ASTM A350 LF2',      '7307.99.00', ['LF2', 'A350 LF2', 'A-350 LF2']),
    (5,  'Aço Carbono Galvanizado', 'Galv.',         'ACO_CARBONO', 'NBR 6323/A153',      '7307.19.10', ['GALVANIZADO', 'GALV', 'GAVALNIZADO']),
    # ── Aços Inox ───────────────────────────────────────────────────────────
    (6,  'Aço Inox 304',            '304',           'ACO_INOX', 'ASTM A182 F304/AISI 304/CF8',  '7307.22.00', ['304', 'F304', 'AISI 304', 'CF8', 'INOX 304', 'ACO INOX 304']),
    (7,  'Aço Inox 304L',           '304L',          'ACO_INOX', 'ASTM A182 F304L/CF3',          '7307.22.00', ['304L', 'F304L', 'AISI 304L', 'CF3']),
    (8,  'Aço Inox 316',            '316',           'ACO_INOX', 'ASTM A182 F316/AISI 316/CF8M', '7307.23.00', ['316', 'F316', 'AISI 316', 'CF8M', 'INOX 316']),
    (9,  'Aço Inox 316L',           '316L',          'ACO_INOX', 'ASTM A182 F316L/CF3M',         '7307.23.00', ['316L', 'F316L', 'AISI 316L', 'CF3M', 'INOX 316L']),
    # ── Ferros Fundidos ─────────────────────────────────────────────────────
    (10, 'Ferro Fundido Cinza A126',     'Cinza',         'FERRO_FUNDIDO', 'ASTM A126',                '8481.80.93', ['A126', 'A-126', 'FERRO FUNDIDO']),
    (11, 'Ferro Fundido Nodular A536',   'Nodular A536',  'FERRO_FUNDIDO', 'ASTM A536',                '8481.80.99', ['A536', 'A-536', 'NODULAR']),
    (12, 'Ferro Fundido Nodular GG25',   'GG25',          'FERRO_FUNDIDO', 'DIN GG25/EN-GJL-250',      '8481.80.99', ['GG25', 'GG-25', 'GJL-250']),
    (13, 'Ferro Fundido Maleável',       'Maleável',      'FERRO_FUNDIDO', 'NBR 6590/ISO 5922/ASTM A197','7307.19.10', ['MALEAVEL', 'MALAVEL', 'FERRO MALEAVEL']),
    (14, 'Ferro Fundido Maleável Galv.', 'Maleável Galv.','FERRO_FUNDIDO', 'NBR 6590 + ASTM A153',     '7307.19.10', ['FERRO GALVANIZADO', 'MALEAVEL GALV']),
    # ── Aços Liga ───────────────────────────────────────────────────────────
    (15, 'Aço Liga F11', 'F11', 'ACO_LIGA', 'ASTM A182 F11', '7307.99.00', ['F11', 'A182 F11', '1.25CR']),
    (16, 'Aço Liga F22', 'F22', 'ACO_LIGA', 'ASTM A182 F22', '7307.99.00', ['F22', 'A182 F22', '2.25CR']),
    (17, 'Aço Liga F91', 'F91', 'ACO_LIGA', 'ASTM A182 F91', '7307.99.00', ['F91', 'A182 F91', '9CR']),
    # ── Não-ferrosos ────────────────────────────────────────────────────────
    (18, 'Bronze',   'Bronze',   'NAO_FERROSO', 'ASTM B62/B143/B147/B148', '8481.80.99', ['BRONZE', 'B62', 'B148']),
    (19, 'Latão',    'Latão',    'NAO_FERROSO', 'ASTM B16/B584',           '7412.20.00', ['LATAO', 'LATÃO', 'BRASS']),
    (20, 'Alumínio', 'Alumínio', 'NAO_FERROSO', 'ASTM B26/B108',           '7609.00.00', ['ALUMINIO', 'ALUMÍNIO']),
    # ── Polímeros ───────────────────────────────────────────────────────────
    (21, 'PVC',                'PVC',      'POLIMERO', '',             '3917.23.00', ['PVC']),
    (22, 'CPVC',               'CPVC',     'POLIMERO', 'ASTM F441',    '3917.23.00', ['CPVC']),
    (23, 'PP (Polipropileno)', 'PP',       'POLIMERO', 'ASTM F2389',   '3917.22.00', ['PP', 'POLIPROPILENO']),
    (24, 'PVDF',               'PVDF',     'POLIMERO', 'ASTM F2389',   '3917.23.00', ['PVDF']),
    (25, 'PTFE',               'PTFE',     'POLIMERO', '',             '3917.23.00', ['PTFE', 'TEFLON']),
    (26, 'Borracha EPDM',      'EPDM',     'POLIMERO', 'ASTM D2000',   '4009.31.00', ['EPDM', 'BORRACHA EPDM']),
    (27, 'Borracha NBR',       'NBR',      'POLIMERO', 'ASTM D2000',   '4009.31.00', ['NBR', 'BUNA-N', 'BORRACHA NBR']),
    (28, 'Silicone',           'Silicone', 'POLIMERO', 'ASTM D2000',   '3910.00.00', ['SILICONE', 'SILICON']),
    # ── Outro ───────────────────────────────────────────────────────────────
    (29, 'Outro', 'Outro', 'OUTRO', '', '', []),
    # ── Adicionados na extensão do Bloco 3 ──────────────────────────────────
    (30, 'Aço Carbono A106',    'A106', 'ACO_CARBONO', 'ASTM A106 Gr.B', '7304.19.00', ['A106', 'A-106', 'ASTM A106', 'API 5L']),
    (31, 'PP (Polipropileno)',  'PP',   'POLIMERO',    'ASTM F2389',     '3917.22.00', ['PP', 'POLIPROPILENO']),
]


class Command(BaseCommand):
    help = 'Popula o catálogo inicial de materiais (idempotente, dry-run por padrão)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Persiste os materiais no banco. Sem esta flag executa dry-run.',
        )

    def handle(self, *args, **opts):
        apply: bool = opts['apply']
        mode = 'APPLY' if apply else 'DRY-RUN'

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'=== seed_materiais [{mode}] ==='))
        self.stdout.write('')

        col_ord  = 4
        col_nome = 32
        col_cat  = 14
        col_acao = 10

        header = (
            f"  {'ORD':>{col_ord}}  "
            f"{'NOME':<{col_nome}}  "
            f"{'CATEGORIA':<{col_cat}}  "
            f"{'AÇÃO':<{col_acao}}"
        )
        self.stdout.write(header)
        self.stdout.write('  ' + '-' * (col_ord + col_nome + col_cat + col_acao + 8))

        criados   = 0
        existentes = 0
        erros      = 0

        for ordem, nome, nome_curto, categoria, norma_astm, ncm_sugerido, aliases in SEED:
            acao = '(dry-run)'

            if apply:
                try:
                    _obj, created = Material.objects.get_or_create(
                        nome=nome,
                        defaults={
                            'nome_curto': nome_curto,
                            'categoria': categoria,
                            'norma_astm': norma_astm,
                            'ncm_sugerido': ncm_sugerido,
                            'aliases': aliases,
                            'ordem': ordem,
                            'ativo': True,
                        },
                    )
                    if created:
                        criados += 1
                        acao = self.style.SUCCESS('CRIADO')
                    else:
                        existentes += 1
                        acao = 'já existe'
                except Exception as exc:
                    erros += 1
                    acao = self.style.ERROR(f'ERRO: {exc}')
            else:
                exists = Material.objects.filter(nome=nome).exists()
                if exists:
                    existentes += 1
                    acao = 'já existe'
                else:
                    criados += 1
                    acao = self.style.SUCCESS('será CRIADO')

            linha = (
                f"  {ordem:>{col_ord}}  "
                f"{nome:<{col_nome}}  "
                f"{categoria:<{col_cat}}  "
                f"{acao}"
            )
            self.stdout.write(linha)

        self.stdout.write('')
        self.stdout.write('─' * 60)
        if apply:
            self.stdout.write(
                self.style.SUCCESS(f'  Criados: {criados}  |  Já existiam: {existentes}  |  Erros: {erros}')
            )
            total = Material.objects.count()
            self.stdout.write(f'  Material.objects.count() = {total}')
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'  Serão criados: {criados}  |  Já existem: {existentes}\n'
                    f'  Execute com --apply para persistir.'
                )
            )
        self.stdout.write('')
