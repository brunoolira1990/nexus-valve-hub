#!/usr/bin/env python3
"""Remove coluna Certificado Fornecedor de 2 tabelas (info interna, nao deve ir pro cliente)."""
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

# 1. VÁLVULA / COMPONENTES: remove coluna "Certificado Fornecedor (snapshot)"
src = replace_once(
    src,
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
    "            item_valvula_data = [[\n"
    "                'Item', 'Código', 'Descrição', 'Quantidade', 'Unidade',\n"
    "            ], [\n"
    "                str(item_valvula.ordem),\n"
    "                item_valvula.codigo_produto or '—',\n"
    "                Paragraph(item_valvula.descricao_material or '—', cell_wrap_style),\n"
    "                _fmt_value(item_valvula.quantidade),\n"
    "                item_valvula.unidade or '—',\n"
    "            ]]\n"
    "            story.append(data_table_auto(item_valvula_data, [12 * mm, 30 * mm, 185 * mm, 24 * mm, 20 * mm]))\n",
    "remove-cf-valvula",
)

# 2. COMPONENTES DA VÁLVULA: remove coluna "Certificado Fornecedor"
src = replace_once(
    src,
    "                comp_rows = [['Comp.', 'Corrida', 'Lote', 'Norma', 'Certificado Fornecedor', 'Observação']]\n"
    "                for cp in comp_chunk:\n"
    "                    comp_rows.append([\n"
    "                        cp.nome_componente or '—',\n"
    "                        cp.corrida or '—',\n"
    "                        getattr(cp, 'lote', '') or item_valvula.lote_snapshot or '—',\n"
    "                        cp.norma or '—',\n"
    "                        cp.numero_certificado_fornecedor_componente_snapshot or item_valvula.numero_certificado_fornecedor_item_snapshot or '—',\n"
    "                        (cp.observacoes or '—')[:38],\n"
    "                    ])\n"
    "                story.append(section_title('Componentes da válvula'))\n"
    "                story.append(data_table(comp_rows, [42 * mm, 30 * mm, 24 * mm, 40 * mm, 48 * mm, 87 * mm], row_h=6.7 * mm))\n",
    "                comp_rows = [['Comp.', 'Corrida', 'Lote', 'Norma', 'Observação']]\n"
    "                for cp in comp_chunk:\n"
    "                    comp_rows.append([\n"
    "                        cp.nome_componente or '—',\n"
    "                        cp.corrida or '—',\n"
    "                        getattr(cp, 'lote', '') or item_valvula.lote_snapshot or '—',\n"
    "                        cp.norma or '—',\n"
    "                        (cp.observacoes or '—')[:60],\n"
    "                    ])\n"
    "                story.append(section_title('Componentes da válvula'))\n"
    "                story.append(data_table(comp_rows, [45 * mm, 35 * mm, 28 * mm, 45 * mm, 118 * mm], row_h=6.7 * mm))\n",
    "remove-cf-componentes",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
