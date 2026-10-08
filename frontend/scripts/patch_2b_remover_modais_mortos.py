#!/usr/bin/env python3
"""Fase 2b — remove 2 modais mortos (busca avancada + resultados fornecedor)."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/Certificados.tsx")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

src = TARGET.read_text(encoding="utf-8")
orig = src

lines = src.split("\n")

def find_block(lines, opener_match):
    start = None
    for i, line in enumerate(lines):
        if opener_match in line:
            start = i
            break
    if start is None:
        return None
    for j in range(start + 1, len(lines)):
        if lines[j] == "      </Modal>":
            return (start, j)
    return None

b1 = find_block(lines, "<Modal isOpen={fornecedorBuscaAvancadaOpen}")
b2 = find_block(lines, "<Modal isOpen={fornecedorMatchModalOpen}")

if b1 is None:
    sys.exit("nao achei modal busca avancada")
if b2 is None:
    sys.exit("nao achei modal resultados fornecedor")

# Ordena decrescente pra remover sem deslocar indices
blocks = sorted([b1, b2], key=lambda x: -x[0])
for (s, e) in blocks:
    print(f"  removendo {e - s + 1} linhas (de {s+1} a {e+1})")
    print(f"    primeira: {lines[s][:80]}")
    print(f"    ultima  : {lines[e]}")
    del lines[s:e+1]

src = "\n".join(lines)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
