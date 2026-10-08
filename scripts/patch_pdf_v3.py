#!/usr/bin/env python3
"""Fix PDF v3 (conservador): alarga coluna Descricao + corte em espaco."""
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

# 1. Adiciona helper de corte em espaco antes da secao "story = []" (perto do inicio do build)
src = replace_once(
    src,
    "def _draw_section_title(c: canvas.Canvas, text: str, x: float, y: float, w: float):\n",
    "def _cortar_descricao(desc: str, max_len: int = 100) -> str:\n"
    "    \"\"\"Corta descricao longa preferindo quebrar em espaco (nao no meio da palavra).\"\"\"\n"
    "    if not desc:\n"
    "        return '—'\n"
    "    if len(desc) <= max_len:\n"
    "        return desc\n"
    "    corte = desc.rfind(' ', 0, max_len)\n"
    "    if corte < int(max_len * 0.7):\n"
    "        corte = max_len\n"
    "    return desc[:corte].rstrip()\n"
    "\n"
    "\n"
    "def _draw_section_title(c: canvas.Canvas, text: str, x: float, y: float, w: float):\n",
    "helper-corte",
)

# 2. Substitui o [:74] pelo helper + alarga coluna Descricao + rebalanceia
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
    "                _cortar_descricao(item_valvula.descricao_material),\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "                item_valvula.norma or '—',\n"
    "                item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "            ]]\n"
    "            story.append(data_table(item_valvula_data, [10 * mm, 26 * mm, 118 * mm, 18 * mm, 15 * mm, 32 * mm, 52 * mm], row_h=7.2 * mm))\n",
    "tabela-valvula-v3",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
