#!/usr/bin/env python3
"""Etapa 3c-2 — prontidao tecnica + origem documental + aviso no Workspace."""
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

# 1. useMemo no import do React
src = replace_once(
    src,
    "import { useCallback, useEffect, useState } from 'react';\n",
    "import { useCallback, useEffect, useMemo, useState } from 'react';\n",
    "import-useMemo",
)

# 2. imports de helpers
src = replace_once(
    src,
    "import { coerceProdutoItemId } from '@/lib/certificadoQualidadeConstants';\n",
    "import { coerceProdutoItemId } from '@/lib/certificadoQualidadeConstants';\n"
    "import {\n"
    "  origemFisicaCqBadge,\n"
    "  origemFisicaCqDescricao,\n"
    "  origemFisicaCqResumo,\n"
    "} from '@/lib/certificadoStatusUi';\n",
    "import-helpers",
)

# 3. tipo ResumoRastreabilidade
src = replace_once(
    src,
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  ItemCertificadoQualidadeComponente,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  ItemCertificadoQualidadeComponente,\n"
    "  Produto,\n"
    "  ResumoRastreabilidadeCertificadoQualidade,\n"
    "} from '@/types';\n",
    "import-tipo-resumo",
)

# 4. useMemos (depois dos contadores)
src = replace_once(
    src,
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n",
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n"
    "\n"
    "  const resumoRastreabilidade = useMemo(\n"
    "    (): ResumoRastreabilidadeCertificadoQualidade | null => {\n"
    "      if (form.resumo_rastreabilidade) return form.resumo_rastreabilidade;\n"
    "      const incl = form.itens.filter((it) => it.incluir_no_certificado !== false);\n"
    "      if (!incl.some((it) => it.rastreabilidade_status)) return null;\n"
    "      let completos = 0;\n"
    "      let parciais = 0;\n"
    "      let pendentes = 0;\n"
    "      incl.forEach((it) => {\n"
    "        if (it.rastreabilidade_status === 'COMPLETA') completos += 1;\n"
    "        else if (it.rastreabilidade_status === 'PARCIAL') parciais += 1;\n"
    "        else pendentes += 1;\n"
    "      });\n"
    "      return {\n"
    "        completos,\n"
    "        parciais,\n"
    "        pendentes,\n"
    "        pode_emitir: incl.length > 0 && parciais === 0 && pendentes === 0,\n"
    "      };\n"
    "    },\n"
    "    [form.resumo_rastreabilidade, form.itens],\n"
    "  );\n"
    "\n"
    "  const origemFisicaResumo = useMemo(\n"
    "    () => origemFisicaCqResumo(form.itens),\n"
    "    [form.itens],\n"
    "  );\n"
    "\n"
    "  const temAvisoRastreabilidadeFisica = useMemo(\n"
    "    () =>\n"
    "      form.itens.some(\n"
    "        (it) =>\n"
    "          it.incluir_no_certificado !== false &&\n"
    "          (it.rastreabilidade_motivos?.includes('SEM_CORRIDA_LOTE') ||\n"
    "            it.rastreabilidade_motivos?.includes('ESTOQUE_NAO_APLICADO') ||\n"
    "            it.rastreabilidade_motivos?.includes('SEM_CONFERENCIA_ORIGEM') ||\n"
    "            it.rastreabilidade_motivos?.includes('RASTREABILIDADE_FISICA_OPCIONAL') ||\n"
    "            it.rastreabilidade_avisos?.some((a) => a.includes('nao impede a emissao')) ||\n"
    "            (!it.tem_corrida_lote &&\n"
    "              !it.corrida &&\n"
    "              !it.lote &&\n"
    "              (it.rastreabilidade_status != null || form.itens.length > 0))),\n"
    "      ),\n"
    "    [form.itens],\n"
    "  );\n",
    "usememos",
)

# 5. bloco JSX no topo da aba Itens
src = replace_once(
    src,
    "        <TabsContent value=\"itens\" className=\"mt-0 space-y-4\">\n"
    "      <div className=\"rounded border border-border bg-muted/10 p-3\">\n"
    "        <p className=\"text-sm font-medium mb-2\">Itens do certificado</p>\n",
    "        <TabsContent value=\"itens\" className=\"mt-0 space-y-4\">\n"
    "          {form.status !== 'cancelado' ? (\n"
    "            <div className=\"rounded border border-border p-3 bg-muted/10\">\n"
    "              <p className=\"text-sm font-medium mb-2\">Prontid\u00e3o t\u00e9cnica</p>\n"
    "              {resumoRastreabilidade ? (\n"
    "                <div className=\"flex flex-wrap gap-2 text-xs mb-2\">\n"
    "                  <span className=\"erp-badge-success\">\n"
    "                    Completa: {resumoRastreabilidade.completos}\n"
    "                  </span>\n"
    "                  <span className=\"erp-badge-warning\">\n"
    "                    Parcial: {resumoRastreabilidade.parciais}\n"
    "                  </span>\n"
    "                  <span className=\"erp-badge-danger\">\n"
    "                    Pendente: {resumoRastreabilidade.pendentes}\n"
    "                  </span>\n"
    "                  {resumoRastreabilidade.pode_emitir ? (\n"
    "                    <span className=\"text-emerald-700 dark:text-emerald-400\">\n"
    "                      Pronto para emiss\u00e3o definitiva\n"
    "                    </span>\n"
    "                  ) : (\n"
    "                    <span className=\"text-amber-800 dark:text-amber-300\">\n"
    "                      Pend\u00eancias de produto/descri\u00e7\u00e3o ou dados t\u00e9cnicos ainda impedem a emiss\u00e3o definitiva.\n"
    "                    </span>\n"
    "                  )}\n"
    "                </div>\n"
    "              ) : (\n"
    "                <p className=\"text-xs text-muted-foreground mb-2\">\n"
    "                  Salve o certificado para calcular o resumo de rastreabilidade no servidor.\n"
    "                </p>\n"
    "              )}\n"
    "              <p className=\"text-[11px] text-muted-foreground mb-3\">\n"
    "                A prontid\u00e3o t\u00e9cnica indica apenas os dados exigidos para emiss\u00e3o do CQ; ela n\u00e3o comprova a origem f\u00edsica do material.\n"
    "              </p>\n"
    "              <p className=\"text-sm font-medium mb-2\">Origem documental</p>\n"
    "              <div className=\"flex flex-wrap items-center gap-2 text-xs mb-1\">\n"
    "                <span className={origemFisicaCqBadge(origemFisicaResumo).className}>\n"
    "                  {origemFisicaCqBadge(origemFisicaResumo).label}\n"
    "                </span>\n"
    "                <span className=\"text-muted-foreground\">\n"
    "                  {origemFisicaCqDescricao(origemFisicaResumo)}\n"
    "                </span>\n"
    "              </div>\n"
    "              <p className=\"text-[11px] text-muted-foreground mb-1\">\n"
    "                Este indicador confirma o v\u00ednculo documental com o Certificado de Fornecedor e os dados de corrida/lote registrados. Ele n\u00e3o comprova, nesta fase, a origem f\u00edsica da quantidade consumida no estoque ou na aloca\u00e7\u00e3o da venda.\n"
    "              </p>\n"
    "              {temAvisoRastreabilidadeFisica ? (\n"
    "                <p className=\"text-xs text-sky-800 dark:text-sky-300\">\n"
    "                  Rastreabilidade f\u00edsica n\u00e3o vinculada. Isso n\u00e3o impede a emiss\u00e3o do certificado.\n"
    "                </p>\n"
    "              ) : null}\n"
    "            </div>\n"
    "          ) : null}\n"
    "      <div className=\"rounded border border-border bg-muted/10 p-3\">\n"
    "        <p className=\"text-sm font-medium mb-2\">Itens do certificado</p>\n",
    "bloco-3c2",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
