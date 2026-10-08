#!/usr/bin/env python3
"""Etapa 6 (B) — state + handlers + modal corridas CF no Workspace."""
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

# 1. AxiosError
src = replace_once(
    src,
    "import { useCallback, useEffect, useMemo, useState } from 'react';\n",
    "import { useCallback, useEffect, useMemo, useState } from 'react';\n"
    "import { AxiosError } from 'axios';\n",
    "import-axios",
)

# 2. ModalCorridasCertificadoFornecedor
src = replace_once(
    src,
    "import { ItemEditor, type LinhaDivisaoCorrida } from './ItemEditor';\n",
    "import { ItemEditor, type LinhaDivisaoCorrida } from './ItemEditor';\n"
    "import { ModalCorridasCertificadoFornecedor } from '@/components/qualidade/ModalCorridasCertificadoFornecedor';\n",
    "import-modal",
)

# 3. helpers de cqCorridasCfUi
src = replace_once(
    src,
    "import { baseItemIrmao } from '@/lib/cqCorridasCfUi';\n",
    "import {\n"
    "  aplicacaoSubstituiTecnicosDoItemAtual,\n"
    "  aplicarDistribuicaoCorridasCfCq,\n"
    "  baseItemIrmao,\n"
    "  quantidadeTotalDistribuicaoCorridasCfCq,\n"
    "  selecoesExistentesCorridasCfCq,\n"
    "  type CorridasCfParaCqResponse,\n"
    "  type SelecaoCorridaCfCq,\n"
    "} from '@/lib/cqCorridasCfUi';\n",
    "import-cq-corridas",
)

# 4. getApiErrorStatus
src = replace_once(
    src,
    "import { apiErrorMessage } from '@/services/api/config';\n",
    "import { apiErrorMessage, getApiErrorStatus } from '@/services/api/config';\n",
    "import-get-status",
)

# 5. state corridasCfModal
src = replace_once(
    src,
    "  const [dividindoCorridas, setDividindoCorridas] = useState<\n"
    "    Record<number, LinhaDivisaoCorrida[]>\n"
    "  >({});\n",
    "  const [dividindoCorridas, setDividindoCorridas] = useState<\n"
    "    Record<number, LinhaDivisaoCorrida[]>\n"
    "  >({});\n"
    "  const [corridasCfModal, setCorridasCfModal] = useState<{\n"
    "    itemIdx: number;\n"
    "    dados: CorridasCfParaCqResponse | null;\n"
    "    carregando: boolean;\n"
    "    erro: string | null;\n"
    "    quantidadeTotal: number;\n"
    "    selecoesIniciais: SelecaoCorridaCfCq[];\n"
    "  } | null>(null);\n",
    "state-corridas-cf-modal",
)

# 6. handlers depois de adicionarComponentesPadrao
src = replace_once(
    src,
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
    "  const adicionarComponentesPadrao = (idx: number) =>\n"
    "    setForm((p) => {\n"
    "      const next = [...p.itens];\n"
    "      const comps = [...(next[idx].componentes || [])];\n"
    "      COMPONENTES_PADRAO.forEach((nome) => {\n"
    "        comps.push(ensureComp({ nome_componente: nome }, comps.length + 1));\n"
    "      });\n"
    "      next[idx] = { ...next[idx], componentes: comps };\n"
    "      return { ...p, itens: next };\n"
    "    });\n"
    "\n"
    "  const abrirModalCorridasCf = async (idx: number) => {\n"
    "    const item = form.itens[idx];\n"
    "    const cfId = item.certificado_fornecedor_origem_id;\n"
    "    const itemCfId = item.item_certificado_fornecedor_origem_id;\n"
    "    if (!cfId || !itemCfId) {\n"
    "      setSaveError(\n"
    "        'Vincule este item a um Certificado de Fornecedor e ao item exato do CF (via corrida disponivel ou busca de dados do fornecedor) antes de adicionar corridas.',\n"
    "      );\n"
    "      return;\n"
    "    }\n"
    "    setSaveError(null);\n"
    "    setCorridasCfModal({\n"
    "      itemIdx: idx,\n"
    "      dados: null,\n"
    "      carregando: true,\n"
    "      erro: null,\n"
    "      quantidadeTotal: Number(item.quantidade) || 0,\n"
    "      selecoesIniciais: [],\n"
    "    });\n"
    "    try {\n"
    "      const dados = await certificadosQualidadeService.corridasCertificadoFornecedor(cfId, itemCfId);\n"
    "      const itensAtuais = form.itens;\n"
    "      setCorridasCfModal({\n"
    "        itemIdx: idx,\n"
    "        dados,\n"
    "        carregando: false,\n"
    "        erro: null,\n"
    "        quantidadeTotal: quantidadeTotalDistribuicaoCorridasCfCq(\n"
    "          dados.linhas,\n"
    "          itensAtuais,\n"
    "          itensAtuais[idx],\n"
    "        ),\n"
    "        selecoesIniciais: selecoesExistentesCorridasCfCq(dados.linhas, itensAtuais),\n"
    "      });\n"
    "    } catch (e) {\n"
    "      const status = getApiErrorStatus(e);\n"
    "      const detail = (e as AxiosError<{ detail?: string }>)?.response?.data?.detail;\n"
    "      const erro =\n"
    "        status === 401 || status === 403\n"
    "          ? apiErrorMessage(e, {\n"
    "              fallback:\n"
    "                'Nao foi possivel carregar as corridas do Certificado de Fornecedor.',\n"
    "            })\n"
    "          : typeof detail === 'string' && detail.trim()\n"
    "            ? detail.trim()\n"
    "            : apiErrorMessage(e, {\n"
    "                fallback:\n"
    "                  'Nao foi possivel carregar as corridas do Certificado de Fornecedor.',\n"
    "              });\n"
    "      setCorridasCfModal({\n"
    "        itemIdx: idx,\n"
    "        dados: null,\n"
    "        carregando: false,\n"
    "        erro,\n"
    "        quantidadeTotal: Number(item.quantidade) || 0,\n"
    "        selecoesIniciais: [],\n"
    "      });\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const aplicarCorridasCfSelecionadas = (selecoes: SelecaoCorridaCfCq[]) => {\n"
    "    const idx = corridasCfModal?.itemIdx;\n"
    "    const dados = corridasCfModal?.dados;\n"
    "    if (idx == null || !dados) return false;\n"
    "    const itemOriginal = form.itens[idx];\n"
    "    if (\n"
    "      aplicacaoSubstituiTecnicosDoItemAtual(itemOriginal, selecoes) &&\n"
    "      !window.confirm(\n"
    "        'O item atual ja possui dados tecnicos preenchidos. Aplicar esta distribuicao substituira os dados tecnicos da primeira origem selecionada. Deseja continuar?',\n"
    "      )\n"
    "    ) {\n"
    "      return false;\n"
    "    }\n"
    "    setForm((p) => {\n"
    "      const itens = aplicarDistribuicaoCorridasCfCq(p.itens, idx, dados.linhas, selecoes);\n"
    "      return { ...p, itens };\n"
    "    });\n"
    "    setCorridasCfModal(null);\n"
    "    adicionarMensagensUnicas(\n"
    "      [\n"
    "        `Corridas aplicadas do Certificado de Fornecedor: ${selecoes\n"
    "          .map(\n"
    "            (s) =>\n"
    "              `${s.linha.corrida}${s.linha.lote ? `/${s.linha.lote}` : ''} (${s.quantidade})`,\n"
    "          )\n"
    "          .join(', ')}.`,\n"
    "        dados.mensagem_origem_fisica || '',\n"
    "      ].filter(Boolean),\n"
    "    );\n"
    "    return true;\n"
    "  };\n",
    "handlers-modal-cf",
)

# 7. props no ItemEditor
src = replace_once(
    src,
    "                    onAplicarDistribuicao: () => aplicarDistribuicaoCorridas(idx),\n"
    "                  }}\n",
    "                    onAplicarDistribuicao: () => aplicarDistribuicaoCorridas(idx),\n"
    "                    onAbrirModalCorridasCf: () => void abrirModalCorridasCf(idx),\n"
    "                  }}\n",
    "prop-modal-cf",
)

# 8. render do modal no fim do space-y-4
src = replace_once(
    src,
    "          {saving ? 'Salvando...' : 'Salvar'}\n"
    "        </button>\n"
    "      </div>\n"
    "    </div>\n"
    "  );\n"
    "}\n",
    "          {saving ? 'Salvando...' : 'Salvar'}\n"
    "        </button>\n"
    "      </div>\n"
    "\n"
    "      <ModalCorridasCertificadoFornecedor\n"
    "        isOpen={corridasCfModal != null}\n"
    "        onClose={() => setCorridasCfModal(null)}\n"
    "        dados={corridasCfModal?.dados ?? null}\n"
    "        carregando={corridasCfModal?.carregando ?? false}\n"
    "        erroCarregamento={corridasCfModal?.erro ?? null}\n"
    "        quantidadeTotalItem={corridasCfModal?.quantidadeTotal ?? 0}\n"
    "        selecoesIniciais={corridasCfModal?.selecoesIniciais ?? []}\n"
    "        contextoChave={\n"
    "          corridasCfModal\n"
    "            ? [\n"
    "                corridasCfModal.itemIdx,\n"
    "                form.itens[corridasCfModal.itemIdx]?.certificado_fornecedor_origem_id ?? '',\n"
    "                form.itens[corridasCfModal.itemIdx]?.item_certificado_fornecedor_origem_id ?? '',\n"
    "                form.itens[corridasCfModal.itemIdx]?.produto ?? '',\n"
    "              ].join(':')\n"
    "            : ''\n"
    "        }\n"
    "        onAplicar={aplicarCorridasCfSelecionadas}\n"
    "      />\n"
    "    </div>\n"
    "  );\n"
    "}\n",
    "render-modal",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
