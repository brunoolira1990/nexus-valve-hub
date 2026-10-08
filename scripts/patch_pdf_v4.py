#!/usr/bin/env python3
"""Fix PDF v4: data_table_auto (auto-height) + Paragraph na tabela de valvula."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("backend/apps/qualidade/certificado_pdf.py")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

src = TARGET.read_text(encoding="utf-8")
orig = src

def replace_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

# 1. Adiciona cell_wrap_style + data_table_auto ANTES de data_table (mesmo escopo)
src = replace_once(
    src,
    "    def data_table(data: list[list[str]], col_widths: list[float], row_h: float) -> Table:\n",
    "    # Estilo para celulas que quebram linha (descricao, norma, cert) — usado so na tabela de valvula\n"
    "    cell_wrap_style = ParagraphStyle(\n"
    "        'cell_wrap_cq',\n"
    "        fontName='Helvetica',\n"
    "        fontSize=PDF_THEME['body_size'],\n"
    "        leading=PDF_THEME['body_size'] + 1.2,\n"
    "        alignment=0,\n"
    "    )\n"
    "\n"
    "    def data_table_auto(data: list[list], col_widths: list[float]) -> Table:\n"
    "        \"\"\"Tabela com altura de linha automatica (aceita Paragraph nas celulas).\"\"\"\n"
    "        t = Table(data, colWidths=col_widths, repeatRows=1 if len(data) > 1 else 0)\n"
    "        t.setStyle(TableStyle([\n"
    "            ('GRID', (0, 0), (-1, -1), 0.28, PDF_THEME['border']),\n"
    "            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 7.1),\n"
    "            ('FONT', (0, 1), (-1, -1), 'Helvetica', PDF_THEME['body_size']),\n"
    "            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),\n"
    "            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),\n"
    "            ('BACKGROUND', (0, 0), (-1, 0), PDF_THEME['table_header_bg']),\n"
    "            ('LINEBELOW', (0, 0), (-1, 0), 0.85, PDF_THEME['brand_primary']),\n"
    "            ('TEXTCOLOR', (0, 0), (-1, -1), PDF_THEME['text']),\n"
    "            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDF_THEME['row_alt']]),\n"
    "            ('LEFTPADDING', (0, 0), (-1, -1), 2),\n"
    "            ('RIGHTPADDING', (0, 0), (-1, -1), 2),\n"
    "        ]))\n"
    "        return t\n"
    "\n"
    "    def data_table(data: list[list[str]], col_widths: list[float], row_h: float) -> Table:\n",
    "cell-wrap-auto",
)

# 2. Tabela de valvula: Paragraph nas celulas longas + data_table_auto
src = replace_once(
    src,
    "                _cortar_descricao(item_valvula.descricao_material),\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "                item_valvula.norma or '—',\n"
    "                item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "            ]]\n"
    "            story.append(data_table(item_valvula_data, [10 * mm, 26 * mm, 118 * mm, 18 * mm, 15 * mm, 32 * mm, 52 * mm], row_h=7.2 * mm))\n",
    "                Paragraph(item_valvula.descricao_material or '—', cell_wrap_style),\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "                Paragraph(item_valvula.norma or '—', cell_wrap_style),\n"
    "                Paragraph(\n"
    "                    item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "                    cell_wrap_style,\n"
    "                ),\n"
    "            ]]\n"
    "            story.append(data_table_auto(item_valvula_data, [10 * mm, 26 * mm, 118 * mm, 18 * mm, 15 * mm, 32 * mm, 52 * mm]))\n",
    "valve-auto",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
