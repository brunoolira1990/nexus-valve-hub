#!/usr/bin/env python3
"""Se item tem CF/item vinculados, puxa componentes via getById (sem exigir corrida)."""
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

OLD = (
    "  const buscarDadosFornecedor = async (idx: number) => {\n"
    "    patchFornecedorBuscaItemMsg(idx, null);\n"
    "    const item = form.itens[idx];\n"
    "    if (!item) return;\n"
    "    const produtoId = coerceProdutoItemId(item.produto);\n"
)
NEW = (
    "  const buscarDadosFornecedor = async (idx: number) => {\n"
    "    patchFornecedorBuscaItemMsg(idx, null);\n"
    "    const item = form.itens[idx];\n"
    "    if (!item) return;\n"
    "\n"
    "    // Se o item ja tem vinculo com CF/item exatos, puxa direto pelo getById\n"
    "    // (nao exige corrida — os componentes vem preenchidos pelo vinculo).\n"
    "    const cfIdVinculado = item.certificado_fornecedor_origem_id;\n"
    "    const itemCfIdVinculado = item.item_certificado_fornecedor_origem_id;\n"
    "    if (cfIdVinculado && itemCfIdVinculado) {\n"
    "      setFornecedorBuscaItemLoading(idx);\n"
    "      try {\n"
    "        const cf = await certificadosFornecedorService.getById(cfIdVinculado);\n"
    "        const itemCf = (cf.itens || []).find((it) => it.id === itemCfIdVinculado);\n"
    "        if (!itemCf) {\n"
    "          patchFornecedorBuscaItemMsg(idx, {\n"
    "            type: 'error',\n"
    "            text: 'Item vinculado nao foi encontrado no certificado fornecedor.',\n"
    "          });\n"
    "          return;\n"
    "        }\n"
    "        const resultado: DadosTecnicosFornecedorResultado = {\n"
    "          id: itemCf.id!,\n"
    "          certificado_fornecedor_id: cf.id,\n"
    "          fornecedor: cf.fornecedor ?? null,\n"
    "          fornecedor_nome: cf.fornecedor_nome_snapshot || '',\n"
    "          numero_nf_entrada: cf.numero_nf_entrada || '',\n"
    "          data_nf_entrada: cf.data_nf_entrada ?? undefined,\n"
    "          numero_certificado_fornecedor: cf.numero_certificado_fornecedor || '',\n"
    "          numero_certificado_fornecedor_item:\n"
    "            itemCf.numero_certificado_fornecedor_item || '',\n"
    "          status_certificado_fornecedor: cf.status,\n"
    "          produto: itemCf.produto ?? null,\n"
    "          codigo_produto: itemCf.codigo_produto || '',\n"
    "          descricao_material: itemCf.descricao_material || '',\n"
    "          norma: itemCf.norma || '',\n"
    "          corrida: itemCf.corrida || '',\n"
    "          lote: itemCf.lote || '',\n"
    "          tipo_dados_tecnicos:\n"
    "            (itemCf.tipo_dados_tecnicos as\n"
    "              | 'PADRAO_ITEM'\n"
    "              | 'VALVULA_COMPONENTES') || 'PADRAO_ITEM',\n"
    "          composicao_json: (\n"
    "            itemCf as unknown as { composicao_json?: Record<string, unknown> }\n"
    "          ).composicao_json,\n"
    "          ensaio_tracao_json: (\n"
    "            itemCf as unknown as { ensaio_tracao_json?: Record<string, unknown> }\n"
    "          ).ensaio_tracao_json,\n"
    "          ensaio_impacto_json: (\n"
    "            itemCf as unknown as { ensaio_impacto_json?: Record<string, unknown> }\n"
    "          ).ensaio_impacto_json,\n"
    "          componentes: itemCf.componentes || [],\n"
    "        };\n"
    "        aplicarDadosFornecedor(idx, resultado);\n"
    "      } catch (e) {\n"
    "        patchFornecedorBuscaItemMsg(idx, {\n"
    "          type: 'error',\n"
    "          text: apiErrorMessage(e, {\n"
    "            fallback: 'Falha ao carregar dados do CF vinculado.',\n"
    "          }),\n"
    "        });\n"
    "      } finally {\n"
    "        setFornecedorBuscaItemLoading(null);\n"
    "      }\n"
    "      return;\n"
    "    }\n"
    "\n"
    "    const produtoId = coerceProdutoItemId(item.produto);\n"
)
src = replace_once(src, OLD, NEW, "branch-vinculo-direto")

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
