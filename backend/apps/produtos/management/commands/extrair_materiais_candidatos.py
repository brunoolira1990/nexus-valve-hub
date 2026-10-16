"""Extrai candidatos a materiais das descrições de FamiliaProduto e Produto.

Somente leitura — não altera nada no banco.

Uso:
    python manage.py extrair_materiais_candidatos
    python manage.py extrair_materiais_candidatos --min-freq 2
    python manage.py extrair_materiais_candidatos --sem-material
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import NamedTuple

from django.core.management.base import BaseCommand

from apps.produtos.models import FamiliaProduto, Produto

# ---------------------------------------------------------------------------
# Padrões de extração (aplicados em ordem, maior especificidade primeiro)
# ---------------------------------------------------------------------------

# Grades ASTM de Aço Carbono (aceita hífen opcional e espaços)
_ASTM_CARBONO = re.compile(
    r'\b(A[-\s]?105|A[-\s]?182|A[-\s]?216\s*WCB?|A[-\s]?350\s*LF\d*|A[-\s]?126|'
    r'A[-\s]?536|A[-\s]?48|A[-\s]?193|A[-\s]?194|A[-\s]?234|A[-\s]?106|A[-\s]?53'
    r')\b',
    re.IGNORECASE,
)

# Grades de Ferro Fundido
_FERRO_FUNDIDO = re.compile(
    r'\b(FERRO\s+FUNDIDO(?:\s+(?:NODULAR|CINZENTO|MALEÁVEL))?'
    r'|GG[-\s]?\d{1,2}|GGG[-\s]?\d{1,2}|NODULAR(?:\s+GGG[-\s]?\d{1,2})?'
    r'|CAST\s+IRON)\b',
    re.IGNORECASE,
)

# Aço Inox com número de liga (304, 316, etc.) — deve vir ANTES do genérico INOX
_INOX_LIGA = re.compile(
    r'\b(?:ACO|AÇO|A[CÇ]O)\s+INOX(?:IDAVEL|IDÁVEL)?\s*'
    r'(3(?:0[46]L?|1[67]L?|17L|04H)|904L|2205|2507|310S?|321|347|'
    r'CF\s*8M?|CF\s*3M?|CN7M)\b',
    re.IGNORECASE,
)

# Aço Inox com código de fundição ASTM
_INOX_FUNDIDO = re.compile(
    r'\b(CF[-\s]?8M?|CF[-\s]?3M?|CN[-\s]?7M|CK[-\s]?20|HK[-\s]?40)\b',
    re.IGNORECASE,
)

# Aço Inox genérico (sem número de liga)
_INOX_GENERICO = re.compile(
    r'\b(?:ACO|AÇO|A[CÇ]O)\s+INOX(?:IDAVEL|IDÁVEL)?\b',
    re.IGNORECASE,
)

# Aço Liga (F11, F22, F91, P91, P22, ...)
_ACO_LIGA = re.compile(
    r'\b(?:ACO|AÇO|A[CÇ]O)\s+LIGA\b'
    r'|\b(?:CROMO[-\s]MOLIBDENIO|CROMO[-\s]MOLIBDÊNIO)\b'
    r'|\b(F[-\s]?(?:11|22|91)|P[-\s]?(?:91|22)|T[-\s]?(?:91|22))\b',
    re.IGNORECASE,
)

# Aço Carbono com possíveis qualificadores
_ACO_CARBONO = re.compile(
    r'\b(?:ACO|AÇO|A[CÇ]O)\s+CARBONO(?:\s+(?:GALVANIZADO|GALVANISADO|ZINCADO|ELETROZINCADO))?\b'
    r'|\b(?:ACO|AÇO|A[CÇ]O)\s+(?:GALVANIZADO|GALVANISADO|ZINCADO)\b',
    re.IGNORECASE,
)

# Bronze
_BRONZE = re.compile(
    r'\bBRONZE(?:\s+(?:TM[-\s]?\d+|SAE[-\s]?\d+|FOSFORO|SILÍCIO|SILICIO|MANGANÊS|MANGANES))?\b',
    re.IGNORECASE,
)

# Latão
_LATAO = re.compile(
    r'\bLAT[AÃ]O(?:\s+(?:FORJADO|BSP|FUNDIDO))?\b',
    re.IGNORECASE,
)

# Alumínio
_ALUMINIO = re.compile(
    r'\bALUM[IÍ]NIO(?:\s+(?:FUNDIDO|FORJADO|ANODIZADO|\d{4}))?\b',
    re.IGNORECASE,
)

# Polímeros e elastômeros
_POLIMEROS = re.compile(
    r'\b(PVC|CPVC|PP[-\s]?R?|PVDF|PTFE|EPDM|NBR|VITON|FKM|SILICONE|BORRACHA|'
    r'NYLON|PA[-\s]?6|PA[-\s]?66|POLIETILENO|POLIPROPILENO|POLIACETAL|POM|PEEK|'
    r'ABS|ACETAL|DELRIN)\b',
    re.IGNORECASE,
)

# Titânio, Duplex, Hastelloy, Inconel, Monel
_ESPECIAIS = re.compile(
    r'\b(TIT[AÂ]NIO|DUPLEX|SUPER[-\s]?DUPLEX|HASTELLOY\s*[A-Z]\d*|'
    r'INCONEL\s*\d*|MONEL\s*\d*|STELLITE|TUNGST[EÊ]NIO)\b',
    re.IGNORECASE,
)

# Ordem de aplicação dos padrões: (regex, rótulo-base)
# O rótulo-base é complementado com o grupo capturado (se houver)
PADROES: list[tuple[re.Pattern, str]] = [
    (_INOX_LIGA,       'Aço Inox'),        # específico antes do genérico
    (_INOX_FUNDIDO,    'Aço Inox fundido'),
    (_INOX_GENERICO,   'Aço Inox'),
    (_ASTM_CARBONO,    'Aço Carbono ASTM'),
    (_ACO_LIGA,        'Aço Liga'),
    (_ACO_CARBONO,     'Aço Carbono'),
    (_FERRO_FUNDIDO,   'Ferro Fundido'),
    (_BRONZE,          'Bronze'),
    (_LATAO,           'Latão'),
    (_ALUMINIO,        'Alumínio'),
    (_POLIMEROS,       'Polímero'),
    (_ESPECIAIS,       'Liga especial'),
]

# ---------------------------------------------------------------------------
# Palavras-ruído a ignorar no texto (maiúsculas, mas não são materiais)
# ---------------------------------------------------------------------------
_RUIDO = frozenset({
    'TUBO', 'VALVULA', 'VÁLVULA', 'CONEXAO', 'CONEXÃO', 'FLANGE', 'CURVA',
    'JOELHO', 'TE', 'CAP', 'NIPLE', 'NIPPLE', 'BUCHA', 'UNION', 'UNIAO',
    'REGISTRO', 'COTOVELO', 'REDUCAO', 'REDUÇÃO', 'ADAPTADOR', 'ESPIGAO',
    'ESPIGÃO', 'LUVA', 'TAMPA', 'PLUG', 'REDUTOR', 'MACHO', 'FÊMEA', 'FEMEA',
    'SOLDAVEL', 'SOLDÁVEL', 'ROSCAVEL', 'ROSCÁVEL', 'SOLDADO', 'ROSCADO',
    'RETO', 'CURTO', 'LONGO', 'SERIE', 'SÉRIE', 'CLASSE', 'CLASS',
    'ANSI', 'ASME', 'DIN', 'NBR', 'ISO', 'ASTM', 'API', 'ABNT',
    'SCH', 'XS', 'XXS', 'STD', 'EXTRA', 'PESADO', 'LEVE',
    'MM', 'KG', 'MT', 'PC', 'UN', 'BAR', 'PSI',
    'SEM', 'COM', 'PARA', 'POR', 'DE', 'DA', 'DO', 'EM', 'NA', 'NO',
    'SC', 'S/C',
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalizar_match(rotulo: str, m: re.Match) -> str:
    """Combina rótulo-base com o texto capturado (uppercase limpo)."""
    texto = m.group(0).upper().strip()
    # Remove espaços extras internos
    texto = re.sub(r'\s+', ' ', texto)
    return texto


def _extrair_da_descricao(descricao: str) -> list[str]:
    """Retorna todos os materiais encontrados (pode ser mais de um por descrição)."""
    texto = descricao.upper()
    encontrados: list[str] = []
    posicoes_usadas: set[int] = set()

    for padrao, _rotulo in PADROES:
        for m in padrao.finditer(texto):
            inicio = m.start()
            # Evita capturar sobreposto com match anterior
            if any(inicio >= p[0] and inicio < p[1] for p in (
                (u, u + 1) for u in posicoes_usadas
            )):
                continue
            # Marca os caracteres deste match como usados
            for i in range(m.start(), m.end()):
                posicoes_usadas.add(i)
            encontrados.append(_normalizar_match(_rotulo, m))

    return encontrados


class Candidato(NamedTuple):
    material: str
    freq: int
    exemplos: list[str]


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Extrai candidatos a materiais das descrições (somente leitura)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-freq',
            type=int,
            default=1,
            metavar='N',
            help='Exibe apenas candidatos com frequência >= N (padrão: 1)',
        )
        parser.add_argument(
            '--sem-material',
            action='store_true',
            default=False,
            help='Exibe descrições sem material identificado',
        )

    def handle(self, *args, **opts):
        min_freq: int = opts['min_freq']
        mostrar_sem_material: bool = opts['sem_material']

        # ------------------------------------------------------------------
        # Coleta descrições
        # ------------------------------------------------------------------
        familias_qs = FamiliaProduto.objects.only('id', 'descricao_base').iterator(chunk_size=200)
        produtos_qs = Produto.objects.only('id', 'descricao').iterator(chunk_size=500)

        descricoes: list[tuple[str, str]] = []  # (fonte, texto)

        for fam in familias_qs:
            txt = (fam.descricao_base or '').strip()
            if txt:
                descricoes.append(('familia', txt))

        vistos: set[str] = set()
        for prod in produtos_qs:
            txt = (prod.descricao or '').strip()
            if txt and txt not in vistos:
                vistos.add(txt)
                descricoes.append(('produto', txt))

        total_analisadas = len(descricoes)

        # ------------------------------------------------------------------
        # Extração
        # ------------------------------------------------------------------
        # freq_map: material → {exemplos (até 5 únicos), contagem}
        freq_map: dict[str, dict] = defaultdict(lambda: {'freq': 0, 'exemplos': []})
        sem_material: list[str] = []
        total_ocorrencias = 0

        for _fonte, txt in descricoes:
            encontrados = _extrair_da_descricao(txt)
            if encontrados:
                total_ocorrencias += len(encontrados)
                for mat in encontrados:
                    freq_map[mat]['freq'] += 1
                    if len(freq_map[mat]['exemplos']) < 2:
                        freq_map[mat]['exemplos'].append(txt)
            else:
                sem_material.append(txt)

        # ------------------------------------------------------------------
        # Ordena por frequência descendente
        # ------------------------------------------------------------------
        candidatos = sorted(
            freq_map.items(),
            key=lambda x: -x[1]['freq'],
        )
        candidatos_filtrados = [(mat, d) for mat, d in candidatos if d['freq'] >= min_freq]

        # ------------------------------------------------------------------
        # Output
        # ------------------------------------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== MATERIAIS CANDIDATOS ==='))
        self.stdout.write('')

        col_freq  = 6
        col_mat   = 40
        col_ex    = 60

        header = (
            f"  {'FREQ':>{col_freq}}  "
            f"{'MATERIAL':<{col_mat}}  "
            f"{'EXEMPLOS (até 2)':<{col_ex}}"
        )
        separator = '  ' + '-' * (col_freq + 2 + col_mat + 2 + col_ex)

        self.stdout.write(header)
        self.stdout.write(separator)

        for mat, d in candidatos_filtrados:
            freq = d['freq']
            exemplos_txt = ' | '.join(
                f'"{ex[:55]}{"…" if len(ex) > 55 else ""}"'
                for ex in d['exemplos']
            )
            linha = (
                f"  {freq:>{col_freq}}  "
                f"{mat!r:<{col_mat}}  "
                f"{exemplos_txt}"
            )
            self.stdout.write(linha)

        if not candidatos_filtrados:
            self.stdout.write('  (nenhum candidato encontrado)')

        # ------------------------------------------------------------------
        # Estatísticas
        # ------------------------------------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== ESTATÍSTICAS ==='))
        self.stdout.write('')
        self.stdout.write(f'  Total descrições analisadas : {total_analisadas}')
        self.stdout.write(f'  Ocorrências de padrão       : {total_ocorrencias}')
        self.stdout.write(f'  Candidatos únicos           : {len(candidatos)}')
        self.stdout.write(f'  Candidatos exibidos (≥{min_freq:2d})   : {len(candidatos_filtrados)}')
        self.stdout.write(f'  Sem material identificado   : {len(sem_material)}')

        if mostrar_sem_material or opts.get('sem_material'):
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    f'--- Descrições SEM material identificado ({len(sem_material)}) ---'
                )
            )
            for txt in sem_material:
                self.stdout.write(f'  · {txt}')

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('Concluído — nenhuma alteração no banco.')
        )
