#!/usr/bin/env python3
"""Etapa 5b-2b (B) — state/handlers de divisao em itens irmaos."""
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

# 1. import do tipo LinhaDivisaoCorrida
src = replace_once(
    src,
    "import { ItemEditor } from './ItemEditor';\n",
    "import { ItemEditor, type LinhaDivisaoCorrida } from './ItemEditor';\n",
    "import-linha-divisao",
)

# 2. state dividindoCorridas
src = replace_once(
    src,
    "  const [corridasDisponiveisPorItem, setCorridasDisponiveisPorItem] = useState<\n"
    "    Record<number, CorridaDisponivelCertificadoQualidade[]>\n"
    "  >({});\n",
    "  const [corridasDisponiveisPorItem, setCorridasDisponiveisPorItem] = useState<\n"
    "    Record<number, CorridaDisponivelCertificadoQualidade[]>\n"
    "  >({});\n"
    "  const [dividindoCorridas, setDividindoCorridas] = useState<\n"
    "    Record<number, LinhaDivisaoCorrida[]>\n"
    "  >({});\n",
    "state-dividindo",
)

# 3. handlers (depois de aplicarCorridaDisponivel)
src = replace_once(
    src,
    "    const quantidadeItem = item.quantidade || 0;\n"
    "    updateItem(idx, construirItemIrmaoDeCorrida(idx, source, String(quantidadeItem)));\n"
    "    if (alertas.length) {\n"
    "      adicionarMensagensUnicas(alertas);\n"
    "    }\n"
    "  };\n",
    "    const quantidadeItem = item.quantidade || 0;\n"
    "    updateItem(idx, construirItemIrmaoDeCorrida(idx, source, String(quantidadeItem)));\n"
    "    if (alertas.length) {\n"
    "      adicionarMensagensUnicas(alertas);\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const addLinhaCorrida = (idx: number) =>\n"
    "    setDividindoCorridas((prev) => ({\n"
    "      ...prev,\n"
    "      [idx]: [\n"
    "        ...(prev[idx] || []),\n"
    "        { corrida: '', lote: '', quantidade: '', valorSelecao: '' },\n"
    "      ],\n"
    "    }));\n"
    "\n"
    "  const removeLinhaCorrida = (idx: number, linhaIdx: number) =>\n"
    "    setDividindoCorridas((prev) => {\n"
    "      const linhas = prev[idx] || [];\n"
    "      const next = [...linhas];\n"
    "      next.splice(linhaIdx, 1);\n"
    "      const out: Record<number, LinhaDivisaoCorrida[]> = { ...prev };\n"
    "      if (next.length > 0) out[idx] = next;\n"
    "      else delete out[idx];\n"
    "      return out;\n"
    "    });\n"
    "\n"
    "  const updateLinhaCorrida = (\n"
    "    idx: number,\n"
    "    linhaIdx: number,\n"
    "    patch: Partial<LinhaDivisaoCorrida>,\n"
    "  ) =>\n"
    "    setDividindoCorridas((prev) => {\n"
    "      const linhas = prev[idx] || [];\n"
    "      const next = [...linhas];\n"
    "      next[linhaIdx] = { ...next[linhaIdx], ...patch };\n"
    "      return { ...prev, [idx]: next };\n"
    "    });\n"
    "\n"
    "  const hasCorridaDuplicada = (idx: number): boolean => {\n"
    "    const linhas = dividindoCorridas[idx] || [];\n"
    "    const chaves = new Set<string>();\n"
    "    for (const l of linhas) {\n"
    "      const chave = (l.valorSelecao || '').trim().toUpperCase();\n"
    "      if (!chave) continue;\n"
    "      if (chaves.has(chave)) return true;\n"
    "      chaves.add(chave);\n"
    "    }\n"
    "    return false;\n"
    "  };\n"
    "\n"
    "  const aplicarDistribuicaoCorridas = (idx: number) => {\n"
    "    const linhas = dividindoCorridas[idx] || [];\n"
    "    if (!linhas.length) return;\n"
    "\n"
    "    const linhasInvalidas = linhas.some(\n"
    "      (l) => !l.valorSelecao || !l.quantidade || parseFloat(l.quantidade) <= 0,\n"
    "    );\n"
    "    if (linhasInvalidas) {\n"
    "      adicionarMensagensUnicas(['Informe corrida e quantidade > 0 para todas as linhas.']);\n"
    "      return;\n"
    "    }\n"
    "\n"
    "    const quantidadeOriginal = form.itens[idx].quantidade || 0;\n"
    "    const somaTotal = linhas.reduce((sum, l) => sum + parseFloat(l.quantidade), 0);\n"
    "    if (Math.abs(somaTotal - quantidadeOriginal) > 0.001) {\n"
    "      adicionarMensagensUnicas([\n"
    "        `A soma das quantidades (${somaTotal}) deve ser igual a quantidade do item original (${quantidadeOriginal}).`,\n"
    "      ]);\n"
    "      return;\n"
    "    }\n"
    "\n"
    "    const chaves = new Set<string>();\n"
    "    for (const l of linhas) {\n"
    "      const chave = (l.valorSelecao || '').trim().toUpperCase();\n"
    "      if (chaves.has(chave)) {\n"
    "        adicionarMensagensUnicas(['A mesma corrida nao pode ser adicionada duas vezes.']);\n"
    "        return;\n"
    "      }\n"
    "      chaves.add(chave);\n"
    "    }\n"
    "\n"
    "    const novosItens: ItemCertificadoQualidade[] = [];\n"
    "    for (const l of linhas) {\n"
    "      const source = (corridasDisponiveisPorItem[idx] || []).find(\n"
    "        (c) =>\n"
    "          (c.valor_selecao && c.valor_selecao === l.valorSelecao) ||\n"
    "          `${c.corrida}||${c.lote || ''}` === l.valorSelecao,\n"
    "      );\n"
    "      if (!source) continue;\n"
    "      const itemIrmao = construirItemIrmaoDeCorrida(idx, source, l.quantidade);\n"
    "      itemIrmao.corrida = source.corrida || '';\n"
    "      itemIrmao.lote = source.lote || '';\n"
    "      itemIrmao.quantidade = parseFloat(l.quantidade);\n"
    "      novosItens.push(itemIrmao);\n"
    "    }\n"
    "\n"
    "    const itemOriginal = form.itens[idx];\n"
    "    const novosItensOrdenados = novosItens.map((it, i) => ({\n"
    "      ...it,\n"
    "      ordem: (itemOriginal.ordem || idx + 1) + i,\n"
    "    }));\n"
    "\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      next.splice(idx, 1, ...novosItensOrdenados);\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "\n"
    "    setDividindoCorridas({});\n"
    "    setCorridasDisponiveisPorItem({});\n"
    "    setProdutoBusca({});\n"
    "    setProdutoResultados({});\n"
    "  };\n",
    "handlers-divisao",
)

# 4. props no ItemEditor
src = replace_once(
    src,
    "                  corridas={{\n"
    "                    produtoBusca: produtoBusca[idx],\n"
    "                    produtoResultados: produtoResultados[idx] || [],\n"
    "                    corridasDisponiveis: corridasDisponiveisPorItem[idx] || [],\n"
    "                    onBuscarProdutos: (term) => void buscarProdutosParaItem(idx, term),\n"
    "                    onVincularProduto: (p) => void vincularProdutoAoItem(idx, p),\n"
    "                    onCarregarCorridas: () => void carregarCorridasDoItem(idx),\n"
    "                    onAplicarCorrida: (v) => aplicarCorridaDisponivel(idx, v),\n"
    "                  }}\n",
    "                  corridas={{\n"
    "                    produtoBusca: produtoBusca[idx],\n"
    "                    produtoResultados: produtoResultados[idx] || [],\n"
    "                    corridasDisponiveis: corridasDisponiveisPorItem[idx] || [],\n"
    "                    onBuscarProdutos: (term) => void buscarProdutosParaItem(idx, term),\n"
    "                    onVincularProduto: (p) => void vincularProdutoAoItem(idx, p),\n"
    "                    onCarregarCorridas: () => void carregarCorridasDoItem(idx),\n"
    "                    onAplicarCorrida: (v) => aplicarCorridaDisponivel(idx, v),\n"
    "                    dividindo: dividindoCorridas[idx] || [],\n"
    "                    temCorridaDuplicada: hasCorridaDuplicada(idx),\n"
    "                    onAddLinha: () => addLinhaCorrida(idx),\n"
    "                    onRemoveLinha: (linhaIdx) => removeLinhaCorrida(idx, linhaIdx),\n"
    "                    onUpdateLinha: (linhaIdx, patch) => updateLinhaCorrida(idx, linhaIdx, patch),\n"
    "                    onAplicarDistribuicao: () => aplicarDistribuicaoCorridas(idx),\n"
    "                  }}\n",
    "props-divisao",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
