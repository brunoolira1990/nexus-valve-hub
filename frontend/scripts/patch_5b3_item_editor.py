#!/usr/bin/env python3
"""Etapa 5b-3 — composicao quimica + ensaios tracao/impacto no ItemEditor."""
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

# 1. import useState
src = replace_once(
    src,
    "import type {\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "import { useState } from 'react';\n"
    "\n"
    "import type {\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "import-useState",
)

# 2. estende import dos constants
src = replace_once(
    src,
    "import {\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "  MOTIVOS_NAO_INCLUSAO,\n"
    "  coerceProdutoItemId,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import {\n"
    "  COMPOSICAO_FIELDS,\n"
    "  IMPACTO_FIELDS,\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "  MOTIVOS_NAO_INCLUSAO,\n"
    "  TRACAO_FIELDS,\n"
    "  coerceProdutoItemId,\n"
    "  ensureMap,\n"
    "  normNumeric,\n"
    "  parseBlockValues,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import-constants",
)

# 3. state paste + helpers
src = replace_once(
    src,
    "export function ItemEditor({ item: it, idx, disabled, onChange, corridas }: Props) {\n"
    "  const incl = it.incluir_no_certificado !== false;\n",
    "export function ItemEditor({ item: it, idx, disabled, onChange, corridas }: Props) {\n"
    "  const incl = it.incluir_no_certificado !== false;\n"
    "  const [pasteCompOpen, setPasteCompOpen] = useState(false);\n"
    "  const [pasteCompText, setPasteCompText] = useState('');\n"
    "\n"
    "  const updateJson = (\n"
    "    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',\n"
    "    key: string,\n"
    "    value: string,\n"
    "  ) => {\n"
    "    const current = ensureMap(it[group]);\n"
    "    onChange({ [group]: { ...current, [key]: value } });\n"
    "  };\n"
    "\n"
    "  const applyCompositionBlock = () => {\n"
    "    const values = parseBlockValues(pasteCompText);\n"
    "    if (!values.length) return;\n"
    "    const next = { ...ensureMap(it.composicao_json) };\n"
    "    COMPOSICAO_FIELDS.forEach((field, i) => {\n"
    "      if (values[i] != null) next[field] = normNumeric(values[i]);\n"
    "    });\n"
    "    onChange({ composicao_json: next });\n"
    "    setPasteCompOpen(false);\n"
    "    setPasteCompText('');\n"
    "  };\n",
    "helpers",
)

# 4. bloco JSX (composicao + tracao + impacto) — antes do fechamento do grid
OLD_END = (
    "        </div>\n"
    "      </div>\n"
    "    </details>\n"
    "  );\n"
    "}\n"
)
NEW_END = (
    "        </div>\n"
    "\n"
    "        {incl && it.tipo_dados_tecnicos !== 'VALVULA_COMPONENTES' ? (\n"
    "          <>\n"
    "            <div className=\"md:col-span-6 rounded border border-border p-2\">\n"
    "              <div className=\"flex items-center justify-between mb-2 gap-2\">\n"
    "                <p className=\"text-xs font-semibold\">Composi\u00e7\u00e3o qu\u00edmica{LABEL_OBRIGATORIO_EMITIR}</p>\n"
    "                <button\n"
    "                  type=\"button\"\n"
    "                  className=\"erp-btn-outline erp-btn-sm\"\n"
    "                  disabled={disabled}\n"
    "                  onClick={() => {\n"
    "                    setPasteCompOpen((cur) => !cur);\n"
    "                    setPasteCompText('');\n"
    "                  }}\n"
    "                >\n"
    "                  Colar composi\u00e7\u00e3o em bloco\n"
    "                </button>\n"
    "              </div>\n"
    "              {pasteCompOpen ? (\n"
    "                <div className=\"mb-2 rounded border border-border p-2 bg-muted/20\">\n"
    "                  <p className=\"text-xs text-muted-foreground mb-1\">\n"
    "                    Cole uma linha (Excel/tabulado) na ordem: {COMPOSICAO_FIELDS.join(', ')}.\n"
    "                  </p>\n"
    "                  <textarea\n"
    "                    className=\"erp-input h-16\"\n"
    "                    value={pasteCompText}\n"
    "                    onChange={(e) => setPasteCompText(e.target.value)}\n"
    "                  />\n"
    "                  <div className=\"flex gap-2 mt-2\">\n"
    "                    <button\n"
    "                      type=\"button\"\n"
    "                      className=\"erp-btn-outline erp-btn-sm\"\n"
    "                      onClick={applyCompositionBlock}\n"
    "                    >\n"
    "                      Aplicar na grade\n"
    "                    </button>\n"
    "                    <button\n"
    "                      type=\"button\"\n"
    "                      className=\"erp-btn-outline erp-btn-sm\"\n"
    "                      onClick={() => {\n"
    "                        setPasteCompOpen(false);\n"
    "                        setPasteCompText('');\n"
    "                      }}\n"
    "                    >\n"
    "                      Cancelar\n"
    "                    </button>\n"
    "                  </div>\n"
    "                </div>\n"
    "              ) : null}\n"
    "              <div className=\"grid grid-cols-2 md:grid-cols-6 lg:grid-cols-8 gap-2\">\n"
    "                {COMPOSICAO_FIELDS.map((el) => (\n"
    "                  <div key={el}>\n"
    "                    <label className=\"erp-label\">{el}</label>\n"
    "                    <input\n"
    "                      className=\"erp-input mt-1\"\n"
    "                      placeholder=\"***\"\n"
    "                      disabled={disabled}\n"
    "                      value={ensureMap(it.composicao_json)[el] || ''}\n"
    "                      onChange={(e) => updateJson('composicao_json', el, normNumeric(e.target.value))}\n"
    "                    />\n"
    "                  </div>\n"
    "                ))}\n"
    "              </div>\n"
    "            </div>\n"
    "            <div className=\"md:col-span-6 rounded border border-border p-2\">\n"
    "              <p className=\"text-xs font-semibold mb-2\">Teste de tra\u00e7\u00e3o{LABEL_OBRIGATORIO_EMITIR}</p>\n"
    "              <div className=\"grid grid-cols-1 md:grid-cols-2 gap-2\">\n"
    "                {TRACAO_FIELDS.map((f) => (\n"
    "                  <div key={f.key}>\n"
    "                    <label className=\"erp-label\">{f.label}</label>\n"
    "                    <input\n"
    "                      className=\"erp-input mt-1\"\n"
    "                      disabled={disabled}\n"
    "                      value={ensureMap(it.ensaio_tracao_json)[f.key] || ''}\n"
    "                      onChange={(e) => updateJson('ensaio_tracao_json', f.key, normNumeric(e.target.value))}\n"
    "                    />\n"
    "                  </div>\n"
    "                ))}\n"
    "              </div>\n"
    "            </div>\n"
    "            <div className=\"md:col-span-6 rounded border border-border p-2\">\n"
    "              <div className=\"flex items-center justify-between mb-2\">\n"
    "                <p className=\"text-xs font-semibold\">Teste de impacto</p>\n"
    "                <label className=\"text-xs flex items-center gap-1\">\n"
    "                  <input\n"
    "                    type=\"checkbox\"\n"
    "                    disabled={disabled}\n"
    "                    checked={ensureMap(it.ensaio_impacto_json).informar_impacto === 'true'}\n"
    "                    onChange={(e) => {\n"
    "                      const map = ensureMap(it.ensaio_impacto_json);\n"
    "                      map.informar_impacto = e.target.checked ? 'true' : '';\n"
    "                      if (!e.target.checked) {\n"
    "                        IMPACTO_FIELDS.forEach((f) => {\n"
    "                          map[f.key] = '';\n"
    "                        });\n"
    "                        map.nao_aplicavel = 'true';\n"
    "                      } else {\n"
    "                        map.nao_aplicavel = '';\n"
    "                      }\n"
    "                      onChange({ ensaio_impacto_json: map });\n"
    "                    }}\n"
    "                  />\n"
    "                  Informar teste de impacto\n"
    "                </label>\n"
    "              </div>\n"
    "              {ensureMap(it.ensaio_impacto_json).informar_impacto !== 'true' ? (\n"
    "                <p className=\"text-xs text-muted-foreground\">\n"
    "                  Impacto oculto por padr\u00e3o (n\u00e3o aplic\u00e1vel no uso di\u00e1rio).\n"
    "                </p>\n"
    "              ) : (\n"
    "                <div className=\"grid grid-cols-1 md:grid-cols-2 gap-2\">\n"
    "                  {IMPACTO_FIELDS.map((f) => (\n"
    "                    <div key={f.key}>\n"
    "                      <label className=\"erp-label\">{f.label}</label>\n"
    "                      <input\n"
    "                        className=\"erp-input mt-1\"\n"
    "                        disabled={disabled}\n"
    "                        value={ensureMap(it.ensaio_impacto_json)[f.key] || ''}\n"
    "                        onChange={(e) => updateJson('ensaio_impacto_json', f.key, normNumeric(e.target.value))}\n"
    "                      />\n"
    "                    </div>\n"
    "                  ))}\n"
    "                </div>\n"
    "              )}\n"
    "            </div>\n"
    "          </>\n"
    "        ) : null}\n"
    "      </div>\n"
    "    </details>\n"
    "  );\n"
    "}\n"
)
src = replace_once(src, OLD_END, NEW_END, "bloco-composicao")

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
