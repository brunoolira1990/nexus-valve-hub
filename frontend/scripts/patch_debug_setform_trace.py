#!/usr/bin/env python3
"""Wrapper no setForm que captura quem zera itens."""
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

# Renomeia o state pra setFormRaw e cria wrapper setForm
src = replace_once(
    src,
    "  const [form, setForm] = useState<FormState>(emptyForm());\n",
    "  const [form, setFormRaw] = useState<FormState>(emptyForm());\n"
    "  const setForm = (\n"
    "    updater: FormState | ((prev: FormState) => FormState),\n"
    "  ) => {\n"
    "    setFormRaw((prev) => {\n"
    "      const next = typeof updater === 'function' ? updater(prev) : updater;\n"
    "      const prevId = prev.itens?.[0]?.id;\n"
    "      const nextId = next.itens?.[0]?.id;\n"
    "      const prevComp = prev.itens?.[0]?.componentes?.length ?? 0;\n"
    "      const nextComp = next.itens?.[0]?.componentes?.length ?? 0;\n"
    "      if (prevComp > 0 && nextComp === 0) {\n"
    "        console.trace('[DBG-setForm ZEROU]', {\n"
    "          de_id: prevId,\n"
    "          para_id: nextId,\n"
    "          de_comp: prevComp,\n"
    "          para_comp: nextComp,\n"
    "        });\n"
    "      }\n"
    "      return next;\n"
    "    });\n"
    "  };\n",
    "wrapper-setForm",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
