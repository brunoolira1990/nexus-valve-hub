#!/usr/bin/env python3
"""Fix PDF: descricao do item quebra linha em vez de truncar em 74 chars."""
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

# 1. data_table aceita row_h=None (altura automatica)
src = replace_once(
    src,
    "    def data_table(data: list[list[str]], col_widths: list[float], row_h: float) -> Table:\n"
    "        rows = [row_h] * len(data)\n"
    "        t = Table(data, colWidths=col_widths, rowHeights=rows, repeatRows=1 if len(data) > 1 else 0)\n",
    "    def data_table(\n"
    "        data: list[list], col_widths: list[float], row_h: float | None = None\n"
    "    ) -> Table:\n"
    "        rows = [row_h] * len(data) if row_h is not None else None\n"
    "        t = Table(data, colWidths=col_widths, rowHeights=rows, repeatRows=1 if len(data) > 1 else 0)\n",
    "data_table-auto",
)

# 2. Cria desc_style perto do footer_style
src = replace_once(
    src,
    "        footer_style = ParagraphStyle(\n",
    "        # Estilo para celulas com texto longo (descricao, norma, cert) — permite quebra de linha\n"
    "        cell_wrap_style = ParagraphStyle(\n"
    "            'cell_wrap_cq',\n"
    "            fontName='Helvetica',\n"
    "            fontSize=PDF_THEME['body_size'],\n"
    "            leading=PDF_THEME['body_size'] + 1.2,\n"
    "            alignment=0,\n"
    "        )\n"
    "\n"
    "        footer_style = ParagraphStyle(\n",
    "cell-wrap-style",
)

# 3. Na tabela do item valvula: Paragraph pra descricao/norma/cert + row_h=None
src = replace_once(
    src,
    "            item_valvula_data = [[\n"
    "                'Item', 'Código', 'Descrição', 'Quantidade', 'Unidade', 'Norma', 'Certificado Fornecedor (snapshot)',\n"
    "            ], [\n"
    "                str(item_valvula.ordem),\n"
    "                item_valvula.codigo_produto or '—',\n"
    "                (item_valvula.descricao_material or '—')[:74],\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "                item_valvula.norma or '—',\n"
    "                item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "            ]]\n"
    "            story.append(data_table(item_valvula_data, [12 * mm, 30 * mm, 95 * mm, 22 * mm, 18 * mm, 36 * mm, 58 * mm], row_h=7.2 * mm))\n",
    "            item_valvula_data = [[\n"
    "                'Item', 'Código', 'Descrição', 'Quantidade', 'Unidade', 'Norma', 'Certificado Fornecedor (snapshot)',\n"
    "            ], [\n"
    "                str(item_valvula.ordem),\n"
    "                item_valvula.codigo_produto or '—',\n"
    "                Paragraph(item_valvula.descricao_material or '—', cell_wrap_style),\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "                Paragraph(item_valvula.norma or '—', cell_wrap_style),\n"
    "                Paragraph(\n"
    "                    item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "                    cell_wrap_style,\n"
    "                ),\n"
    "            ]]\n"
    "            story.append(data_table(item_valvula_data, [12 * mm, 30 * mm, 95 * mm, 22 * mm, 18 * mm, 36 * mm, 58 * mm]))\n",
    "tabela-item-wrap",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
