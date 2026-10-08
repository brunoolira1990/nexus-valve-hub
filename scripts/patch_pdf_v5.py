#!/usr/bin/env python3
"""Remove coluna Norma da tabela VALVULA/COMPONENTES (norma esta nos componentes)."""
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

src = replace_once(
    src,
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
    "            story.append(data_table_auto(item_valvula_data, [10 * mm, 26 * mm, 118 * mm, 18 * mm, 15 * mm, 32 * mm, 52 * mm]))\n",
    "            item_valvula_data = [[\n"
    "                'Item', 'Código', 'Descrição', 'Quantidade', 'Unidade', 'Certificado Fornecedor (snapshot)',\n"
    "            ], [\n"
    "                str(item_valvula.ordem),\n"
    "                item_valvula.codigo_produto or '—',\n"
    "                Paragraph(item_valvula.descricao_material or '—', cell_wrap_style),\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "                Paragraph(\n"
    "                    item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "                    cell_wrap_style,\n"
    "                ),\n"
    "            ]]\n"
    "            story.append(data_table_auto(item_valvula_data, [10 * mm, 28 * mm, 148 * mm, 20 * mm, 17 * mm, 48 * mm]))\n",
    "remove-norma",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
