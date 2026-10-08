#!/usr/bin/env python3
"""Rodada 3 (B) — handler puxarComponentesDoCfVinculado + props."""
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

# 1. state puxandoComponentes
src = replace_once(
    src,
    "  const [fornecedorBuscaCompMsg, setFornecedorBuscaCompMsg] = useState<\n"
    "    Record<string, { type: 'error' | 'info'; text: string }>\n"
    "  >({});\n",
    "  const [fornecedorBuscaCompMsg, setFornecedorBuscaCompMsg] = useState<\n"
    "    Record<string, { type: 'error' | 'info'; text: string }>\n"
    "  >({});\n"
    "  const [puxandoComponentes, setPuxandoComponentes] = useState<number | null>(null);\n",
    "state-puxando",
)

# 2. handler puxarComponentesDoCfVinculado (antes de buscarDadosFornecedor)
src = replace_once(
    src,
    "  const buscarDadosFornecedor = async (idx: number) => {\n",
    "  const puxarComponentesDoCfVinculado = async (idx: number) => {\n"
    "    const item = form.itens[idx];\n"
    "    const cfId = item.certificado_fornecedor_origem_id;\n"
    "    const itemCfId = item.item_certificado_fornecedor_origem_id;\n"
    "    if (!cfId || !itemCfId) {\n"
    "      adicionarMensagensUnicas([\n"
    "        'Vincule o item a um CF antes de puxar componentes.',\n"
    "      ]);\n"
    "      return;\n"
    "    }\n"
    "    setPuxandoComponentes(idx);\n"
    "    try {\n"
    "      const cf = await certificadosFornecedorService.getById(cfId);\n"
    "      const itemCf = (cf.itens || []).find((it) => it.id === itemCfId);\n"
    "      if (!itemCf) {\n"
    "        adicionarMensagensUnicas([\n"
    "          'Item vinculado nao foi encontrado no certificado fornecedor.',\n"
    "        ]);\n"
    "        return;\n"
    "      }\n"
    "      const componentesCf = itemCf.componentes || [];\n"
    "      if (!componentesCf.length) {\n"
    "        adicionarMensagensUnicas([\n"
    "          'O CF vinculado nao possui componentes cadastrados para este item.',\n"
    "        ]);\n"
    "        return;\n"
    "      }\n"
    "      const existentes = (item.componentes || []).map((c, i) => ensureComp(c, i + 1));\n"
    "      const existePreenchido = existentes.some((c) =>\n"
    "        Boolean(\n"
    "          (c.nome_componente || '').trim() ||\n"
    "            (c.corrida || '').trim() ||\n"
    "            Object.values(ensureMap(c.composicao_json)).some(Boolean),\n"
    "        ),\n"
    "      );\n"
    "      if (existePreenchido) {\n"
    "        const ok = window.confirm(\n"
    "          'Este item ja possui componentes preenchidos. Deseja substituir pelos componentes do CF vinculado?',\n"
    "        );\n"
    "        if (!ok) return;\n"
    "      }\n"
    "      const novosComponentes = componentesCf.map((cp, i) => ({\n"
    "        ...ensureComp(cp, i + 1),\n"
    "        numero_certificado_fornecedor_componente_snapshot:\n"
    "          String(cp.numero_certificado_fornecedor_componente || '') ||\n"
    "          itemCf.numero_certificado_fornecedor_item ||\n"
    "          cf.numero_certificado_fornecedor ||\n"
    "          '',\n"
    "      }));\n"
    "      updateItem(idx, {\n"
    "        componentes: novosComponentes,\n"
    "        fornecedor_nome_snapshot: item.fornecedor_nome_snapshot || cf.fornecedor_nome_snapshot || '',\n"
    "      });\n"
    "      adicionarMensagensUnicas([\n"
    "        `${novosComponentes.length} componente(s) puxado(s) do CF vinculado.`,\n"
    "      ]);\n"
    "    } catch (e) {\n"
    "      adicionarMensagensUnicas([\n"
    "        apiErrorMessage(e, { fallback: 'Falha ao puxar componentes do CF.' }),\n"
    "      ]);\n"
    "    } finally {\n"
    "      setPuxandoComponentes(null);\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const buscarDadosFornecedor = async (idx: number) => {\n",
    "handler-puxar",
)

# 3. props: troca onAddPadrao por onPuxarComponentesDoCfVinculado
src = replace_once(
    src,
    "                    onAdd: (nome?: string) => addComponente(idx, nome),\n"
    "                    onAddPadrao: () => adicionarComponentesPadrao(idx),\n",
    "                    onAdd: (nome?: string) => addComponente(idx, nome),\n"
    "                    onPuxarComponentesDoCfVinculado: () =>\n"
    "                      void puxarComponentesDoCfVinculado(idx),\n"
    "                    puxandoComponentes: puxandoComponentes === idx,\n",
    "props-r3",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
