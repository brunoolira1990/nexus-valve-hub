#!/usr/bin/env python3
"""Remove todos os debugs temporarios e restaura o codigo limpo."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
VITE = pathlib.Path("vite.config.ts")
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

# 1. Remove wrapper setForm, volta pro useState original
OLD_WRAPPER = (
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
    "  };\n"
)
src = replace_once(
    src,
    OLD_WRAPPER,
    "  const [form, setForm] = useState<FormState>(emptyForm());\n",
    "remove-wrapper",
)

# 2. Remove console.log do load
src = replace_once(
    src,
    "        console.log('[DBG-load] row.itens.length=', row.itens?.length, ' itens[0].componentes=', row.itens?.[0]?.componentes);\n",
    "",
    "remove-log-load",
)

# 3. Remove o useEffect monitor completo (com console.log + console.trace)
OLD_MONITOR = (
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
    "  }, [form.itens]);\n"
    "\n"
)
src = replace_once(src, OLD_MONITOR, "", "remove-monitor")

# 4. Remove console.log do updateItem (volta ao arrow direto)
OLD_UPDATE = (
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) => {\n"
    "    if (idx === 0) {\n"
    "      console.log('[DBG-updateItem idx=0] patch=', JSON.stringify(Object.keys(patch)), 'temComponentes=', 'componentes' in patch);\n"
    "    }\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n"
    "  };\n"
)
NEW_UPDATE = (
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n"
)
src = replace_once(src, OLD_UPDATE, NEW_UPDATE, "remove-updateItem-log")

# 5. Remove console.log do render map (volta ao arrow direto)
src = replace_once(
    src,
    "              {form.itens.map((it, idx) => {\n"
    "                console.log('[DBG-render] idx=', idx, 'it.componentes=', it.componentes?.length);\n"
    "                return (\n",
    "              {form.itens.map((it, idx) => (\n",
    "remove-render-log-open",
)

src = replace_once(
    src,
    "                />\n"
    "                );\n"
    "              })}\n"
    "            </div>\n",
    "                />\n"
    "              ))}\n"
    "            </div>\n",
    "remove-render-log-close",
)

# 6. Salva
if src == orig:
    sys.exit("nada mudou no Workspace — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} lines)")

# 7. Remove sourcemap do vite.config
if VITE.exists():
    v = VITE.read_text(encoding="utf-8")
    old_v = (
        "  build: {\n"
        "    // TEMPORARIO: sourcemap pra debugar stack trace em producao interna\n"
        "    sourcemap: true,\n"
        "  },\n"
    )
    if old_v in v:
        v = v.replace(old_v, "", 1)
        vbackup = VITE.with_suffix(f".ts.bak_{stamp}")
        shutil.copyfile(VITE, vbackup)
        VITE.write_text(v, encoding="utf-8")
        print(f"\nvite.config.ts: sourcemap removido (backup: {vbackup})")
    else:
        print("\nvite.config.ts: sourcemap nao encontrado (talvez ja removido)")
