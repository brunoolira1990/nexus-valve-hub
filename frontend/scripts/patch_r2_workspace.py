#!/usr/bin/env python3
"""Rodada 2 (B) — states + handlers + integracao com modal de resultados."""
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

# 1. states novos
src = replace_once(
    src,
    "  const [fornecedorBuscaItemMsg, setFornecedorBuscaItemMsg] = useState<\n"
    "    Record<number, { type: 'error' | 'info'; text: string }>\n"
    "  >({});\n",
    "  const [fornecedorBuscaItemMsg, setFornecedorBuscaItemMsg] = useState<\n"
    "    Record<number, { type: 'error' | 'info'; text: string }>\n"
    "  >({});\n"
    "  const [fornecedorTargetCompIdx, setFornecedorTargetCompIdx] = useState<number | null>(\n"
    "    null,\n"
    "  );\n"
    "  const [fornecedorBuscaCompLoading, setFornecedorBuscaCompLoading] = useState<\n"
    "    number | null\n"
    "  >(null);\n"
    "  const [fornecedorBuscaCompMsg, setFornecedorBuscaCompMsg] = useState<\n"
    "    Record<string, { type: 'error' | 'info'; text: string }>\n"
    "  >({});\n",
    "states-2",
)

# 2. handlers novos antes de buscarDadosFornecedor
src = replace_once(
    src,
    "  const buscarDadosFornecedor = async (idx: number) => {\n",
    "  const aplicarDadosFornecedorComponente = (\n"
    "    idx: number,\n"
    "    compIdx: number,\n"
    "    srcData: DadosTecnicosFornecedorResultado,\n"
    "  ) => {\n"
    "    const item = form.itens[idx];\n"
    "    const comps = [...(item.componentes || [])];\n"
    "    if (!comps[compIdx]) return;\n"
    "    const compAlvo = ensureComp(comps[compIdx], compIdx + 1);\n"
    "    const corridaAlvo = (compAlvo.corrida || '').trim().toUpperCase();\n"
    "    const loteAlvo = (compAlvo.lote || '').trim().toUpperCase();\n"
    "    const listaSrc = srcData.componentes || [];\n"
    "    const match =\n"
    "      listaSrc.find((c) => {\n"
    "        const cCorrida = String(c.corrida || '').trim().toUpperCase();\n"
    "        const cLote = String(c.lote || '').trim().toUpperCase();\n"
    "        return cCorrida === corridaAlvo && cLote === loteAlvo;\n"
    "      }) || listaSrc[0];\n"
    "    if (!match) {\n"
    "      setFornecedorBuscaCompMsg((p) => ({\n"
    "        ...p,\n"
    "        [`${idx}:${compIdx}`]: {\n"
    "          type: 'error',\n"
    "          text: 'Nenhum componente compativel foi retornado pelo CF.',\n"
    "        },\n"
    "      }));\n"
    "      return;\n"
    "    }\n"
    "    comps[compIdx] = {\n"
    "      ...compAlvo,\n"
    "      corrida: String(match.corrida || compAlvo.corrida || ''),\n"
    "      lote: String(match.lote || compAlvo.lote || ''),\n"
    "      norma: String(match.norma || compAlvo.norma || ''),\n"
    "      descricao_componente:\n"
    "        String(match.descricao_componente || compAlvo.descricao_componente || ''),\n"
    "      numero_certificado_fornecedor_componente_snapshot:\n"
    "        String(match.numero_certificado_fornecedor_componente || '') ||\n"
    "        srcData.numero_certificado_fornecedor_item ||\n"
    "        srcData.numero_certificado_fornecedor ||\n"
    "        '',\n"
    "      composicao_json: ensureMap(match.composicao_json),\n"
    "      ensaio_tracao_json: ensureMap(match.ensaio_tracao_json),\n"
    "      ensaio_impacto_json: ensureMap(match.ensaio_impacto_json),\n"
    "    };\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "    updateItem(idx, {\n"
    "      certificado_fornecedor_origem_id:\n"
    "        item.certificado_fornecedor_origem_id || srcData.certificado_fornecedor_id || null,\n"
    "      item_certificado_fornecedor_origem_id:\n"
    "        item.item_certificado_fornecedor_origem_id || srcData.id || null,\n"
    "    });\n"
    "    adicionarMensagensUnicas([\n"
    "      `Componente ${compAlvo.nome_componente || compIdx + 1}: dados do CF aplicados.`,\n"
    "    ]);\n"
    "    setFornecedorBuscaCompMsg((p) => {\n"
    "      const next = { ...p };\n"
    "      delete next[`${idx}:${compIdx}`];\n"
    "      return next;\n"
    "    });\n"
    "  };\n"
    "\n"
    "  const buscarDadosCorridaComponente = async (idx: number, compIdx: number) => {\n"
    "    const chave = `${idx}:${compIdx}`;\n"
    "    setFornecedorBuscaCompMsg((p) => {\n"
    "      const next = { ...p };\n"
    "      delete next[chave];\n"
    "      return next;\n"
    "    });\n"
    "    const item = form.itens[idx];\n"
    "    const comp = ensureComp(item.componentes?.[compIdx], compIdx + 1);\n"
    "    const corrida = (comp.corrida || '').trim();\n"
    "    const lote = (comp.lote || '').trim();\n"
    "    if (!corrida && !lote) {\n"
    "      setFornecedorBuscaCompMsg((p) => ({\n"
    "        ...p,\n"
    "        [chave]: {\n"
    "          type: 'error',\n"
    "          text: 'Informe a corrida ou o lote deste componente antes de buscar.',\n"
    "        },\n"
    "      }));\n"
    "      return;\n"
    "    }\n"
    "    setFornecedorBuscaCompLoading(compIdx);\n"
    "    try {\n"
    "      const { resultados: encontrados, dicas_busca: dicasBusca } =\n"
    "        await certificadosFornecedorService.buscarDadosTecnicos({\n"
    "          corrida: corrida || undefined,\n"
    "          lote: lote || undefined,\n"
    "          codigo_produto: item.codigo_produto || undefined,\n"
    "          descricao: comp.nome_componente || item.descricao_material || undefined,\n"
    "          norma: comp.norma || item.norma || undefined,\n"
    "          tipo_dados_tecnicos: 'VALVULA_COMPONENTES',\n"
    "          status: 'registrado',\n"
    "        });\n"
    "      if (!encontrados.length) {\n"
    "        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicasBusca);\n"
    "        setFornecedorBuscaCompMsg((p) => ({\n"
    "          ...p,\n"
    "          [chave]: {\n"
    "            type: 'error',\n"
    "            text:\n"
    "              dicaMsg ||\n"
    "              'Nenhum dado tecnico encontrado para esta corrida do componente.',\n"
    "          },\n"
    "        }));\n"
    "        return;\n"
    "      }\n"
    "      if (encontrados.length === 1) {\n"
    "        aplicarDadosFornecedorComponente(idx, compIdx, encontrados[0]);\n"
    "        return;\n"
    "      }\n"
    "      setFornecedorTargetIdx(idx);\n"
    "      setFornecedorTargetCompIdx(compIdx);\n"
    "      setFornecedorMatches(encontrados);\n"
    "      setFornecedorMatchModalOpen(true);\n"
    "    } catch (e) {\n"
    "      setFornecedorBuscaCompMsg((p) => ({\n"
    "        ...p,\n"
    "        [chave]: {\n"
    "          type: 'error',\n"
    "          text: apiErrorMessage(e, {\n"
    "            fallback: 'Falha ao buscar dados tecnicos da corrida.',\n"
    "          }),\n"
    "        },\n"
    "      }));\n"
    "    } finally {\n"
    "      setFornecedorBuscaCompLoading(null);\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const buscarDadosFornecedor = async (idx: number) => {\n",
    "handlers-2",
)

# 3. modal roteia pro comp quando aplicavel
src = replace_once(
    src,
    "                    if (fornecedorTargetIdx == null) return;\n"
    "                    aplicarDadosFornecedor(fornecedorTargetIdx, r);\n"
    "                    setFornecedorMatchModalOpen(false);\n",
    "                    if (fornecedorTargetIdx == null) return;\n"
    "                    if (fornecedorTargetCompIdx != null) {\n"
    "                      aplicarDadosFornecedorComponente(\n"
    "                        fornecedorTargetIdx,\n"
    "                        fornecedorTargetCompIdx,\n"
    "                        r,\n"
    "                      );\n"
    "                    } else {\n"
    "                      aplicarDadosFornecedor(fornecedorTargetIdx, r);\n"
    "                    }\n"
    "                    setFornecedorMatchModalOpen(false);\n"
    "                    setFornecedorTargetCompIdx(null);\n",
    "modal-roteamento",
)

# 4. props novas no ItemEditor
src = replace_once(
    src,
    "                    onUpdate: (compIdx, patch) => updateComponente(idx, compIdx, patch),\n"
    "                    onUpdateJson: (compIdx, group, key, value) =>\n"
    "                      updateCompJson(idx, compIdx, group, key, value),\n"
    "                  }}\n",
    "                    onUpdate: (compIdx, patch) => updateComponente(idx, compIdx, patch),\n"
    "                    onUpdateJson: (compIdx, group, key, value) =>\n"
    "                      updateCompJson(idx, compIdx, group, key, value),\n"
    "                    onBuscarDadosCorrida: (compIdx) =>\n"
    "                      void buscarDadosCorridaComponente(idx, compIdx),\n"
    "                    fornecedorBuscaCompLoading,\n"
    "                    fornecedorBuscaCompMsg: Object.keys(fornecedorBuscaCompMsg)\n"
    "                      .filter((k) => k.startsWith(`${idx}:`))\n"
    "                      .map((k) => fornecedorBuscaCompMsg[k])\n"
    "                      .find(Boolean) || null,\n"
    "                  }}\n",
    "props-item-comp",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
