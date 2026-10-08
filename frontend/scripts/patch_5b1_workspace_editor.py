#!/usr/bin/env python3
"""Etapa 5b-1 (corretivo) — patch no Workspace assumindo ItemEditor ja criado e tipo ja importado."""
import shutil, sys, pathlib, datetime

WORKSPACE = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
ITEM_EDITOR = pathlib.Path("src/pages/CertificadosQualidade/ItemEditor.tsx")

if not WORKSPACE.exists():
    sys.exit(f"nao encontrei {WORKSPACE}")
if not ITEM_EDITOR.exists():
    sys.exit(f"nao encontrei {ITEM_EDITOR} — rode primeiro o patch_5b1_item_editor.py")

src = WORKSPACE.read_text(encoding="utf-8")
orig = src

def replace_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

# 1. import do ItemEditor
src = replace_once(
    src,
    "import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';\n",
    "import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';\n"
    "import { ItemEditor } from './ItemEditor';\n",
    "import-item-editor",
)

# 2. handler updateItem
src = replace_once(
    src,
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n",
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n"
    "\n"
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n",
    "updateItem",
)

# 3. substitui tabela por map de ItemEditor (sem trailing spaces nos <td>)
OLD_TABLE = '''            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th className="text-left py-1 pr-2">#</th>
                    <th className="text-left py-1 pr-2">C\u00f3digo</th>
                    <th className="text-left py-1 pr-2">Descri\u00e7\u00e3o</th>
                    <th className="text-right py-1 pr-2">Qtd</th>
                    <th className="text-left py-1 pr-2">Un</th>
                    <th className="text-left py-1 pr-2">Norma</th>
                    <th className="text-left py-1 pr-2">Lote</th>
                    <th className="text-left py-1 pr-2">Rastreab.</th>
                    <th className="text-left py-1">Incl.</th>
                  </tr>
                </thead>
                <tbody>
                  {form.itens.map((it, idx) => (
                    <tr
                      key={it.id ?? idx}
                      className={
                        it.incluir_no_certificado === false
                          ? 'border-b border-border/50 bg-amber-50/30 dark:bg-amber-900/10'
                          : 'border-b border-border/50'
                      }
                    >
                      <td className="py-1 pr-2 tabular-nums">{it.ordem}</td>
                      <td className="py-1 pr-2 font-mono">{it.codigo_produto}</td>
                      <td className="py-1 pr-2">{it.descricao_material}</td>
                      <td className="py-1 pr-2 text-right tabular-nums">{it.quantidade}</td>
                      <td className="py-1 pr-2">{it.unidade}</td>
                      <td className="py-1 pr-2">{it.norma}</td>
                      <td className="py-1 pr-2">{it.lote || ''}</td>
                      <td className="py-1 pr-2">
                        {it.incluir_no_certificado !== false && it.rastreabilidade_status ? (
                          <span
                            className={
                              it.rastreabilidade_status === 'COMPLETA'
                                ? 'erp-badge-success text-[10px]'
                                : it.rastreabilidade_status === 'PARCIAL'
                                  ? 'erp-badge-warning text-[10px]'
                                  : 'erp-badge-danger text-[10px]'
                            }
                          >
                            {it.rastreabilidade_label || it.rastreabilidade_status}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">\u2014</span>
                        )}
                      </td>
                      <td className="py-1">
                        {it.incluir_no_certificado === false ? (
                          <span className="text-amber-700 dark:text-amber-300">N\u00e3o</span>
                        ) : (
                          <span className="text-emerald-700 dark:text-emerald-400">Sim</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
'''
NEW_EDITOR_LIST = '''            <div className="space-y-2">
              {form.itens.map((it, idx) => (
                <ItemEditor
                  key={it.id ?? idx}
                  item={it}
                  idx={idx}
                  disabled={nfeBloqueada || saving}
                  onChange={(patch) => updateItem(idx, patch)}
                />
              ))}
            </div>
'''
src = replace_once(src, OLD_TABLE, NEW_EDITOR_LIST, "substitui-tabela")

# 4. placeholder cinza
src = replace_once(
    src,
    "        <p className=\"font-medium mb-1\">Editor de item, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5: editor \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>\n",
    "        <p className=\"font-medium mb-1\">Corrida/lote, composi\u00e7\u00e3o, componentes, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5b-2/3/4: corrida/composi\u00e7\u00e3o/componentes \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>\n",
    "placeholder-atualizado",
)

# backup + write
if src == orig:
    sys.exit("nada mudou no Workspace — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = WORKSPACE.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(WORKSPACE, backup)
WORKSPACE.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {WORKSPACE} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
