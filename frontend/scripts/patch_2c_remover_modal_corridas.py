#!/usr/bin/env python3
"""Fase 2c — remove o <ModalCorridasCertificadoFornecedor> (morto) do Certificados.tsx."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/Certificados.tsx")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

src = TARGET.read_text(encoding="utf-8")
orig = src
lines = src.split("\n")

start = None
for i, line in enumerate(lines):
    if "<ModalCorridasCertificadoFornecedor" in line:
        start = i
        break
if start is None:
    sys.exit("nao achei ModalCorridasCertificadoFornecedor")

# procura próximo `      />` (6 espacos + />)
end = None
for j in range(start + 1, len(lines)):
    if lines[j] == "      />":
        end = j
        break
if end is None:
    sys.exit("nao achei fechamento />")

removidas = end - start + 1
print(f"  removendo {removidas} linhas (de {start+1} a {end+1})")
print(f"    primeira: {lines[start][:80]}")
print(f"    ultima  : {lines[end]}")

new_lines = lines[:start] + lines[end+1:]
src = "\n".join(new_lines)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
