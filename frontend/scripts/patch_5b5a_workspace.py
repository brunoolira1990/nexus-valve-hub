#!/usr/bin/env python3
"""Rodada 1 (B) — states + handlers + modal de resultados no Workspace."""
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

# 1. import Modal
src = replace_once(
    src,
    "import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';\n",
    "import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';\n"
    "import { Modal } from '@/components/Modal';\n",
    "import-modal",
)

# 2. import service + helpers
src = replace_once(
    src,
    "import { produtosService } from '@/services/api/produtos';\n",
    "import { produtosService } from '@/services/api/produtos';\n"
    "import {\n"
    "  certificadosFornecedorService,\n"
    "  corridaLoteEfetivosResultadoFornecedor,\n"
    "  mensagemPrincipalBuscaDadosTecnicosFornecedor,\n"
    "} from '@/services/api/certificadosFornecedor';\n",
    "import-service",
)

# 3. helpers de constants
src = replace_once(
    src,
    "import {\n"
    "  COMPONENTES_PADRAO,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import {\n"
    "  COMPONENTES_PADRAO,\n"
    "  ensureComp,\n"
    "  ensureMap,\n"
    "  fornecedorResultadoSemProdutoVinculado,\n"
    "  resolverCorridaLoteBuscaFornecedor,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import-constants-extra",
)

# 4. tipo DadosTecnicosFornecedorResultado
src = replace_once(
    src,
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  ItemCertificadoQualidadeComponente,\n"
    "  Produto,\n"
    "  ResumoRastreabilidadeCertificadoQualidade,\n"
    "} from '@/types';\n",
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  DadosTecnicosFornecedorResultado,\n"
    "  ItemCertificadoQualidade,\n"
    "  ItemCertificadoQualidadeComponente,\n"
    "  Produto,\n"
    "  ResumoRastreabilidadeCertificadoQualidade,\n"
    "} from '@/types';\n",
    "import-tipo-fornecedor",
)

# 5. states
src = replace_once(
    src,
    "  } | null>(null);\n"
    "\n"
    "  // Carrega CQ existente (ou reseta para novo)\n",
    "  } | null>(null);\n"
    "  const [fornecedorMatches, setFornecedorMatches] = useState<\n"
    "    DadosTecnicosFornecedorResultado[]\n"
    "  >([]);\n"
    "  const [fornecedorTargetIdx, setFornecedorTargetIdx] = useState<number | null>(null);\n"
    "  const [fornecedorMatchModalOpen, setFornecedorMatchModalOpen] = useState(false);\n"
    "  const [fornecedorBuscaItemLoading, setFornecedorBuscaItemLoading] = useState<number | null>(\n"
    "    null,\n"
    "  );\n"
    "  const [fornecedorBuscaItemMsg, setFornecedorBuscaItemMsg] = useState<\n"
    "    Record<number, { type: 'error' | 'info'; text: string }>\n"
    "  >({});\n"
    "\n"
    "  // Carrega CQ existente (ou reseta para novo)\n",
    "states-fornecedor",
)

# 6. handlers (apos aplicarCorridasCfSelecionadas)
src = replace_once(
    src,
    "        dados.mensagem_origem_fisica || '',\n"
    "      ].filter(Boolean),\n"
    "    );\n"
    "    return true;\n"
    "  };\n",
    "        dados.mensagem_origem_fisica || '',\n"
    "      ].filter(Boolean),\n"
    "    );\n"
    "    return true;\n"
    "  };\n"
    "\n"
    "  const patchFornecedorBuscaItemMsg = (\n"
    "    idx: number,\n"
    "    v: { type: 'error' | 'info'; text: string } | null,\n"
    "  ) =>\n"
    "    setFornecedorBuscaItemMsg((prev) => {\n"
    "      const next = { ...prev };\n"
    "      if (v == null) delete next[idx];\n"
    "      else next[idx] = v;\n"
    "      return next;\n"
    "    });\n"
    "\n"
    "  const componentePreenchido = (comp: ReturnType<typeof ensureComp>) =>\n"
    "    Boolean(\n"
    "      (comp.nome_componente || '').trim() ||\n"
    "        (comp.corrida || '').trim() ||\n"
    "        (comp.norma || '').trim() ||\n"
    "        Object.values(ensureMap(comp.composicao_json)).some(Boolean) ||\n"
    "        Object.values(ensureMap(comp.ensaio_tracao_json)).some(Boolean),\n"
    "    );\n"
    "\n"
    "  const aplicarDadosFornecedor = (idx: number, srcData: DadosTecnicosFornecedorResultado) => {\n"
    "    if (srcData.status_certificado_fornecedor === 'rascunho') {\n"
    "      const ok = window.confirm(\n"
    "        'O certificado fornecedor encontrado ainda esta em rascunho. Registre o certificado antes de usar os dados tecnicos. Deseja aplicar mesmo assim?',\n"
    "      );\n"
    "      if (!ok) return;\n"
    "    }\n"
    "    if (fornecedorResultadoSemProdutoVinculado(srcData)) {\n"
    "      const ok = window.confirm(\n"
    "        'Este dado tecnico veio de um certificado fornecedor cujo item nao esta vinculado a produto cadastrado. Confira codigo, descricao e corrida antes de aplicar. Deseja continuar?',\n"
    "      );\n"
    "      if (!ok) return;\n"
    "    }\n"
    "    const item = form.itens[idx];\n"
    "    const isValvula =\n"
    "      (srcData.tipo_dados_tecnicos || item.tipo_dados_tecnicos) === 'VALVULA_COMPONENTES';\n"
    "    const { corrida: crEf, lote: loEf } = corridaLoteEfetivosResultadoFornecedor(srcData);\n"
    "    const novosComponentes = (srcData.componentes || []).map((cp, i) => ({\n"
    "      ...ensureComp(cp, i + 1),\n"
    "      numero_certificado_fornecedor_componente_snapshot:\n"
    "        String(cp.numero_certificado_fornecedor_componente || '') ||\n"
    "        (srcData.numero_certificado_fornecedor_item ||\n"
    "          srcData.numero_certificado_fornecedor ||\n"
    "          ''),\n"
    "    }));\n"
    "    if (isValvula) {\n"
    "      const existentes = (item.componentes || []).map((c, i) => ensureComp(c, i + 1));\n"
    "      const existePreenchido = existentes.some(componentePreenchido);\n"
    "      if (existePreenchido && novosComponentes.length) {\n"
    "        const ok = window.confirm(\n"
    "          'Este item ja possui componentes preenchidos. Deseja substituir pelos dados do certificado fornecedor?',\n"
    "        );\n"
    "        if (!ok) return;\n"
    "      }\n"
    "      updateItem(idx, {\n"
    "        tipo_dados_tecnicos: 'VALVULA_COMPONENTES',\n"
    "        corrida: crEf || item.corrida,\n"
    "        lote: loEf || item.lote,\n"
    "        componentes: novosComponentes,\n"
    "        certificado_fornecedor_origem_id: srcData.certificado_fornecedor_id || null,\n"
    "        item_certificado_fornecedor_origem_id: srcData.id || null,\n"
    "        fornecedor_nome_snapshot: srcData.fornecedor_nome || '',\n"
    "        nf_entrada_snapshot: srcData.numero_nf_entrada || '',\n"
    "        codigo_item_fornecedor_snapshot: srcData.codigo_produto || '',\n"
    "        descricao_item_fornecedor_snapshot: srcData.descricao_material || '',\n"
    "        numero_certificado_fornecedor_item_snapshot:\n"
    "          srcData.numero_certificado_fornecedor_item ||\n"
    "          srcData.numero_certificado_fornecedor ||\n"
    "          '',\n"
    "        corrida_snapshot: crEf || item.corrida_snapshot || '',\n"
    "        lote_snapshot: loEf || item.lote_snapshot || '',\n"
    "        origem_rastreabilidade_tipo: 'certificado_fornecedor',\n"
    "        origem_status_tecnico: srcData.status_certificado_fornecedor || '',\n"
    "      });\n"
    "    } else {\n"
    "      updateItem(idx, {\n"
    "        norma: srcData.norma || item.norma,\n"
    "        corrida: crEf || item.corrida,\n"
    "        lote: loEf || item.lote || '',\n"
    "        composicao_json: ensureMap(srcData.composicao_json),\n"
    "        ensaio_tracao_json: ensureMap(srcData.ensaio_tracao_json),\n"
    "        ensaio_impacto_json: ensureMap(srcData.ensaio_impacto_json),\n"
    "        tipo_dados_tecnicos: srcData.tipo_dados_tecnicos || item.tipo_dados_tecnicos,\n"
    "        certificado_fornecedor_origem_id: srcData.certificado_fornecedor_id || null,\n"
    "        item_certificado_fornecedor_origem_id: srcData.id || null,\n"
    "        fornecedor_nome_snapshot: srcData.fornecedor_nome || '',\n"
    "        nf_entrada_snapshot: srcData.numero_nf_entrada || '',\n"
    "        codigo_item_fornecedor_snapshot: srcData.codigo_produto || '',\n"
    "        descricao_item_fornecedor_snapshot: srcData.descricao_material || '',\n"
    "        numero_certificado_fornecedor_item_snapshot:\n"
    "          srcData.numero_certificado_fornecedor_item ||\n"
    "          srcData.numero_certificado_fornecedor ||\n"
    "          '',\n"
    "        corrida_snapshot: crEf || item.corrida_snapshot || '',\n"
    "        lote_snapshot: loEf || item.lote_snapshot || '',\n"
    "        origem_rastreabilidade_tipo: 'certificado_fornecedor',\n"
    "        origem_status_tecnico: srcData.status_certificado_fornecedor || '',\n"
    "      });\n"
    "    }\n"
    "    const avisos: string[] = [];\n"
    "    if (srcData.aviso_divergencia_codigo) avisos.push(srcData.aviso_divergencia_codigo);\n"
    "    if (fornecedorResultadoSemProdutoVinculado(srcData)) {\n"
    "      avisos.push(\n"
    "        'Dados encontrados em certificado fornecedor sem produto vinculado. Confira codigo, descricao e corrida antes de aplicar.',\n"
    "      );\n"
    "    } else {\n"
    "      avisos.push('Dados tecnicos encontrados no certificado fornecedor.');\n"
    "    }\n"
    "    if (srcData.status_certificado_fornecedor === 'rascunho') {\n"
    "      avisos.push(\n"
    "        'O certificado fornecedor encontrado ainda esta em rascunho. Registre o certificado antes de usar os dados tecnicos.',\n"
    "      );\n"
    "    }\n"
    "    if (\n"
    "      srcData.aviso_sem_vinculo_produto &&\n"
    "      !fornecedorResultadoSemProdutoVinculado(srcData)\n"
    "    ) {\n"
    "      avisos.push(srcData.aviso_sem_vinculo_produto);\n"
    "    }\n"
    "    adicionarMensagensUnicas(avisos);\n"
    "    patchFornecedorBuscaItemMsg(idx, null);\n"
    "  };\n"
    "\n"
    "  const buscarDadosFornecedor = async (idx: number) => {\n"
    "    patchFornecedorBuscaItemMsg(idx, null);\n"
    "    const item = form.itens[idx];\n"
    "    if (!item) return;\n"
    "    const produtoId = coerceProdutoItemId(item.produto);\n"
    "    const isValvula =\n"
    "      (item.tipo_dados_tecnicos || 'PADRAO_ITEM') === 'VALVULA_COMPONENTES';\n"
    "    const { corrida: corridaBusca, lote: loteBusca } = resolverCorridaLoteBuscaFornecedor(item);\n"
    "    if (!corridaBusca && !loteBusca) {\n"
    "      patchFornecedorBuscaItemMsg(idx, {\n"
    "        type: 'error',\n"
    "        text: 'Informe a corrida ou o lote antes de buscar dados do certificado fornecedor.',\n"
    "      });\n"
    "      return;\n"
    "    }\n"
    "    setFornecedorBuscaItemLoading(idx);\n"
    "    try {\n"
    "      const { resultados: encontrados, dicas_busca: dicasBusca } =\n"
    "        await certificadosFornecedorService.buscarDadosTecnicos({\n"
    "          ...(produtoId ? { produto: produtoId } : {}),\n"
    "          corrida: corridaBusca || undefined,\n"
    "          lote: loteBusca || undefined,\n"
    "          codigo_produto: item.codigo_produto || undefined,\n"
    "          descricao: item.descricao_material || undefined,\n"
    "          tipo_dados_tecnicos: isValvula ? 'VALVULA_COMPONENTES' : 'PADRAO_ITEM',\n"
    "          norma: item.norma || undefined,\n"
    "          status: 'registrado',\n"
    "        });\n"
    "      if (!encontrados.length) {\n"
    "        const dicaMsg = mensagemPrincipalBuscaDadosTecnicosFornecedor(dicasBusca);\n"
    "        const text =\n"
    "          dicaMsg ||\n"
    "          'Nenhum certificado fornecedor registrado foi encontrado para esta corrida.';\n"
    "        patchFornecedorBuscaItemMsg(idx, { type: 'error', text });\n"
    "        return;\n"
    "      }\n"
    "      if (encontrados.length === 1) {\n"
    "        aplicarDadosFornecedor(idx, encontrados[0]);\n"
    "        return;\n"
    "      }\n"
    "      patchFornecedorBuscaItemMsg(idx, null);\n"
    "      setFornecedorTargetIdx(idx);\n"
    "      setFornecedorMatches(encontrados);\n"
    "      setFornecedorMatchModalOpen(true);\n"
    "    } catch (e) {\n"
    "      patchFornecedorBuscaItemMsg(idx, {\n"
    "        type: 'error',\n"
    "        text: apiErrorMessage(e, {\n"
    "          fallback: 'Falha ao buscar dados tecnicos de entrada.',\n"
    "        }),\n"
    "      });\n"
    "    } finally {\n"
    "      setFornecedorBuscaItemLoading(null);\n"
    "    }\n"
    "  };\n",
    "handlers-fornecedor",
)

# 7. props no ItemEditor
src = replace_once(
    src,
    "                    onAbrirModalCorridasCf: () => void abrirModalCorridasCf(idx),\n"
    "                  }}\n",
    "                    onAbrirModalCorridasCf: () => void abrirModalCorridasCf(idx),\n"
    "                    onBuscarDadosFornecedor: () => void buscarDadosFornecedor(idx),\n"
    "                    fornecedorBuscaLoading: fornecedorBuscaItemLoading === idx,\n"
    "                    fornecedorBuscaMsg: fornecedorBuscaItemMsg[idx],\n"
    "                  }}\n",
    "props-fornecedor-item",
)

# 8. modal de resultados antes do fechamento final
src = replace_once(
    src,
    "        onAplicar={aplicarCorridasCfSelecionadas}\n"
    "      />\n"
    "    </div>\n"
    "  );\n"
    "}\n",
    "        onAplicar={aplicarCorridasCfSelecionadas}\n"
    "      />\n"
    "\n"
    "      <Modal\n"
    "        isOpen={fornecedorMatchModalOpen}\n"
    "        onClose={() => setFornecedorMatchModalOpen(false)}\n"
    "        title=\"Resultados de certificado de fornecedor\"\n"
    "        size=\"xl\"\n"
    "      >\n"
    "        <div className=\"space-y-2 max-h-[55vh] overflow-auto pr-1\">\n"
    "          {fornecedorMatches.map((r) => (\n"
    "            <div\n"
    "              key={`${r.certificado_fornecedor_id}-${r.id}`}\n"
    "              className=\"rounded border border-border p-3\"\n"
    "            >\n"
    "              <div className=\"flex flex-wrap items-center gap-2 mb-2\">\n"
    "                {r.produto_match_tipo === 'sem_vinculo' ? (\n"
    "                  <span className=\"erp-badge-warning text-xs\">\n"
    "                    Item CF sem produto vinculado\n"
    "                  </span>\n"
    "                ) : null}\n"
    "                {r.produto_match_tipo === 'vinculado' ? (\n"
    "                  <span className=\"erp-badge-success text-xs\">\n"
    "                    Produto CF = produto CQ\n"
    "                  </span>\n"
    "                ) : null}\n"
    "              </div>\n"
    "              <div className=\"grid grid-cols-1 md:grid-cols-2 gap-1 text-sm\">\n"
    "                <p><span className=\"font-medium\">Fornecedor:</span> {r.fornecedor_nome || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">NF entrada:</span> {r.numero_nf_entrada || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Certificado:</span> {r.numero_certificado_fornecedor || `#${r.certificado_fornecedor_id}`}</p>\n"
    "                <p><span className=\"font-medium\">Status (fornecedor):</span> {r.status_certificado_fornecedor || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Codigo item fornecedor:</span> {r.codigo_produto || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Descricao:</span> {r.descricao_material || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Corrida:</span> {r.corrida || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Lote:</span> {r.lote || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Norma:</span> {r.norma || '\\u2014'}</p>\n"
    "                <p><span className=\"font-medium\">Tipo tecnico:</span> {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? 'Valvula por componentes' : 'Dados por item'}</p>\n"
    "                {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? (\n"
    "                  <p className=\"md:col-span-2\">\n"
    "                    <span className=\"font-medium\">Componentes:</span> {(r.componentes || []).length}\n"
    "                    {(r.componentes || []).length\n"
    "                      ? ` (${(r.componentes || []).slice(0, 6).map((c) => c.nome_componente || 'Componente').join(', ')})`\n"
    "                      : ''}\n"
    "                  </p>\n"
    "                ) : null}\n"
    "              </div>\n"
    "              {r.aviso_sem_vinculo_produto ? (\n"
    "                <p className=\"text-xs text-amber-800 dark:text-amber-200 mt-2\">{r.aviso_sem_vinculo_produto}</p>\n"
    "              ) : null}\n"
    "              {r.aviso_divergencia_codigo ? (\n"
    "                <p className=\"text-xs text-amber-700 dark:text-amber-300 mt-2\">{r.aviso_divergencia_codigo}</p>\n"
    "              ) : null}\n"
    "              <div className=\"flex justify-end mt-2\">\n"
    "                <button\n"
    "                  type=\"button\"\n"
    "                  className=\"erp-btn-primary erp-btn-sm w-full sm:w-auto\"\n"
    "                  onClick={() => {\n"
    "                    if (fornecedorTargetIdx == null) return;\n"
    "                    aplicarDadosFornecedor(fornecedorTargetIdx, r);\n"
    "                    setFornecedorMatchModalOpen(false);\n"
    "                  }}\n"
    "                >\n"
    "                  {r.tipo_dados_tecnicos === 'VALVULA_COMPONENTES' ? 'Usar estes componentes' : 'Usar estes dados'}\n"
    "                </button>\n"
    "              </div>\n"
    "            </div>\n"
    "          ))}\n"
    "          {!fornecedorMatches.length ? (\n"
    "            <p className=\"text-sm text-muted-foreground\">Nenhum resultado.</p>\n"
    "          ) : null}\n"
    "        </div>\n"
    "      </Modal>\n"
    "    </div>\n"
    "  );\n"
    "}\n",
    "render-modal-fornecedor",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
