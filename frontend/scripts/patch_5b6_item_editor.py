#!/usr/bin/env python3
"""Em VALVULA_COMPONENTES, esconde seletores de corrida/lote do item."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/ItemEditor.tsx")
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

# 1. envolve o <div> do select de corrida/lote + warning em condicional
src = replace_once(
    src,
    "            <div className=\"mt-2\">\n"
    "              <label className=\"erp-label\">Corrida/Lote disponivel</label>\n"
    "              <select\n",
    "            {it.tipo_dados_tecnicos !== 'VALVULA_COMPONENTES' ? (\n"
    "            <div className=\"mt-2\">\n"
    "              <label className=\"erp-label\">Corrida/Lote disponivel</label>\n"
    "              <select\n",
    "abre-select-corrida",
)

src = replace_once(
    src,
    "                <p className=\"text-xs text-amber-700 dark:text-amber-300 mt-1\">\n"
    "                  Nenhuma corrida/lote disponivel encontrada para este produto cadastrado.\n"
    "                </p>\n"
    "              ) : null}\n"
    "            </div>\n"
    "            <div className=\"mt-2 flex flex-wrap gap-2\">\n",
    "                <p className=\"text-xs text-amber-700 dark:text-amber-300 mt-1\">\n"
    "                  Nenhuma corrida/lote disponivel encontrada para este produto cadastrado.\n"
    "                </p>\n"
    "              ) : null}\n"
    "            </div>\n"
    "            ) : null}\n"
    "            <div className=\"mt-2 flex flex-wrap gap-2\">\n",
    "fecha-select-corrida",
)

# 2. envolve o <div> de corrida manual + lote manual em condicional
src = replace_once(
    src,
    "            <div className=\"flex flex-col sm:flex-row gap-2 mt-2\">\n"
    "              <div className=\"flex-1\">\n"
    "                <label className=\"erp-label\">Corrida manual{LABEL_OBRIGATORIO_EMITIR}</label>\n",
    "            {it.tipo_dados_tecnicos !== 'VALVULA_COMPONENTES' ? (\n"
    "            <div className=\"flex flex-col sm:flex-row gap-2 mt-2\">\n"
    "              <div className=\"flex-1\">\n"
    "                <label className=\"erp-label\">Corrida manual{LABEL_OBRIGATORIO_EMITIR}</label>\n",
    "abre-corrida-manual",
)

src = replace_once(
    src,
    "                  value={it.lote || it.lote_snapshot || ''}\n"
    "                  disabled={disabled}\n"
    "                  onChange={(e) => onChange({ lote: e.target.value })}\n"
    "                />\n"
    "              </div>\n"
    "            </div>\n"
    "            <div className=\"mt-2 flex flex-wrap gap-2 items-center\">\n",
    "                  value={it.lote || it.lote_snapshot || ''}\n"
    "                  disabled={disabled}\n"
    "                  onChange={(e) => onChange({ lote: e.target.value })}\n"
    "                />\n"
    "              </div>\n"
    "            </div>\n"
    "            ) : null}\n"
    "            <div className=\"mt-2 flex flex-wrap gap-2 items-center\">\n",
    "fecha-corrida-manual",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
