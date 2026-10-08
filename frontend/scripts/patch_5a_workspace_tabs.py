#!/usr/bin/env python3
"""Etapa 5a — reorganiza Workspace do CQ em Tabs (Dados | Itens | Observacoes), padrao do CF."""
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

# 1. imports do Tabs
src = replace_once(
    src,
    "import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';\n",
    "import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';\n"
    "import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';\n",
    "import-tabs",
)

# 2. state abaAtiva
src = replace_once(
    src,
    "  const [nfHistoricas, setNfHistoricas] = useState<NFeSaidaHistoricaList[]>([]);\n",
    "  const [nfHistoricas, setNfHistoricas] = useState<NFeSaidaHistoricaList[]>([]);\n"
    "  const [abaAtiva, setAbaAtiva] = useState('dados');\n",
    "state-abaAtiva",
)

# 3. remove o bloco de observacoes do grid (fica so texto_padrao na aba Dados)
src = replace_once(
    src,
    "        <div className=\"md:col-span-4\">\n"
    "          <label className=\"erp-label\">Observa\u00e7\u00f5es</label>\n"
    "          <textarea\n"
    "            className=\"erp-input mt-1 min-h-[60px]\"\n"
    "            value={form.observacoes || ''}\n"
    "            onChange={(e) => setF('observacoes', e.target.value)}\n"
    "          />\n"
    "        </div>\n"
    "        <div className=\"md:col-span-4\">\n"
    "          <label className=\"erp-label\">Texto padr\u00e3o</label>\n",
    "        <div className=\"md:col-span-4\">\n"
    "          <label className=\"erp-label\">Texto padr\u00e3o</label>\n",
    "remove-obs-do-grid",
)

# 4. abre Tabs + TabsList + TabsContent dados (logo apos saveError, antes do grid)
src = replace_once(
    src,
    "      {saveError ? (\n"
    "        <p className=\"text-sm text-destructive\">{saveError}</p>\n"
    "      ) : null}\n"
    "\n"
    "      <div className=\"grid grid-cols-1 md:grid-cols-4 gap-3\">\n",
    "      {saveError ? (\n"
    "        <p className=\"text-sm text-destructive\">{saveError}</p>\n"
    "      ) : null}\n"
    "\n"
    "      <Tabs value={abaAtiva} onValueChange={setAbaAtiva}>\n"
    "        <TabsList className=\"h-auto w-full justify-start gap-1 overflow-x-auto whitespace-nowrap bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/90 border border-border border-b-0 rounded-t-lg px-3 pt-2.5 pb-1 sm:px-4\">\n"
    "          <TabsTrigger value=\"dados\">Dados</TabsTrigger>\n"
    "          <TabsTrigger value=\"itens\">Itens</TabsTrigger>\n"
    "          <TabsTrigger value=\"observacoes\">Observa\u00e7\u00f5es</TabsTrigger>\n"
    "        </TabsList>\n"
    "\n"
    "        <TabsContent value=\"dados\" className=\"mt-0 space-y-4\">\n"
    "      <div className=\"grid grid-cols-1 md:grid-cols-4 gap-3\">\n",
    "abre-tabs-dados",
)

# 5. fecha TabsContent dados, abre TabsContent itens (entre bloco NF-e e bloco Itens)
src = replace_once(
    src,
    "        ) : null}\n"
    "      </div>\n"
    "\n"
    "      <div className=\"rounded border border-border bg-muted/10 p-3\">\n"
    "        <p className=\"text-sm font-medium mb-2\">Itens do certificado</p>\n",
    "        ) : null}\n"
    "      </div>\n"
    "        </TabsContent>\n"
    "\n"
    "        <TabsContent value=\"itens\" className=\"mt-0 space-y-4\">\n"
    "      <div className=\"rounded border border-border bg-muted/10 p-3\">\n"
    "        <p className=\"text-sm font-medium mb-2\">Itens do certificado</p>\n",
    "fecha-dados-abre-itens",
)

# 6. fecha itens, cria TabsContent observacoes, fecha Tabs (antes dos botoes)
src = replace_once(
    src,
    "      <div className=\"rounded border border-dashed p-4 text-center text-xs text-muted-foreground\">\n"
    "        <p className=\"font-medium mb-1\">Editor de item, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5: editor \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>\n"
    "      </div>\n"
    "\n"
    "      <div className=\"flex justify-end gap-2\">\n",
    "      <div className=\"rounded border border-dashed p-4 text-center text-xs text-muted-foreground\">\n"
    "        <p className=\"font-medium mb-1\">Editor de item, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5: editor \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>\n"
    "      </div>\n"
    "        </TabsContent>\n"
    "\n"
    "        <TabsContent value=\"observacoes\" className=\"mt-0 space-y-4\">\n"
    "          <div>\n"
    "            <label className=\"erp-label\">Observa\u00e7\u00f5es</label>\n"
    "            <textarea\n"
    "              className=\"erp-input mt-1 min-h-[120px]\"\n"
    "              value={form.observacoes || ''}\n"
    "              onChange={(e) => setF('observacoes', e.target.value)}\n"
    "            />\n"
    "          </div>\n"
    "        </TabsContent>\n"
    "      </Tabs>\n"
    "\n"
    "      <div className=\"flex justify-end gap-2\">\n",
    "fecha-itens-obs-tabs",
)

# 7. backup + write
if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
