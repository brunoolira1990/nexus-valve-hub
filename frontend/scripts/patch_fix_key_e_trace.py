#!/usr/bin/env python3
"""Fix key + stack trace quando item zerar."""
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

# 1. key fixa em idx (evita remount quando id muda)
src = replace_once(
    src,
    "                  key={it.id ?? idx}\n",
    "                  key={`item-${idx}`}\n",
    "key-fixa",
)

# 2. stack trace quando item zerar
src = replace_once(
    src,
    "  // DEBUG: monitor de mudanca em form.itens\n"
    "  useEffect(() => {\n"
    "    const c = form.itens?.[0]?.componentes;\n"
    "    console.log(\n"
    "      '[DBG-monitor] form.itens[0].componentes =',\n"
    "      c?.length ?? 'undefined',\n"
    "      '| it.id=', form.itens?.[0]?.id,\n"
    "    );\n"
    "  }, [form.itens]);\n",
    "  // DEBUG: monitor de mudanca em form.itens\n"
    "  useEffect(() => {\n"
    "    const c = form.itens?.[0]?.componentes;\n"
    "    console.log(\n"
    "      '[DBG-monitor] form.itens[0].componentes =',\n"
    "      c?.length ?? 'undefined',\n"
    "      '| it.id=', form.itens?.[0]?.id,\n"
    "    );\n"
    "    // Se zerou de 1+ para 0, captura o stack\n"
    "    if (\n"
    "      form.itens?.[0] &&\n"
    "      (form.itens[0].componentes?.length ?? 0) === 0 &&\n"
    "      form.itens[0].id === undefined\n"
    "    ) {\n"
    "      console.trace('[DBG-STACK] item zerou e ficou sem id!');\n"
    "    }\n"
    "  }, [form.itens]);\n",
    "stack-trace",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
