#!/usr/bin/env python3
"""Etapa 4b — carregarPorNFe passa a popular form.itens (tabela read-only)."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

src = TARGET.read_text(encoding="utf-8")
orig = src

def replace_once(text: str, old: str, new: str, tag: str) -> str:
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

# 1. imports dos helpers de normalizacao
src = replace_once(
    src,
    "import { emptyForm, LABEL_OBRIGATORIO_EMITIR } from '@/lib/certificadoQualidadeConstants';\n",
    "import {\n"
    "  emptyForm,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "imports-constants",
)

# 2. import do tipo ItemCertificadoQualidade
src = replace_once(
    src,
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "} from '@/types';\n",
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  ItemCertificadoQualidade,\n"
    "} from '@/types';\n",
    "imports-types",
)

# 3. setForm do carregarPorNFe: adicionar 'itens' (antes do fechamento)
src = replace_once(
    src,
    "        nota_fiscal_historica: data.nota_fiscal_historica ?? p.nota_fiscal_historica,\n"
    "        data_emissao: data.data_emissao ?? p.data_emissao,\n"
    "      }));\n",
    "        nota_fiscal_historica: data.nota_fiscal_historica ?? p.nota_fiscal_historica,\n"
    "        data_emissao: data.data_emissao ?? p.data_emissao,\n"
    "        itens: ((data.itens as ItemCertificadoQualidade[]) ?? []).map((it) => ({\n"
    "          ...it,\n"
    "          tipo_dados_tecnicos: it.tipo_dados_tecnicos || 'PADRAO_ITEM',\n"
    "          incluir_no_certificado: it.incluir_no_certificado !== false,\n"
    "          motivo_nao_inclusao: it.motivo_nao_inclusao || '',\n"
    "          observacao_nao_inclusao: it.observacao_nao_inclusao || '',\n"
    "          composicao_json: ensureMap(it.composicao_json),\n"
    "          ensaio_tracao_json: ensureMap(it.ensaio_tracao_json),\n"
    "          ensaio_impacto_json: ensureMap(it.ensaio_impacto_json),\n"
    "          componentes: (it.componentes || []).map((cp, i) => ensureComp(cp, i + 1)),\n"
    "        })),\n"
    "      }));\n",
    "carregar-itens",
)

# 4. remove a mensagem "N itens retornado(s)" (agora que populamos)
src = replace_once(
    src,
    "      const msg = [...(data.mensagens || [])];\n"
    "      const nItens = Array.isArray((data as { itens?: unknown[] }).itens) ? ((data as { itens?: unknown[] }).itens as unknown[]).length : 0;\n"
    "      if (nItens > 0) {\n"
    "        msg.push(\n"
    "          `${nItens} item(ns) retornado(s) pela NF-e. A tabela de itens sera portada na Etapa 4.`,\n"
    "        );\n"
    "      }\n"
    "      setMensagens(msg);\n",
    "      setMensagens(data.mensagens || []);\n",
    "remove-msg-itens",
)

# 5. backup + write
if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
