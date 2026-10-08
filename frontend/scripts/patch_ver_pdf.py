#!/usr/bin/env python3
"""Fix: botao 'Ver PDF' quando emitido/cancelado + preserva 'Previa' pra rascunho."""
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

# 1. Renomear abrirPreviaPdf -> abrirPdfModal (aceita preview dinamico)
src = replace_once(
    src,
    "  const abrirPreviaPdf = async () => {\n"
    "    if (!editing?.id) return;\n"
    "    setPdfBusy('preview');\n"
    "    setSaveError(null);\n"
    "    try {\n"
    "      const blob = await certificadosQualidadeService.obterPdfBlob(editing.id, true);\n",
    "  const abrirPdfModal = async () => {\n"
    "    if (!editing?.id) return;\n"
    "    setPdfBusy('preview');\n"
    "    setSaveError(null);\n"
    "    try {\n"
    "      const preview = editing.status === 'rascunho';\n"
    "      const blob = await certificadosQualidadeService.obterPdfBlob(editing.id, preview);\n",
    "handler-renomeia",
)

# 2. Titulo dinamico (mostra 'Ver PDF' ou 'Previa')
src = replace_once(
    src,
    "      setPreviewPdfTitulo(\n"
    "        `Previa PDF \\u2014 ${editing.numero_formatado || editing.numero || 'CQ'}`,\n"
    "      );\n",
    "      const prefixo = editing.status === 'rascunho' ? 'Previa' : 'PDF';\n"
    "      setPreviewPdfTitulo(\n"
    "        `${prefixo} \\u2014 ${editing.numero_formatado || editing.numero || 'CQ'}`,\n"
    "      );\n",
    "titulo-dinamico",
)

# 3. Botao "Previa PDF" -> mantem so pra rascunho + adiciona "Ver PDF" pra emitido/cancelado
src = replace_once(
    src,
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
    "            </button>\n",
    "            {editing.status === 'rascunho' ? (\n"
    "              <button\n"
    "                type=\"button\"\n"
    "                className=\"erp-btn-outline\"\n"
    "                onClick={() => void abrirPdfModal()}\n"
    "                disabled={pdfBusy !== null}\n"
    "                title=\"Gera previa do PDF a partir do rascunho atual.\"\n"
    "              >\n"
    "                <FileText className=\"h-4 w-4 mr-1\" />\n"
    "                {pdfBusy === 'preview' ? 'Gerando previa...' : 'Previa PDF (rascunho)'}\n"
    "              </button>\n"
    "            ) : (\n"
    "              <button\n"
    "                type=\"button\"\n"
    "                className=\"erp-btn-outline\"\n"
    "                onClick={() => void abrirPdfModal()}\n"
    "                disabled={pdfBusy !== null}\n"
    "                title=\"Abrir PDF do certificado.\"\n"
    "              >\n"
    "                <FileText className=\"h-4 w-4 mr-1\" />\n"
    "                {pdfBusy === 'preview' ? 'Gerando...' : 'Ver PDF'}\n"
    "              </button>\n"
    "            )}\n",
    "botao-ver-pdf",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
