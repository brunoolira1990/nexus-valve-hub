#!/usr/bin/env python3
"""3b-Frontend (B): botao Reemitir no Workspace."""
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

# 1. Import useNavigate
src = replace_once(
    src,
    "import { AxiosError } from 'axios';\n",
    "import { AxiosError } from 'axios';\n"
    "import { useNavigate } from 'react-router-dom';\n",
    "import-usenavigate",
)

# 2. Hook + state reemiting
src = replace_once(
    src,
    "  const [pdfBusy, setPdfBusy] = useState<'preview' | 'download' | null>(null);\n",
    "  const [pdfBusy, setPdfBusy] = useState<'preview' | 'download' | null>(null);\n"
    "  const [reemiting, setReemiting] = useState(false);\n"
    "  const navigate = useNavigate();\n",
    "state-reemiting",
)

# 3. Handler antes do pdfMeta
src = replace_once(
    src,
    "  const pdfMeta = (): PdfFilenameInput => ({\n",
    "  const reemitir = async () => {\n"
    "    if (!editing?.id) return;\n"
    "    if (editing.status !== 'emitido') return;\n"
    "    const numero = editing.numero_formatado || editing.numero || 'CQ';\n"
    "    const ok = window.confirm(\n"
    "      `Reemitir o certificado ${numero}?\\n\\n`\n"
    "        + 'Isto criara um NOVO certificado em rascunho, com serie incrementada, '\n"
    "        + 'e marcara este como SUBSTITUIDO (registro preservado para auditoria).\\n\\n'\n"
    "        + 'Deseja continuar?',\n"
    "    );\n"
    "    if (!ok) return;\n"
    "    setReemiting(true);\n"
    "    setSaveError(null);\n"
    "    try {\n"
    "      const novo = await certificadosQualidadeService.reemitir(editing.id);\n"
    "      adicionarMensagensUnicas([\n"
    "        `Certificado reemitido: ${novo.numero_formatado || novo.numero}.`,\n"
    "      ]);\n"
    "      navigate(`/certificados-qualidade/${novo.id}`);\n"
    "    } catch (e) {\n"
    "      setSaveError(\n"
    "        apiErrorMessage(e, { fallback: 'Nao foi possivel reemitir o certificado.' }),\n"
    "      );\n"
    "    } finally {\n"
    "      setReemiting(false);\n"
    "    }\n"
    "  };\n"
    "\n"
    "  const pdfMeta = (): PdfFilenameInput => ({\n",
    "handler-reemitir",
)

# 4. Botao no rodape
src = replace_once(
    src,
    "            >\n"
    "              <FileText className=\"h-4 w-4 mr-1\" />\n"
    "              {pdfBusy === 'download' ? 'Gerando...' : 'Baixar PDF'}\n"
    "            </button>\n"
    "          </>\n"
    "        ) : null}\n",
    "            >\n"
    "              <FileText className=\"h-4 w-4 mr-1\" />\n"
    "              {pdfBusy === 'download' ? 'Gerando...' : 'Baixar PDF'}\n"
    "            </button>\n"
    "            {editing.status === 'emitido' ? (\n"
    "              <button\n"
    "                type=\"button\"\n"
    "                className=\"erp-btn-outline\"\n"
    "                onClick={() => void reemitir()}\n"
    "                disabled={reemiting || saving || pdfBusy !== null}\n"
    "                title=\"Cria um NOVO CQ em rascunho (serie incrementada) e marca este como SUBSTITUIDO.\"\n"
    "              >\n"
    "                {reemiting ? 'Reemitindo...' : 'Reemitir'}\n"
    "              </button>\n"
    "            ) : null}\n"
    "          </>\n"
    "        ) : null}\n",
    "botao-reemitir",
)

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
