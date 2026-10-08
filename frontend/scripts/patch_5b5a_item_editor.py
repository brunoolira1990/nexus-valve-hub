#!/usr/bin/env python3
"""Rodada 1 (A) — botao 'Buscar dados do fornecedor' no ItemEditor."""
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

# 1. props novas em CorridasProps
src = replace_once(
    src,
    "  onAplicarDistribuicao: () => void;\n"
    "  onAbrirModalCorridasCf: () => void;\n"
    "};\n",
    "  onAplicarDistribuicao: () => void;\n"
    "  onAbrirModalCorridasCf: () => void;\n"
    "  onBuscarDadosFornecedor: () => void;\n"
    "  fornecedorBuscaLoading: boolean;\n"
    "  fornecedorBuscaMsg?: { type: 'error' | 'info'; text: string };\n"
    "};\n",
    "props-fornecedor",
)

# 2. botao + msg abaixo da row corrida/lote manual
src = replace_once(
    src,
    "                  onChange={(e) => onChange({ lote: e.target.value })}\n"
    "                />\n"
    "              </div>\n"
    "            </div>\n"
    "          </div>\n"
    "        ) : null}\n",
    "                  onChange={(e) => onChange({ lote: e.target.value })}\n"
    "                />\n"
    "              </div>\n"
    "            </div>\n"
    "            <div className=\"mt-2 flex flex-wrap gap-2 items-center\">\n"
    "              <button\n"
    "                type=\"button\"\n"
    "                className=\"erp-btn-outline erp-btn-sm\"\n"
    "                disabled={disabled || corridas.fornecedorBuscaLoading}\n"
    "                title=\"Busca por produto + corrida/lote (e codigo/descricao do item). Itens do fornecedor sem produto vinculado exigem confirmacao antes de aplicar.\"\n"
    "                onClick={corridas.onBuscarDadosFornecedor}\n"
    "              >\n"
    "                {corridas.fornecedorBuscaLoading\n"
    "                  ? 'Buscando...'\n"
    "                  : 'Buscar dados do fornecedor'}\n"
    "              </button>\n"
    "            </div>\n"
    "            {corridas.fornecedorBuscaMsg ? (\n"
    "              <p\n"
    "                className={\n"
    "                  corridas.fornecedorBuscaMsg.type === 'error'\n"
    "                    ? 'text-sm text-destructive mt-2'\n"
    "                    : 'text-sm text-amber-800 dark:text-amber-200 mt-2'\n"
    "                }\n"
    "                role={\n"
    "                  corridas.fornecedorBuscaMsg.type === 'error' ? 'alert' : 'status'\n"
    "                }\n"
    "              >\n"
    "                {corridas.fornecedorBuscaMsg.text}\n"
    "              </p>\n"
    "            ) : null}\n"
    "          </div>\n"
    "        ) : null}\n",
    "botao-fornecedor",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
