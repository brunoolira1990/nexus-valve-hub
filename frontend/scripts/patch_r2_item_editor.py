#!/usr/bin/env python3
"""Rodada 2 (A) — botao 'Buscar dados da corrida' por componente."""
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

# 1. estende ComponentesProps
src = replace_once(
    src,
    "  onUpdateJson: (\n"
    "    compIdx: number,\n"
    "    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',\n"
    "    key: string,\n"
    "    value: string,\n"
    "  ) => void;\n"
    "};\n",
    "  onUpdateJson: (\n"
    "    compIdx: number,\n"
    "    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',\n"
    "    key: string,\n"
    "    value: string,\n"
    "  ) => void;\n"
    "  onBuscarDadosCorrida: (compIdx: number) => void;\n"
    "  fornecedorBuscaCompLoading?: number | null;\n"
    "  fornecedorBuscaCompMsg?: { type: 'error' | 'info'; text: string } | null;\n"
    "};\n",
    "props-busca-comp",
)

# 2. botao + msg dentro do <details> do componente, junto aos outros botoes
src = replace_once(
    src,
    "                        <button\n"
    "                          type=\"button\"\n"
    "                          className=\"erp-btn-outline erp-btn-sm\"\n"
    "                          disabled={disabled}\n"
    "                          onClick={() => componentes.onRemove(cidx)}\n"
    "                        >\n"
    "                          Remover componente\n"
    "                        </button>\n"
    "                      </div>\n",
    "                        <button\n"
    "                          type=\"button\"\n"
    "                          className=\"erp-btn-outline erp-btn-sm\"\n"
    "                          disabled={disabled}\n"
    "                          onClick={() => componentes.onRemove(cidx)}\n"
    "                        >\n"
    "                          Remover componente\n"
    "                        </button>\n"
    "                        <button\n"
    "                          type=\"button\"\n"
    "                          className=\"erp-btn-outline erp-btn-sm\"\n"
    "                          disabled={\n"
    "                            disabled ||\n"
    "                            componentes.fornecedorBuscaCompLoading === cidx\n"
    "                          }\n"
    "                          title=\"Busca dados do CF pela corrida/lote deste componente.\"\n"
    "                          onClick={() => componentes.onBuscarDadosCorrida(cidx)}\n"
    "                        >\n"
    "                          {componentes.fornecedorBuscaCompLoading === cidx\n"
    "                            ? 'Buscando...'\n"
    "                            : 'Buscar dados da corrida'}\n"
    "                        </button>\n"
    "                      </div>\n"
    "                      {componentes.fornecedorBuscaCompMsg ? (\n"
    "                        <p\n"
    "                          className={\n"
    "                            componentes.fornecedorBuscaCompMsg.type === 'error'\n"
    "                              ? 'text-sm text-destructive'\n"
    "                              : 'text-sm text-amber-800 dark:text-amber-200'\n"
    "                          }\n"
    "                          role={\n"
    "                            componentes.fornecedorBuscaCompMsg.type === 'error'\n"
    "                              ? 'alert'\n"
    "                              : 'status'\n"
    "                          }\n"
    "                        >\n"
    "                          {componentes.fornecedorBuscaCompMsg.text}\n"
    "                        </p>\n"
    "                      ) : null}\n",
    "botao-busca-comp",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
