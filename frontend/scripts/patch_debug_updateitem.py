#!/usr/bin/env python3
"""Debug temporario: rastrear quem chama updateItem e quando form.itens muda."""
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

# 1. updateItem: loga o patch
src = replace_once(
    src,
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n",
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) => {\n"
    "    if (idx === 0) {\n"
    "      console.log('[DBG-updateItem idx=0] patch=', JSON.stringify(Object.keys(patch)), 'temComponentes=', 'componentes' in patch);\n"
    "    }\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n"
    "  };\n",
    "log-updateItem",
)

# 2. Monitor: loga toda mudanca em form.itens
src = replace_once(
    src,
    "  // Carrega NF-e de saida historicas (uma vez no mount)\n",
    "  // DEBUG: monitor de mudanca em form.itens\n"
    "  useEffect(() => {\n"
    "    const c = form.itens?.[0]?.componentes;\n"
    "    console.log(\n"
    "      '[DBG-monitor] form.itens[0].componentes =',\n"
    "      c?.length ?? 'undefined',\n"
    "      '| it.id=', form.itens?.[0]?.id,\n"
    "    );\n"
    "  }, [form.itens]);\n"
    "\n"
    "  // Carrega NF-e de saida historicas (uma vez no mount)\n",
    "log-monitor",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
