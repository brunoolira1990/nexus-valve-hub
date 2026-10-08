#!/usr/bin/env python3
"""Etapa 3c-1 — porta select de NF-e saida historica para o Workspace."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
if not TARGET.exists():
    sys.exit(f"nao encontrei {TARGET}")

src = TARGET.read_text(encoding="utf-8")
orig = src

def replace_once(text: str, old: str, new: str, tag: str) -> str:
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

# 1. import do service de NF-e historica
src = replace_once(
    src,
    "import {\n"
    "  certificadosQualidadeService,\n"
    "  type NfeElegivelCqOpcao,\n"
    "} from '@/services/api/qualidade';\n",
    "import {\n"
    "  certificadosQualidadeService,\n"
    "  type NfeElegivelCqOpcao,\n"
    "} from '@/services/api/qualidade';\n"
    "import {\n"
    "  nfeHistoricaImportadaService,\n"
    "  type NFeSaidaHistoricaList,\n"
    "} from '@/services/api/nfeHistoricaImportada';\n",
    "import-historica",
)

# 2. state nfHistoricas
src = replace_once(
    src,
    "  const [carregandoNfe, setCarregandoNfe] = useState(false);\n",
    "  const [carregandoNfe, setCarregandoNfe] = useState(false);\n"
    "  const [nfHistoricas, setNfHistoricas] = useState<NFeSaidaHistoricaList[]>([]);\n",
    "state-nfHistoricas",
)

# 3. useEffect pra carregar nfHistoricas (uma vez)
src = replace_once(
    src,
    "      .finally(() => setLoading(false));\n"
    "  }, [certificadoId]);\n",
    "      .finally(() => setLoading(false));\n"
    "  }, [certificadoId]);\n"
    "\n"
    "  // Carrega NF-e de saida historicas (uma vez no mount)\n"
    "  useEffect(() => {\n"
    "    nfeHistoricaImportadaService\n"
    "      .list()\n"
    "      .then((r) => setNfHistoricas(r))\n"
    "      .catch(() => setNfHistoricas([]));\n"
    "  }, []);\n",
    "useEffect-historica",
)

# 4. JSX — select + move botao pra linha 2 (md:col-span-3)
src = replace_once(
    src,
    "          </div>\n"
    "          <div className=\"flex items-end\">\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"erp-btn-outline w-full md:w-auto\"\n"
    "              onClick={() => void carregarPorNFe()}\n"
    "              disabled={\n"
    "                carregandoNfe ||\n"
    "                nfeBloqueada ||\n"
    "                (!form.nota_fiscal && !form.nota_fiscal_historica)\n"
    "              }\n"
    "            >\n"
    "              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}\n"
    "            </button>\n"
    "          </div>\n",
    "          </div>\n"
    "          <div>\n"
    "            <label className=\"erp-label\">NF-e sa\u00edda hist\u00f3rica</label>\n"
    "            <select\n"
    "              className=\"erp-select mt-1 w-full\"\n"
    "              value={form.nota_fiscal_historica || ''}\n"
    "              disabled={nfeBloqueada}\n"
    "              onChange={(e) => {\n"
    "                const histId = e.target.value ? +e.target.value : null;\n"
    "                setNfeOpcaoSelecionada(null);\n"
    "                setF('nota_fiscal_historica', histId);\n"
    "                setF('nota_fiscal', null);\n"
    "                setMensagens([]);\n"
    "              }}\n"
    "            >\n"
    "              <option value=\"\">Selecione...</option>\n"
    "              {nfHistoricas.map((n) => (\n"
    "                <option key={n.id} value={n.id}>\n"
    "                  {n.numero}/{n.serie} - {n.cliente_nome} - {n.dh_emissao.slice(0, 10)}\n"
    "                </option>\n"
    "              ))}\n"
    "            </select>\n"
    "          </div>\n"
    "          <div className=\"flex items-end md:col-span-3\">\n"
    "            <button\n"
    "              type=\"button\"\n"
    "              className=\"erp-btn-outline w-full md:w-auto\"\n"
    "              onClick={() => void carregarPorNFe()}\n"
    "              disabled={\n"
    "                carregandoNfe ||\n"
    "                nfeBloqueada ||\n"
    "                (!form.nota_fiscal && !form.nota_fiscal_historica)\n"
    "              }\n"
    "            >\n"
    "              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}\n"
    "            </button>\n"
    "          </div>\n",
    "jsx-historica",
)

# 5. backup + write
if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
