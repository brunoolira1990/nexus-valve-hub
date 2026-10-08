#!/usr/bin/env python3
"""Etapa 5b-2a (B) — states/handlers de corrida + props pro ItemEditor."""
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

# 1. imports adicionais
src = replace_once(
    src,
    "import { ItemEditor } from './ItemEditor';\n",
    "import { ItemEditor } from './ItemEditor';\n"
    "import { produtosService } from '@/services/api/produtos';\n"
    "import { baseItemIrmao } from '@/lib/cqCorridasCfUi';\n"
    "import { mesclarMensagensUnicas } from '@/lib/cqMensagensUi';\n"
    "import { coerceProdutoItemId } from '@/lib/certificadoQualidadeConstants';\n",
    "imports-libs",
)

src = replace_once(
    src,
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  ItemCertificadoQualidade,\n"
    "} from '@/types';\n",
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "imports-types",
)

# 2. states adicionais
src = replace_once(
    src,
    "  const [abaAtiva, setAbaAtiva] = useState('dados');\n",
    "  const [abaAtiva, setAbaAtiva] = useState('dados');\n"
    "  const [produtoBusca, setProdutoBusca] = useState<Record<number, string>>({});\n"
    "  const [produtoResultados, setProdutoResultados] = useState<Record<number, Produto[]>>({});\n"
    "  const [corridasDisponiveisPorItem, setCorridasDisponiveisPorItem] = useState<\n"
    "    Record<number, CorridaDisponivelCertificadoQualidade[]>\n"
    "  >({});\n",
    "states",
)

# 3. handlers (depois do updateItem existente)
src = replace_once(
    src,
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n",
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n"
    "\n"
    "  const adicionarMensagensUnicas = (novas: string | string[]) =>\n"
    "    setMensagens((m) => mesclarMensagensUnicas(m, novas));\n"
    "\n"
    "  const buscarProdutosParaItem = async (idx: number, termo: string) => {\n"
    "    setProdutoBusca((p) => ({ ...p, [idx]: termo }));\n"
    "    const query = termo.trim();\n"
    "    if (query.length < 2) {\n"
    "      setProdutoResultados((p) => ({ ...p, [idx]: [] }));\n"
    "      return;\n"
    "    }\n"
    "    try {\n"
    "      const encontrados = await produtosService.search(query, 20);\n"
    "      setProdutoResultados((p) => ({ ...p, [idx]: encontrados }));\n"
    "    } catch {\n"
    "      setProdutoResultados((p) => ({ ...p, [idx]: [] }));\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const vincularProdutoAoItem = async (idx: number, produto: Produto) => {\n"
    "    updateItem(idx, {\n"
    "      produto: produto.id,\n"
    "      produto_codigo: produto.codigo_completo,\n"
    "      produto_descricao: produto.descricao,\n"
    "      produto_ncm_efetivo: produto.ncm_efetivo?.codigo || produto.ncm || '',\n"
    "      status_vinculo_produto: 'VINCULADO',\n"
    "      origem_observacoes: '',\n"
    "    });\n"
    "    setProdutoBusca((p) => ({ ...p, [idx]: `${produto.codigo_completo} - ${produto.descricao}` }));\n"
    "    setProdutoResultados((p) => ({ ...p, [idx]: [] }));\n"
    "    try {\n"
    "      const corridas = await certificadosQualidadeService.corridasDisponiveisPorProduto(produto.id);\n"
    "      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: corridas }));\n"
    "      if (!corridas.length) {\n"
    "        adicionarMensagensUnicas('Nenhuma corrida/lote disponivel para este produto.');\n"
    "      }\n"
    "    } catch {\n"
    "      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: [] }));\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const carregarCorridasDoItem = async (idx: number) => {\n"
    "    const produtoId = coerceProdutoItemId(form.itens[idx]?.produto);\n"
    "    if (!produtoId) return;\n"
    "    try {\n"
    "      const corridas = await certificadosQualidadeService.corridasDisponiveisPorProduto(produtoId);\n"
    "      setCorridasDisponiveisPorItem((p) => ({ ...p, [idx]: corridas }));\n"
    "    } catch (e) {\n"
    "      setSaveError(apiErrorMessage(e));\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const construirItemIrmaoDeCorrida = (\n"
    "    idx: number,\n"
    "    source: CorridaDisponivelCertificadoQualidade,\n"
    "    quantidade: string,\n"
    "  ): ItemCertificadoQualidade => {\n"
    "    const item = form.itens[idx];\n"
    "    return {\n"
    "      ...baseItemIrmao(item),\n"
    "      corrida: source.corrida || item.corrida,\n"
    "      lote: source.lote || item.lote || '',\n"
    "      quantidade: parseFloat(quantidade) || 0,\n"
    "      norma: source.norma || item.norma,\n"
    "      ncm: source.ncm || item.ncm || '',\n"
    "      composicao_json: ensureMap(source.composicao_json),\n"
    "      ensaio_tracao_json: ensureMap(source.ensaio_tracao_json),\n"
    "      ensaio_impacto_json: ensureMap(source.ensaio_impacto_json),\n"
    "      certificado_fornecedor_origem_id:\n"
    "        source.certificado_fornecedor_origem_id ?? source.certificado_fornecedor_id ?? null,\n"
    "      item_certificado_fornecedor_origem_id:\n"
    "        source.item_certificado_fornecedor_origem_id ?? source.item_certificado_fornecedor_id ?? null,\n"
    "      fornecedor_nome_snapshot: source.fornecedor || '',\n"
    "      nf_entrada_snapshot: source.nf_entrada || '',\n"
    "      numero_certificado_fornecedor_item_snapshot:\n"
    "        source.numero_certificado_fornecedor_item || source.certificado_fornecedor || '',\n"
    "      corrida_snapshot: source.corrida || '',\n"
    "      lote_snapshot: source.lote || '',\n"
    "      origem_rastreabilidade_tipo: source.origem || 'manual',\n"
    "      origem_status_tecnico:\n"
    "        source.status_origem_tecnica ||\n"
    "        (source.tem_dados_tecnicos ? 'dados_tecnicos' : 'sem_dados_tecnicos'),\n"
    "      origem_observacoes: source.observacoes_origem || '',\n"
    "    };\n"
    "  };\n"
    "\n"
    "  const aplicarCorridaDisponivel = (idx: number, valorSelecao: string) => {\n"
    "    const item = form.itens[idx];\n"
    "    const source = (corridasDisponiveisPorItem[idx] || []).find(\n"
    "      (c) =>\n"
    "        (c.valor_selecao && c.valor_selecao === valorSelecao) ||\n"
    "        `${c.corrida}||${c.lote || ''}` === valorSelecao,\n"
    "    );\n"
    "    if (!source) return;\n"
    "    if (source.status_certificado_fornecedor === 'rascunho') {\n"
    "      const ok = window.confirm(\n"
    "        'Dados tecnicos encontrados em certificado fornecedor em rascunho. Use com confirmacao ou registre o certificado fornecedor antes de emitir. Deseja aplicar estes dados?',\n"
    "      );\n"
    "      if (!ok) return;\n"
    "    }\n"
    "    const alertas = [...(source.alertas || [])];\n"
    "    const existeDivergenciaNcm = Boolean(item.ncm && source.ncm && item.ncm !== source.ncm);\n"
    "    if (existeDivergenciaNcm) {\n"
    "      alertas.push(\n"
    "        'A corrida foi encontrada, mas ha divergencia entre descricao/NCM/norma da origem e do item de saida. Confira antes de aplicar.',\n"
    "      );\n"
    "    }\n"
    "    const quantidadeItem = item.quantidade || 0;\n"
    "    updateItem(idx, construirItemIrmaoDeCorrida(idx, source, String(quantidadeItem)));\n"
    "    if (alertas.length) {\n"
    "      adicionarMensagensUnicas(alertas);\n"
    "    }\n"
    "  };\n",
    "handlers-corrida",
)

# 4. passa props pro ItemEditor
src = replace_once(
    src,
    "                <ItemEditor\n"
    "                  key={it.id ?? idx}\n"
    "                  item={it}\n"
    "                  idx={idx}\n"
    "                  disabled={nfeBloqueada || saving}\n"
    "                  onChange={(patch) => updateItem(idx, patch)}\n"
    "                />\n",
    "                <ItemEditor\n"
    "                  key={it.id ?? idx}\n"
    "                  item={it}\n"
    "                  idx={idx}\n"
    "                  disabled={nfeBloqueada || saving}\n"
    "                  onChange={(patch) => updateItem(idx, patch)}\n"
    "                  corridas={{\n"
    "                    produtoBusca: produtoBusca[idx],\n"
    "                    produtoResultados: produtoResultados[idx] || [],\n"
    "                    corridasDisponiveis: corridasDisponiveisPorItem[idx] || [],\n"
    "                    onBuscarProdutos: (term) => void buscarProdutosParaItem(idx, term),\n"
    "                    onVincularProduto: (p) => void vincularProdutoAoItem(idx, p),\n"
    "                    onCarregarCorridas: () => void carregarCorridasDoItem(idx),\n"
    "                    onAplicarCorrida: (v) => aplicarCorridaDisponivel(idx, v),\n"
    "                  }}\n"
    "                />\n",
    "props-item-editor",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
