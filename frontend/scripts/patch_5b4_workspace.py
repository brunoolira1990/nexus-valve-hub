#!/usr/bin/env python3
"""Etapa 5b-4 (B) — handlers de componentes + props no ItemEditor."""
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

# 1. import de COMPONENTES_PADRAO + ensureComp
src = replace_once(
    src,
    "import { produtosService } from '@/services/api/produtos';\n",
    "import { produtosService } from '@/services/api/produtos';\n"
    "import {\n"
    "  COMPONENTES_PADRAO,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import-componentes-padrao",
)

# 2. import do tipo ItemCertificadoQualidadeComponente
src = replace_once(
    src,
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  ItemCertificadoQualidadeComponente,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "import-tipo-componente",
)

# 3. handlers de componentes (depois de aplicarDistribuicaoCorridas)
src = replace_once(
    src,
    "    setDividindoCorridas({});\n"
    "    setCorridasDisponiveisPorItem({});\n"
    "    setProdutoBusca({});\n"
    "    setProdutoResultados({});\n"
    "  };\n",
    "    setDividindoCorridas({});\n"
    "    setCorridasDisponiveisPorItem({});\n"
    "    setProdutoBusca({});\n"
    "    setProdutoResultados({});\n"
    "  };\n"
    "\n"
    "  const updateComponente = (\n"
    "    idx: number,\n"
    "    compIdx: number,\n"
    "    patch: Partial<ItemCertificadoQualidadeComponente>,\n"
    "  ) =>\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      comps[compIdx] = { ...comps[compIdx], ...patch };\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "\n"
    "  const updateCompJson = (\n"
    "    idx: number,\n"
    "    compIdx: number,\n"
    "    group: 'composicao_json' | 'ensaio_tracao_json' | 'ensaio_impacto_json',\n"
    "    key: string,\n"
    "    value: string,\n"
    "  ) =>\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      const map = ensureMap(comps[compIdx][group]);\n"
    "      map[key] = value;\n"
    "      comps[compIdx] = { ...comps[compIdx], [group]: map };\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "\n"
    "  const addComponente = (idx: number, nome = '') =>\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "\n"
    "  const removeComponente = (idx: number, compIdx: number) =>\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      comps.splice(compIdx, 1);\n"
    "      next[idx] = {\n"
    "        ...next[idx],\n"
    "        componentes: comps.map((c, i) => ({ ...c, ordem: i + 1 })),\n"
    "      };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "\n"
    "  const duplicarComponente = (idx: number, compIdx: number) => {\n"
    "    const srcComp = ensureComp(form.itens[idx].componentes?.[compIdx], 1);\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      comps.push({ ...srcComp, ordem: comps.length + 1 });\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "  };\n"
    "\n"
    "  const copiarComponenteAnterior = (idx: number, compIdx: number) => {\n"
    "    if (compIdx === 0) return;\n"
    "    const prev = ensureComp(form.itens[idx].componentes?.[compIdx - 1], compIdx);\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      comps[compIdx] = { ...comps[compIdx], ...prev, ordem: comps[compIdx].ordem };\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "  };\n"
    "\n"
    "  const adicionarComponentesPadrao = (idx: number) =>\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      COMPONENTES_PADRAO.forEach((nome) => {\n"
    "        comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));\n"
    "      });\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n",
    "handlers-componentes",
)

# 4. props no ItemEditor
src = replace_once(
    src,
    "                    onAplicarDistribuicao: () => aplicarDistribuicaoCorridas(idx),\n"
    "                  }}\n"
    "                />\n",
    "                    onAplicarDistribuicao: () => aplicarDistribuicaoCorridas(idx),\n"
    "                  }}\n"
    "                  componentes={{\n"
    "                    lista: it.componentes || [],\n"
    "                    onAdd: (nome?: string) => addComponente(idx, nome),\n"
    "                    onAddPadrao: () => adicionarComponentesPadrao(idx),\n"
    "                    onRemove: (compIdx: number) => removeComponente(idx, compIdx),\n"
    "                    onDuplicar: (compIdx: number) => duplicarComponente(idx, compIdx),\n"
    "                    onCopiarAnterior: (compIdx: number) =>\n"
    "                      copiarComponenteAnterior(idx, compIdx),\n"
    "                    onUpdate: (compIdx, patch) => updateComponente(idx, compIdx, patch),\n"
    "                    onUpdateJson: (compIdx, group, key, value) =>\n"
    "                      updateCompJson(idx, compIdx, group, key, value),\n"
    "                  }}\n"
    "                />\n",
    "props-componentes",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
