#!/usr/bin/env python3
"""Fix — origemFisicaCqItem considera componentes quando VALVULA_COMPONENTES."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/lib/certificadoStatusUi.ts")
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

# 1. estende ItemOrigemFisicaCq com tipo_dados_tecnicos + componentes
src = replace_once(
    src,
    "export interface ItemOrigemFisicaCq {\n"
    "  incluir_no_certificado?: boolean;\n"
    "  corrida?: string;\n"
    "  lote?: string;\n"
    "  corrida_snapshot?: string;\n"
    "  lote_snapshot?: string;\n"
    "  norma?: string;\n"
    "  certificado_fornecedor_origem_id?: number | null;\n"
    "  item_certificado_fornecedor_origem_id?: number | null;\n"
    "  tem_certificado_fornecedor?: boolean;\n"
    "  rastreabilidade_motivos?: string[];\n"
    "  rastreabilidade_avisos?: string[];\n"
    "}\n",
    "export interface ItemOrigemFisicaCqComponente {\n"
    "  nome_componente?: string;\n"
    "  corrida?: string;\n"
    "  lote?: string;\n"
    "  ativo?: boolean;\n"
    "}\n"
    "\n"
    "export interface ItemOrigemFisicaCq {\n"
    "  incluir_no_certificado?: boolean;\n"
    "  corrida?: string;\n"
    "  lote?: string;\n"
    "  corrida_snapshot?: string;\n"
    "  lote_snapshot?: string;\n"
    "  norma?: string;\n"
    "  tipo_dados_tecnicos?: string;\n"
    "  certificado_fornecedor_origem_id?: number | null;\n"
    "  item_certificado_fornecedor_origem_id?: number | null;\n"
    "  tem_certificado_fornecedor?: boolean;\n"
    "  rastreabilidade_motivos?: string[];\n"
    "  rastreabilidade_avisos?: string[];\n"
    "  componentes?: ItemOrigemFisicaCqComponente[];\n"
    "}\n",
    "tipo-extendido",
)

# 2. helpers puros (antes de origemFisicaCqItem) + nova versao do origemFisicaCqItem
OLD_FN = (
    "export function origemFisicaCqItem(item: ItemOrigemFisicaCq): OrigemFisicaCqStatus {\n"
    "  const origemDocumental = itemCqTemOrigemDocumental(item);\n"
    "  const marcadoManual = item.rastreabilidade_motivos?.includes('CF_NAO_VINCULADO_MANUAL') ?? false;\n"
    "  if (!origemDocumental || marcadoManual) {\n"
    "    const dadosDigitados = Boolean(\n"
    "      (item.corrida || '').trim() || (item.lote || '').trim() || (item.norma || '').trim(),\n"
    "    );\n"
    "    return dadosDigitados ? 'MANUAL' : 'NAO_CONFIRMADA';\n"
    "  }\n"
    "  const corridaLoteDaOrigem = Boolean(\n"
    "    (item.corrida_snapshot || '').trim() || (item.lote_snapshot || '').trim(),\n"
    "  );\n"
    "  if (!corridaLoteDaOrigem) return 'PARCIAL';\n"
    "  return (item.rastreabilidade_avisos?.length ?? 0) > 0 ? 'PARCIAL' : 'CONFIRMADA';\n"
    "}\n"
)
NEW_FN = (
    "/** Componentes ativos com nome — replica o filtro do backend (_componentes_ativos + nome). */\n"
    "function componentesValidosParaRastreabilidade(\n"
    "  item: ItemOrigemFisicaCq,\n"
    "): ItemOrigemFisicaCqComponente[] {\n"
    "  return (item.componentes || []).filter(\n"
    "    (c) => c.ativo !== false && (c.nome_componente || '').trim().length > 0,\n"
    "  );\n"
    "}\n"
    "\n"
    "/** Replica o criterio AND do backend: em valvula, TODOS os componentes ativos\n"
    " * nomeados precisam ter corrida OU lote para a origem documental ser completa. */\n"
    "function temCorridaOuLoteEmTodosComponentes(item: ItemOrigemFisicaCq): boolean {\n"
    "  const comps = componentesValidosParaRastreabilidade(item);\n"
    "  if (!comps.length) return false;\n"
    "  return comps.every(\n"
    "    (c) => (c.corrida || '').trim().length > 0 || (c.lote || '').trim().length > 0,\n"
    "  );\n"
    "}\n"
    "\n"
    "function algumComponenteComCorridaOuLote(item: ItemOrigemFisicaCq): boolean {\n"
    "  return componentesValidosParaRastreabilidade(item).some(\n"
    "    (c) => (c.corrida || '').trim().length > 0 || (c.lote || '').trim().length > 0,\n"
    "  );\n"
    "}\n"
    "\n"
    "export function origemFisicaCqItem(item: ItemOrigemFisicaCq): OrigemFisicaCqStatus {\n"
    "  const origemDocumental = itemCqTemOrigemDocumental(item);\n"
    "  const marcadoManual = item.rastreabilidade_motivos?.includes('CF_NAO_VINCULADO_MANUAL') ?? false;\n"
    "  const isValvula = item.tipo_dados_tecnicos === 'VALVULA_COMPONENTES';\n"
    "\n"
    "  if (!origemDocumental || marcadoManual) {\n"
    "    const dadosDigitados = isValvula\n"
    "      ? algumComponenteComCorridaOuLote(item)\n"
    "      : Boolean(\n"
    "          (item.corrida || '').trim() ||\n"
    "            (item.lote || '').trim() ||\n"
    "            (item.norma || '').trim(),\n"
    "        );\n"
    "    return dadosDigitados ? 'MANUAL' : 'NAO_CONFIRMADA';\n"
    "  }\n"
    "\n"
    "  if (isValvula) {\n"
    "    if (!temCorridaOuLoteEmTodosComponentes(item)) return 'PARCIAL';\n"
    "    return (item.rastreabilidade_avisos?.length ?? 0) > 0 ? 'PARCIAL' : 'CONFIRMADA';\n"
    "  }\n"
    "\n"
    "  const corridaLoteDaOrigem = Boolean(\n"
    "    (item.corrida_snapshot || '').trim() || (item.lote_snapshot || '').trim(),\n"
    "  );\n"
    "  if (!corridaLoteDaOrigem) return 'PARCIAL';\n"
    "  return (item.rastreabilidade_avisos?.length ?? 0) > 0 ? 'PARCIAL' : 'CONFIRMADA';\n"
    "}\n"
)
src = replace_once(src, OLD_FN, NEW_FN, "origemFisicaCqItem")

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".ts.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
