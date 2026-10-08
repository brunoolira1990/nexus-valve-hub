#!/usr/bin/env python3
"""Etapa 7 — botoes de PDF (previa + download) no Workspace."""
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

# 1. import FileText
src = replace_once(
    src,
    "import { AxiosError } from 'axios';\n",
    "import { AxiosError } from 'axios';\n"
    "import { FileText } from 'lucide-react';\n",
    "import-filetext",
)

# 2. import PdfFilenameInput
src = replace_once(
    src,
    "import {\n"
    "  certificadosQualidadeService,\n"
    "  type NfeElegivelCqOpcao,\n"
    "} from '@/services/api/qualidade';\n",
    "import {\n"
    "  certificadosQualidadeService,\n"
    "  type NfeElegivelCqOpcao,\n"
    "  type PdfFilenameInput,\n"
    "} from '@/services/api/qualidade';\n",
    "import-pdf-input",
)

# 3. states pdf
src = replace_once(
    src,
    "  const [puxandoComponentes, setPuxandoComponentes] = useState<number | null>(null);\n",
    "  const [puxandoComponentes, setPuxandoComponentes] = useState<number | null>(null);\n"
    "  const [pdfBusy, setPdfBusy] = useState<'preview' | 'download' | null>(null);\n"
    "  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);\n"
    "  const [previewPdfTitulo, setPreviewPdfTitulo] = useState('Previa PDF');\n",
    "states-pdf",
)

# 4. handlers antes do return
src = replace_once(
    src,
    "  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');\n",
    "  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');\n"
    "\n"
    "  const pdfMeta = (): PdfFilenameInput => ({\n"
    "    numero: editing?.numero_formatado || editing?.numero || form.numero,\n"
    "    cliente: form.cliente_nome_snapshot,\n"
    "    nf: form.nota_fiscal_numero,\n"
    "  });\n"
    "\n"
    "  const baixarPdf = async () => {\n"
    "    if (!editing?.id) return;\n"
    "    setPdfBusy('download');\n"
    "    setSaveError(null);\n"
    "    try {\n"
    "      const preview = editing.status === 'rascunho';\n"
    "      await certificadosQualidadeService.baixarPdf(editing.id, preview, pdfMeta());\n"
    "    } catch (e) {\n"
    "      setSaveError(\n"
    "        apiErrorMessage(e, { fallback: 'Nao foi possivel gerar o PDF.' }),\n"
    "      );\n"
    "    } finally {\n"
    "      setPdfBusy(null);\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const abrirPreviaPdf = async () => {\n"
    "    if (!editing?.id) return;\n"
    "    setPdfBusy('preview');\n"
    "    setSaveError(null);\n"
    "    try {\n"
    "      const blob = await certificadosQualidadeService.obterPdfBlob(editing.id, true);\n"
    "      const url = URL.createObjectURL(blob);\n"
    "      setPreviewPdfUrl((old) => {\n"
    "        if (old) URL.revokeObjectURL(old);\n"
    "        return url;\n"
    "      });\n"
    "      setPreviewPdfTitulo(\n"
    "        `Previa PDF \\u2014 ${editing.numero_formatado || editing.numero || 'CQ'}`,\n"
    "      );\n"
    "    } catch (e) {\n"
    "      setSaveError(\n"
    "        apiErrorMessage(e, { fallback: 'Nao foi possivel gerar a previa do PDF.' }),\n"
    "      );\n"
    "    } finally {\n"
    "      setPdfBusy(null);\n"
    "    }\n"
    "  };\n",
    "handlers-pdf",
)

# 5. botoes no rodape (antes do Voltar)
src = replace_once(
    src,
    "      <div className=\"flex justify-end gap-2\">\n"
    "        <button\n"
    "          type=\"button\"\n"
    "          className=\"erp-btn-outline\"\n"
    "          onClick={onCancel}\n"
    "          disabled={saving}\n"
    "        >\n"
    "          Voltar\n"
    "        </button>\n",
    "      <div className=\"flex flex-wrap justify-end gap-2\">\n"
    "        {editing?.id ? (\n"
    "          <>\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"erp-btn-outline\"\n"
    "              onClick={() => void abrirPreviaPdf()}\n"
    "              disabled={pdfBusy !== null || editing.status !== 'rascunho'}\n"
    "              title={\n"
    "                editing.status !== 'rascunho'\n"
    "                  ? 'Previa disponivel apenas para rascunho.'\n"
    "                  : 'Gera previa do PDF a partir do rascunho atual.'\n"
    "              }\n"
    "            >\n"
    "              <FileText className=\"h-4 w-4 mr-1\" />\n"
    "              {pdfBusy === 'preview' ? 'Gerando previa...' : 'Previa PDF (rascunho)'}\n"
    "            </button>\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"erp-btn-outline\"\n"
    "              onClick={() => void baixarPdf()}\n"
    "              disabled={pdfBusy !== null}\n"
    "              title=\"Baixar PDF conforme o status atual.\"\n"
    "            >\n"
    "              <FileText className=\"h-4 w-4 mr-1\" />\n"
    "              {pdfBusy === 'download' ? 'Gerando...' : 'Baixar PDF'}\n"
    "            </button>\n"
    "          </>\n"
    "        ) : null}\n"
    "        <button\n"
    "          type=\"button\"\n"
    "          className=\"erp-btn-outline\"\n"
    "          onClick={onCancel}\n"
    "          disabled={saving}\n"
    "        >\n"
    "          Voltar\n"
    "        </button>\n",
    "botoes-pdf",
)

# 6. modal de previa antes do </div> final
src = replace_once(
    src,
    "          ) : null}\n"
    "        </div>\n"
    "      </Modal>\n"
    "    </div>\n"
    "  );\n"
    "}\n",
    "          ) : null}\n"
    "        </div>\n"
    "      </Modal>\n"
    "\n"
    "      <Modal\n"
    "        isOpen={previewPdfUrl != null}\n"
    "        onClose={() => {\n"
    "          if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);\n"
    "          setPreviewPdfUrl(null);\n"
    "        }}\n"
    "        title={previewPdfTitulo}\n"
    "        size=\"xl\"\n"
    "      >\n"
    "        {previewPdfUrl ? (\n"
    "          <div className=\"h-[78vh]\">\n"
    "            <iframe\n"
    "              title=\"Previa PDF do certificado\"\n"
    "              src={previewPdfUrl}\n"
    "              className=\"w-full h-full border border-border rounded\"\n"
    "            />\n"
    "          </div>\n"
    "        ) : null}\n"
    "      </Modal>\n"
    "    </div>\n"
    "  );\n"
    "}\n",
    "modal-previa",
)

# 7. atualiza placeholder cinza (remove mencao PDF)
src = replace_once(
    src,
    "        <p className=\"font-medium mb-1\">Corrida/lote, composição, componentes, corridas CF e rastreabilidade/PDF serão portados nas próximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontidão/origem · Etapa 5b-2/3/4: corrida/composição/componentes · Etapa 6: corridas CF · Etapa 7: rastreabilidade/PDF</p>\n",
    "        <p className=\"font-medium mb-1\">Rastreabilidade física por item será portada na próxima etapa</p>\n"
    "        <p>Etapa 8: rastreabilidade física por item</p>\n",
    "placeholder-pdf",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
