#!/usr/bin/env python3
"""Fix: pedido_cliente usa numero da NF-e (xPed) em vez do ID do pedido_venda."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("backend/apps/qualidade/views.py")
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

# 1. Operacional: usa pedido_cliente_numero (xPed do XML)
src = replace_once(
    src,
    "                'pedido_cliente': (str(nf.pedido_venda_id) if nf.pedido_venda_id else ''),\n",
    "                'pedido_cliente': (nf.pedido_cliente_numero or '').strip(),\n",
    "operacional-pedido",
)

# 2. Historica: usa o campo direto se existir (NFeSaidaHistoricaImportada.pedido_cliente_numero)
src = replace_once(
    src,
    "            'pedido_cliente': '',\n",
    "            'pedido_cliente': getattr(nf_hist, 'pedido_cliente_numero', '') or '',\n",
    "historica-pedido",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
