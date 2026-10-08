#!/usr/bin/env python3
"""Etapa 6 (A) — botao 'Adicionar corridas do CF' no ItemEditor."""
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

# 1. import do TITULO_MODAL_CORRIDAS_CF_CQ
src = replace_once(
    src,
    "} from '@/lib/certificadoStatusUi';\n",
    "} from '@/lib/certificadoStatusUi';\n"
    "import { TITULO_MODAL_CORRIDAS_CF_CQ } from '@/lib/cqCorridasCfUi';\n",
    "import-titulo",
)

# 2. adicionar onAbrirModalCorridasCf ao CorridasProps
src = replace_once(
    src,
    "  onAplicarDistribuicao: () => void;\n"
    "};\n",
    "  onAplicarDistribuicao: () => void;\n"
    "  onAbrirModalCorridasCf: () => void;\n"
    "};\n",
    "prop-nova",
)

# 3. botao entre o select e o bloco corrida manual
src = replace_once(
    src,
    "                  Nenhuma corrida/lote disponivel encontrada para este produto cadastrado.\n"
    "                </p>\n"
    "              ) : null}\n"
    "            </div>\n"
    "            <div className=\"flex flex-col sm:flex-row gap-2 mt-2\">\n",
    "                  Nenhuma corrida/lote disponivel encontrada para este produto cadastrado.\n"
    "                </p>\n"
    "              ) : null}\n"
    "            </div>\n"
    "            <div className=\"mt-2 flex flex-wrap gap-2\">\n"
    "              <button\n"
    "                type=\"button\"\n"
    "                className=\"erp-btn-outline erp-btn-sm\"\n"
    "                disabled={\n"
    "                  disabled ||\n"
    "                  !it.certificado_fornecedor_origem_id ||\n"
    "                  !it.item_certificado_fornecedor_origem_id\n"
    "                }\n"
    "                title={\n"
    "                  !it.certificado_fornecedor_origem_id ||\n"
    "                  !it.item_certificado_fornecedor_origem_id\n"
    "                    ? 'Vincule este item ao Certificado de Fornecedor e ao item exato do CF antes de adicionar corridas.'\n"
    "                    : 'Distribui este item em uma linha por corrida do CF vinculado, com quantidade e dados tecnicos por corrida.'\n"
    "                }\n"
    "                onClick={corridas.onAbrirModalCorridasCf}\n"
    "              >\n"
    "                {TITULO_MODAL_CORRIDAS_CF_CQ}\n"
    "              </button>\n"
    "            </div>\n"
    "            <div className=\"flex flex-col sm:flex-row gap-2 mt-2\">\n",
    "botao-modal-cf",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
