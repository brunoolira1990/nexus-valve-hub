#!/usr/bin/env python3
"""Consolida os 3 imports de certificadoQualidadeConstants num so."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
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

# 1. Remove o bloco duplicado mais abaixo (o 3o import com emptyForm)
src = replace_once(
    src,
    "import {\n"
    "  emptyForm,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "",
    "remove-bloco-3",
)

# 2. Remove o import standalone de coerceProdutoItemId
src = replace_once(
    src,
    "import { coerceProdutoItemId } from '@/lib/certificadoQualidadeConstants';\n",
    "",
    "remove-coerce-standalone",
)

# 3. Substitui o 1o bloco pelo consolidado
src = replace_once(
    src,
    "import {\n"
    "  COMPONENTES_PADRAO,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "  fornecedorResultadoSemProdutoVinculado,\n"
    "  resolverCorridaLoteBuscaFornecedor,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import {\n"
    "  COMPONENTES_PADRAO,\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "  coerceProdutoItemId,\n"
    "  emptyForm,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "  fornecedorResultadoSemProdutoVinculado,\n"
    "  resolverCorridaLoteBuscaFornecedor,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "consolida",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
