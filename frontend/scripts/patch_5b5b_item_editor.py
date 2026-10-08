#!/usr/bin/env python3
"""Label do botao muda quando item ja tem CF/item vinculados."""
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

src = replace_once(
    src,
    "                {corridas.fornecedorBuscaLoading\n"
    "                  ? 'Buscando...'\n"
    "                  : 'Buscar dados do fornecedor'}\n",
    "                {corridas.fornecedorBuscaLoading\n"
    "                  ? 'Buscando...'\n"
    "                  : it.certificado_fornecedor_origem_id &&\n"
    "                      it.item_certificado_fornecedor_origem_id\n"
    "                    ? 'Puxar dados do CF vinculado'\n"
    "                    : 'Buscar dados do fornecedor'}\n",
    "label-dinamico",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
