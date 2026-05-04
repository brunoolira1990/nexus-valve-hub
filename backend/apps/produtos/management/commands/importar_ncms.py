from __future__ import annotations

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.produtos.models import Ncm


COLUMN_ALIASES = {
    'codigo': {'ncm', 'codigo', 'código', 'codigo_ncm', 'ncm_codigo'},
    'descricao': {'descricao', 'descrição', 'descricao_ncm', 'descrição_ncm'},
    'ex_tipi': {'ex', 'ex_tipi', 'extipi'},
    'aliquota_ipi': {'aliquota_ipi', 'alíquota_ipi', 'aliquota ipi', 'alíquota ipi', 'ipi'},
    'vigencia_inicio': {'vigencia_inicio', 'vigência_inicio', 'vigencia inicio', 'vigência início'},
    'vigencia_fim': {'vigencia_fim', 'vigência_fim', 'vigencia fim', 'vigência fim'},
    'observacoes': {'observacoes', 'observações', 'obs'},
}


def _norm_header(value: str) -> str:
    return (
        (value or '')
        .strip()
        .lower()
        .replace('-', '_')
        .replace('/', '_')
    )


def _normalize_codigo(raw: str) -> str:
    clean = ''.join(ch for ch in (raw or '') if ch.isdigit())
    return clean


def _to_upper(raw: str) -> str:
    return (raw or '').strip().upper()


def _parse_decimal(raw: str):
    txt = (raw or '').strip()
    if not txt:
        return None
    txt = txt.replace('%', '').replace(' ', '').replace(',', '.')
    try:
        return Decimal(txt)
    except InvalidOperation:
        return None


def _parse_date(raw: str):
    txt = (raw or '').strip()
    if not txt:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_spaces(raw: str) -> str:
    return re.sub(r'\s+', ' ', (raw or '').strip())


def _extract_ex_tipi(raw: str) -> str:
    txt = _to_upper(raw)
    if not txt:
        return ''
    m = re.search(r'\bEX[\s\-]*(\d{1,3})\b', txt)
    if not m:
        return ''
    return f'EX {m.group(1).zfill(2)}'


def _extract_aliquota_from_text(raw: str):
    txt = _to_upper(raw)
    if not txt:
        return None
    if txt in {'NT', 'N.T', 'N/T', '-', 'ISENTO'}:
        return None
    m_ipi = re.search(r'\bIPI\b\s*[:\-]?\s*(NT|N\.T|N/T|-|ISENTO|\d{1,2}(?:[.,]\d{1,2})?)\s*%?', txt)
    if m_ipi:
        valor = m_ipi.group(1)
        if valor in {'NT', 'N.T', 'N/T', '-', 'ISENTO'}:
            return None
        return _parse_decimal(valor)
    return None


def _clean_pdf_descricao(raw: str) -> str:
    txt = _normalize_spaces(_to_upper(raw))
    if not txt:
        return ''
    txt = re.sub(r'\bEX[\s\-]*\d{1,3}\b', ' ', txt)
    txt = re.sub(r'\bIPI\b\s*[:\-]?\s*(NT|N\.T|N/T|-|ISENTO|\d{1,2}(?:[.,]\d{1,2})?)\s*%?', ' ', txt)
    txt = re.sub(r'\b(NT|N\.T|N/T)\b$', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip(' -;,.')
    return txt


def _fit_len(raw: str, max_len: int) -> str:
    txt = (raw or '').strip()
    if len(txt) <= max_len:
        return txt
    return txt[:max_len].rstrip()


class Command(BaseCommand):
    help = 'Importa lista mestre de NCM (CSV, TXT, XLSX ou PDF) de forma idempotente.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', type=str, help='Caminho do arquivo de importação.')
        parser.add_argument('--fonte', type=str, default='', help='Fonte dos dados (ex.: TIPI).')
        parser.add_argument('--desativar-ausentes', action='store_true', help='Desativa NCMs não presentes no arquivo.')
        parser.add_argument('--dry-run', action='store_true', help='Simula importação sem gravar.')
        parser.add_argument('--diagnosticar', action='store_true', help='Mostra diagnóstico detalhado do arquivo sem gravar.')
        parser.add_argument(
            '--confirmar-pdf',
            action='store_true',
            help='Confirma importação de PDF sem dry-run prévio (use com cautela).',
        )

    def _read_rows_csv_or_txt(self, path: Path):
        with path.open('r', encoding='utf-8-sig', newline='') as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=';,|\t,')
            except csv.Error:
                dialect = csv.excel
                dialect.delimiter = ';'
            reader = csv.DictReader(f, dialect=dialect)
            return list(reader)

    def _read_rows_xlsx(self, path: Path):
        try:
            from openpyxl import load_workbook
        except Exception as exc:  # noqa: BLE001
            raise CommandError('Para importar XLSX, instale openpyxl no backend.') from exc
        wb = load_workbook(filename=path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], {'formato': 'XLSX', 'amostras': [], 'suspeitas': ['Planilha vazia.']}

        header_idx = None
        col_codigo = None
        col_ex = None
        col_descricao = None
        col_ipi = None

        for ridx, row in enumerate(rows[:120]):
            normalized = [_norm_header(str(v or '')) for v in row]
            for cidx, val in enumerate(normalized):
                if val in COLUMN_ALIASES['codigo']:
                    col_codigo = cidx
                elif val in COLUMN_ALIASES['ex_tipi']:
                    col_ex = cidx
                elif val in COLUMN_ALIASES['descricao']:
                    col_descricao = cidx
                elif val in COLUMN_ALIASES['aliquota_ipi']:
                    col_ipi = cidx
            if col_codigo is not None and col_descricao is not None:
                header_idx = ridx
                break

        if header_idx is None:
            # fallback TIPI oficial
            header_idx = 0
            col_codigo, col_ex, col_descricao, col_ipi = 0, 1, 2, 3

        out = []
        amostras = []
        suspeitas = []
        ignored_reasons = {
            'linha_vazia': 0,
            'sem_codigo': 0,
            'codigo_incompleto_ou_invalido': 0,
            'sem_descricao': 0,
            'linha_hierarquica_sem_ncm_completo': 0,
        }
        ignored_samples = []

        for line_no, line in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            cells = [line[idx] if idx < len(line) else None for idx in range(max(col_codigo, col_descricao, col_ex or 0, col_ipi or 0) + 1)]
            if not any(v not in (None, '') for v in cells):
                ignored_reasons['linha_vazia'] += 1
                continue

            raw_codigo = str(line[col_codigo] if col_codigo is not None and col_codigo < len(line) else '' or '')
            raw_desc = str(line[col_descricao] if col_descricao is not None and col_descricao < len(line) else '' or '')
            raw_ex = str(line[col_ex] if col_ex is not None and col_ex < len(line) else '' or '')
            raw_ipi = str(line[col_ipi] if col_ipi is not None and col_ipi < len(line) else '' or '')

            codigo = _normalize_codigo(raw_codigo)
            descricao = _normalize_spaces(raw_desc)
            if not raw_codigo.strip() and not descricao:
                ignored_reasons['linha_vazia'] += 1
                continue
            if not raw_codigo.strip():
                ignored_reasons['sem_codigo'] += 1
                if len(ignored_samples) < 15:
                    ignored_samples.append(f'Linha {line_no}: sem código | valores={line}')
                continue
            if len(codigo) != 8:
                # TIPI tem níveis 2/4/6/7 dígitos e linhas de capítulo; ignorar sem erro.
                if 1 <= len(codigo) <= 7:
                    ignored_reasons['linha_hierarquica_sem_ncm_completo'] += 1
                else:
                    ignored_reasons['codigo_incompleto_ou_invalido'] += 1
                if len(ignored_samples) < 15:
                    ignored_samples.append(f'Linha {line_no}: código não é NCM 8 dígitos ({raw_codigo})')
                continue
            if not descricao:
                ignored_reasons['sem_descricao'] += 1
                if len(ignored_samples) < 15:
                    ignored_samples.append(f'Linha {line_no}: NCM {codigo} sem descrição')
                continue

            row = {
                'codigo': codigo,
                'descricao': _fit_len(_to_upper(descricao), 512),
                'ex_tipi': _extract_ex_tipi(raw_ex),
                'aliquota_ipi': str(_extract_aliquota_from_text(raw_ipi) or ''),
                '__origem_ref': f'Linha {line_no}',
            }
            out.append(row)
            if len(amostras) < 10:
                amostras.append(row)

        report = {
            'formato': 'XLSX',
            'sheet': ws.title,
            'sheetnames': wb.sheetnames,
            'header_idx': header_idx + 1,
            'header_map': {
                'codigo': col_codigo,
                'ex_tipi': col_ex,
                'descricao': col_descricao,
                'aliquota_ipi': col_ipi,
            },
            'rows_total': len(rows),
            'amostras': amostras,
            'suspeitas': suspeitas,
            'ignored_reasons': ignored_reasons,
            'ignored_samples': ignored_samples,
        }
        return out, report

    def _read_rows_pdf(self, path: Path):
        try:
            from pypdf import PdfReader
        except Exception as exc:  # noqa: BLE001
            raise CommandError('Para importar PDF, instale pypdf no backend.') from exc

        reader = PdfReader(str(path))
        if not reader.pages:
            raise CommandError('PDF sem páginas.')

        rows = []
        paginas_processadas = 0
        paginas_sem_texto = 0
        linhas_ignoradas = 0
        codigos_invalidos = 0
        descricoes_sem_codigo = 0
        aliquotas_nao_interpretadas = 0
        suspeitas: list[str] = []
        amostras: list[dict] = []
        regex_codigo = re.compile(r'(?<!\d)(\d{4}[.\s]?\d{2}[.\s]?\d{2}|\d{8})(?!\d)')

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ''
            paginas_processadas += 1
            if not text.strip():
                paginas_sem_texto += 1
                continue

            linhas = [ln.strip() for ln in text.splitlines() if ln and ln.strip()]
            for idx, ln in enumerate(linhas):
                m = regex_codigo.search(ln)
                if not m:
                    if re.search(r'(?<!\d)\d{2,6}(?!\d)', ln):
                        linhas_ignoradas += 1
                        suspeitas.append(f'Página {page_number}: código incompleto ignorado: {ln[:40]}')
                    elif len(ln) > 20 and not re.search(r'\d', ln):
                        descricoes_sem_codigo += 1
                    continue

                codigo_bruto = m.group(1)
                codigo = _normalize_codigo(codigo_bruto)
                if len(codigo) != 8:
                    codigos_invalidos += 1
                    suspeitas.append(f'Página {page_number}: NCM inválido extraído: {codigo_bruto}')
                    continue

                pos_final = m.end()
                desc_base = _normalize_spaces(ln[pos_final:])
                extra_parts = [desc_base] if desc_base else []
                lookahead = 1
                while lookahead <= 2 and idx + lookahead < len(linhas):
                    prox = linhas[idx + lookahead].strip()
                    if not prox or regex_codigo.search(prox):
                        break
                    if re.match(r'^(CAP[IÍ]TULO|SE[CÇ][AÃ]O|NOTAS?)\b', _to_upper(prox)):
                        break
                    extra_parts.append(prox)
                    lookahead += 1
                descricao = _clean_pdf_descricao(' '.join(extra_parts))
                if not descricao:
                    suspeitas.append(f'Página {page_number}: NCM {codigo} sem descrição associada.')
                    continue

                ex_tipi = _extract_ex_tipi(ln) or _extract_ex_tipi(descricao)
                aliquota_ipi = _extract_aliquota_from_text(ln)
                if aliquota_ipi is None:
                    aliquota_ipi = _extract_aliquota_from_text(descricao)
                if aliquota_ipi is None and re.search(r'\b(IPI|AL[IÍ]QUOTA)\b', _to_upper(ln + ' ' + descricao)):
                    aliquotas_nao_interpretadas += 1
                    suspeitas.append(f'Página {page_number}: alíquota não interpretada para NCM {codigo}.')

                row = {
                    'codigo': codigo,
                    'descricao': descricao,
                    'ex_tipi': ex_tipi,
                    'aliquota_ipi': str(aliquota_ipi) if aliquota_ipi is not None else '',
                    '__origem_ref': f'Página {page_number}',
                }
                rows.append(row)
                if len(amostras) < 10:
                    amostras.append(row)

        if paginas_sem_texto == paginas_processadas:
            raise CommandError(
                'Não foi possível extrair texto estruturado do PDF. Utilize o arquivo XLSX/CSV oficial ou um PDF com texto selecionável.',
            )
        if not rows:
            raise CommandError('Nenhum NCM válido de 8 dígitos foi encontrado no PDF.')

        total_suspeitas = linhas_ignoradas + codigos_invalidos + descricoes_sem_codigo
        if total_suspeitas >= 20 and (total_suspeitas / max(len(rows), 1)) > 0.30:
            raise CommandError(
                'Extração de PDF com baixa confiabilidade (mais de 30% de linhas suspeitas). '
                'Revise com --dry-run e prefira XLSX/CSV oficial.',
            )

        report = {
            'formato': 'PDF',
            'paginas_processadas': paginas_processadas,
            'paginas_sem_texto': paginas_sem_texto,
            'linhas_ignoradas': linhas_ignoradas,
            'codigos_invalidos': codigos_invalidos,
            'descricoes_sem_codigo': descricoes_sem_codigo,
            'aliquotas_nao_interpretadas': aliquotas_nao_interpretadas,
            'suspeitas': suspeitas,
            'amostras': amostras,
        }
        return rows, report

    def _map_row(self, row: dict):
        mapped = {}
        normalized = {_norm_header(k): v for k, v in row.items()}
        for target, aliases in COLUMN_ALIASES.items():
            found = None
            for alias in aliases:
                if alias in normalized:
                    found = normalized[alias]
                    break
            mapped[target] = found
        return mapped

    def _read_rows(self, path: Path):
        ext = path.suffix.lower()
        if ext in {'.csv', '.txt'}:
            return self._read_rows_csv_or_txt(path), {'formato': ext.upper().replace('.', ''), 'amostras': [], 'suspeitas': []}
        if ext in {'.xlsx'}:
            return self._read_rows_xlsx(path)
        if ext == '.pdf':
            return self._read_rows_pdf(path)
        raise CommandError(f'Formato não suportado: {ext}. Use CSV, TXT, XLSX ou PDF.')

    def handle(self, *args, **options):
        arquivo = Path(options['arquivo']).expanduser()
        if not arquivo.exists():
            raise CommandError(f'Arquivo não encontrado: {arquivo}')

        fonte = _to_upper(options.get('fonte') or '')
        dry_run = bool(options.get('dry_run'))
        diagnosticar = bool(options.get('diagnosticar'))
        desativar_ausentes = bool(options.get('desativar_ausentes'))
        confirmar_pdf = bool(options.get('confirmar_pdf'))
        ext = arquivo.suffix.lower()

        if ext == '.pdf' and not dry_run and not confirmar_pdf:
            raise CommandError(
                'Para importar PDF diretamente, execute primeiro com --dry-run ou use --confirmar-pdf após validar a prévia.',
            )

        rows, report = self._read_rows(arquivo)
        if not rows:
            raise CommandError('Arquivo sem linhas válidas para importação.')

        criados = 0
        atualizados = 0
        ignorados = 0
        erros: list[str] = []
        codigos_processados: set[str] = set()
        ignored_reasons_runtime = {
            'linha_vazia': 0,
            'sem_codigo': 0,
            'codigo_invalido': 0,
            'descricao_vazia': 0,
        }

        with transaction.atomic():
            for idx, row in enumerate(rows, start=2):
                data = self._map_row(row)
                codigo = _normalize_codigo(str(data.get('codigo') or ''))
                descricao = _to_upper(_normalize_spaces(str(data.get('descricao') or '')))
                if not codigo and not descricao:
                    ignorados += 1
                    ignored_reasons_runtime['linha_vazia'] += 1
                    continue
                if len(codigo) != 8:
                    erros.append(f'Linha {idx}: NCM inválido: {codigo or "vazio"}')
                    ignored_reasons_runtime['codigo_invalido'] += 1
                    continue
                if not descricao:
                    origem_ref = row.get('__origem_ref') or f'Linha {idx}'
                    erros.append(f'{origem_ref}: descrição vazia')
                    ignored_reasons_runtime['descricao_vazia'] += 1
                    continue

                payload = {
                    'descricao': _fit_len(descricao, 512),
                    'ex_tipi': _fit_len(_to_upper(str(data.get('ex_tipi') or '')), 16),
                    'aliquota_ipi': _parse_decimal(str(data.get('aliquota_ipi') or '')),
                    'vigencia_inicio': _parse_date(str(data.get('vigencia_inicio') or '')),
                    'vigencia_fim': _parse_date(str(data.get('vigencia_fim') or '')),
                    'observacoes': _fit_len(_to_upper(str(data.get('observacoes') or '')), 255),
                    'ativo': True,
                }
                if fonte:
                    payload['fonte'] = _fit_len(fonte, 64)

                obj, created = Ncm.objects.update_or_create(codigo=codigo, defaults=payload)
                _ = obj
                codigos_processados.add(codigo)
                if created:
                    criados += 1
                else:
                    atualizados += 1

            if desativar_ausentes and codigos_processados:
                Ncm.objects.exclude(codigo__in=list(codigos_processados)).update(ativo=False)

            if dry_run:
                transaction.set_rollback(True)

        if criados == 0 and atualizados == 0:
            if dry_run or diagnosticar:
                self.stdout.write(
                    self.style.WARNING(
                        'ALERTA: nenhum NCM válido foi importável. Verifique formato da planilha e relatório de ignorados.',
                    ),
                )
            else:
                raise CommandError(
                    'Nenhum NCM válido foi encontrado no arquivo. Verifique o formato da planilha ou execute com --diagnosticar/--dry-run.',
                )

        self.stdout.write('')
        self.stdout.write('Importação de NCM concluída.')
        self.stdout.write('')
        self.stdout.write(f'Arquivo: {arquivo.name}')
        self.stdout.write(f'Formato: {report.get("formato", ext.upper().replace(".", ""))}')
        self.stdout.write(f'Criados: {criados}')
        self.stdout.write(f'Atualizados: {atualizados}')
        self.stdout.write(f'Ignorados: {ignorados}')
        self.stdout.write(f'Erros: {len(erros)}')
        self.stdout.write(f'Registros encontrados: {len(rows)}')
        self.stdout.write(f'Fonte: {fonte or "NÃO INFORMADA"}')
        if dry_run:
            self.stdout.write('Modo: DRY-RUN (sem persistência)')
        if diagnosticar:
            self.stdout.write('Modo: DIAGNÓSTICO (sem persistência)')
        if report.get('formato') == 'XLSX':
            self.stdout.write(f'Aba processada: {report.get("sheet", "N/A")}')
            self.stdout.write(f'Abas no arquivo: {", ".join(report.get("sheetnames", []))}')
            self.stdout.write(f'Linha de cabeçalho detectada: {report.get("header_idx", "N/A")}')
            hm = report.get('header_map') or {}
            self.stdout.write(
                f'Mapeamento de colunas: codigo={hm.get("codigo")}, ex={hm.get("ex_tipi")}, descricao={hm.get("descricao")}, ipi={hm.get("aliquota_ipi")}',
            )
            ir = report.get('ignored_reasons') or {}
            self.stdout.write('Ignorados por motivo:')
            self.stdout.write(f'- linha vazia: {ir.get("linha_vazia", 0)}')
            self.stdout.write(f'- sem código NCM: {ir.get("sem_codigo", 0)}')
            self.stdout.write(f'- código inválido/incompleto: {ir.get("codigo_incompleto_ou_invalido", 0)}')
            self.stdout.write(f'- linha hierárquica sem NCM completo: {ir.get("linha_hierarquica_sem_ncm_completo", 0)}')
            self.stdout.write(f'- descrição vazia: {ir.get("sem_descricao", 0)}')
            samples_ignored = report.get('ignored_samples') or []
            if samples_ignored:
                self.stdout.write('')
                self.stdout.write('Amostras ignoradas:')
                for s in samples_ignored[:10]:
                    self.stdout.write(s)
            samples = report.get('amostras') or []
            if samples:
                self.stdout.write('')
                self.stdout.write('Amostra de linhas interpretadas:')
                for sample in samples[:5]:
                    ipi_txt = sample.get('aliquota_ipi') or 'N/A'
                    self.stdout.write(f'{sample["codigo"]} | {sample["descricao"]} | IPI: {ipi_txt}')
        if ext == '.pdf':
            self.stdout.write(f'Páginas processadas: {report.get("paginas_processadas", 0)}')
            self.stdout.write(f'Páginas sem texto: {report.get("paginas_sem_texto", 0)}')
            self.stdout.write(f'Linhas ignoradas: {report.get("linhas_ignoradas", 0)}')
            self.stdout.write(f'Códigos inválidos: {report.get("codigos_invalidos", 0)}')
            self.stdout.write(f'Descrições sem NCM: {report.get("descricoes_sem_codigo", 0)}')
            self.stdout.write(f'Alíquotas não interpretadas: {report.get("aliquotas_nao_interpretadas", 0)}')
            if report.get('amostras'):
                self.stdout.write('')
                self.stdout.write('Amostra de linhas interpretadas:')
                for sample in report['amostras'][:5]:
                    ipi_txt = sample.get('aliquota_ipi') or 'N/A'
                    self.stdout.write(f'{sample["codigo"]} | {sample["descricao"]} | IPI: {ipi_txt}')
            if report.get('suspeitas'):
                self.stdout.write('')
                self.stdout.write('Inconsistências/suspeitas:')
                for msg in report['suspeitas'][:30]:
                    self.stdout.write(msg)
        if erros:
            self.stdout.write('')
            for e in erros[:100]:
                self.stdout.write(e)
