#!/usr/bin/env python3
"""Etapa 3b — porta busca de NF-e elegivel para CertificadoQualidadeWorkspace.tsx."""
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

# ---------- 1. imports ----------
src = replace_once(
    src,
    "import { useEffect, useState } from 'react';\n"
    "import { certificadosQualidadeService } from '@/services/api/qualidade';\n",
    "import { useCallback, useEffect, useState } from 'react';\n"
    "import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';\n"
    "import {\n"
    "  certificadosQualidadeService,\n"
    "  type NfeElegivelCqOpcao,\n"
    "} from '@/services/api/qualidade';\n",
    "imports",
)

# ---------- 2. novo state ----------
src = replace_once(
    src,
    "  const [saveError, setSaveError] = useState<string | null>(null);\n",
    "  const [saveError, setSaveError] = useState<string | null>(null);\n"
    "  const [nfeOpcaoSelecionada, setNfeOpcaoSelecionada] = useState<NfeElegivelCqOpcao | null>(null);\n"
    "  const [mensagens, setMensagens] = useState<string[]>([]);\n"
    "  const [carregandoNfe, setCarregandoNfe] = useState(false);\n",
    "novo-state",
)

# ---------- 3. reset branch (novo CQ) ----------
src = replace_once(
    src,
    "    if (!certificadoId) {\n"
    "      setEditing(null);\n"
    "      setForm(emptyForm());\n"
    "      setSaveError(null);\n"
    "      return;\n"
    "    }\n",
    "    if (!certificadoId) {\n"
    "      setEditing(null);\n"
    "      setForm(emptyForm());\n"
    "      setSaveError(null);\n"
    "      setNfeOpcaoSelecionada(null);\n"
    "      setMensagens([]);\n"
    "      return;\n"
    "    }\n",
    "reset-branch",
)

# ---------- 4. load branch: resolver opcao ao carregar ----------
src = replace_once(
    src,
    "        });\n"
    "        setSaveError(null);\n"
    "      })\n"
    "      .catch((e) => setSaveError(apiErrorMessage(e)))",
    "        });\n"
    "        setSaveError(null);\n"
    "        setNfeOpcaoSelecionada(null);\n"
    "        if (row.nota_fiscal) {\n"
    "          void certificadosQualidadeService.obterNfeOpcao(row.nota_fiscal).then((opt) => {\n"
    "            if (opt) setNfeOpcaoSelecionada(opt);\n"
    "            else {\n"
    "              setNfeOpcaoSelecionada({\n"
    "                id: row.nota_fiscal!,\n"
    "                label_principal: row.nota_fiscal_numero\n"
    "                  ? `NF-e ${row.nota_fiscal_numero}`\n"
    "                  : `NF-e vinculada #${row.nota_fiscal}`,\n"
    "                label_secundario: 'Documento legado — verifique elegibilidade',\n"
    "                ambiente_badge: null,\n"
    "                numero_nfe: '',\n"
    "                serie_nfe: '',\n"
    "                cliente_nome: row.cliente_nome_snapshot || '',\n"
    "                data_emissao: row.data_emissao || null,\n"
    "                status_emissao_sefaz: '',\n"
    "                elegivel: false,\n"
    "              });\n"
    "            }\n"
    "          });\n"
    "        }\n"
    "      })\n"
    "      .catch((e) => setSaveError(apiErrorMessage(e)))",
    "load-branch",
)

# ---------- 5. handlers: busca + selecionarNfe + carregarPorNFe ----------
HANDLERS_ANCHOR = (
    "  const setF = <K extends keyof FormState>(key: K, value: FormState[K]) => {\n"
    "    setForm((prev) => ({ ...prev, [key]: value }));\n"
    "  };\n"
)
assert src.count(HANDLERS_ANCHOR) == 1
HANDLERS_NEW = HANDLERS_ANCHOR + """
  const buscaNfesElegiveis = useCallback(
    (term: string, limit?: number) =>
      certificadosQualidadeService.buscarNfesElegiveis(term, limit ?? 20),
    [],
  );

  const selecionarNfe = useCallback(
    (id: number | string | null, option?: NfeElegivelCqOpcao | null) => {
      const nextId = id == null || id === '' ? null : Number(id);
      const trocando = nextId !== form.nota_fiscal;
      if (option && !option.elegivel && trocando) return;
      const temItens = (form.itens?.length ?? 0) > 0;
      if (trocando && temItens) {
        const ok = window.confirm(
          'Trocar a NF-e limpara os itens e dados tecnicos ja carregados desta nota. Continuar?',
        );
        if (!ok) return;
      }
      setNfeOpcaoSelecionada(option ?? null);
      setForm((p) => ({
        ...p,
        nota_fiscal: nextId,
        nota_fiscal_historica: null,
        nota_fiscal_numero:
          option && option.numero_nfe
            ? `${option.numero_nfe}${option.serie_nfe ? `/${option.serie_nfe}` : ''}`
            : nextId
              ? p.nota_fiscal_numero
              : '',
        ...(trocando
          ? {
              itens: [],
              cliente: null,
              cliente_nome_snapshot: '',
              cliente_cnpj_snapshot: '',
              pedido_cliente: '',
              data_emissao: '',
            }
          : {}),
      }));
      setMensagens([]);
    },
    [form.nota_fiscal, form.itens],
  );

  const carregarPorNFe = async () => {
    setSaveError(null);
    setMensagens([]);
    setCarregandoNfe(true);
    try {
      const data = await certificadosQualidadeService.preencherPorNfe({
        nf_saida_id: form.nota_fiscal || undefined,
        nf_saida_historica_id: form.nota_fiscal_historica || undefined,
      });
      setForm((p) => ({
        ...p,
        cliente: data.cliente ?? p.cliente,
        cliente_nome_snapshot: data.cliente_nome_snapshot ?? p.cliente_nome_snapshot,
        cliente_cnpj_snapshot: data.cliente_cnpj_snapshot ?? p.cliente_cnpj_snapshot,
        pedido_cliente: data.pedido_cliente ?? p.pedido_cliente,
        nota_fiscal_numero: data.nota_fiscal_numero ?? p.nota_fiscal_numero,
        nota_fiscal: data.nota_fiscal ?? p.nota_fiscal,
        nota_fiscal_historica: data.nota_fiscal_historica ?? p.nota_fiscal_historica,
        data_emissao: data.data_emissao ?? p.data_emissao,
      }));
      if (data.nota_fiscal) {
        void certificadosQualidadeService.obterNfeOpcao(data.nota_fiscal).then((opt) => {
          if (opt) setNfeOpcaoSelecionada(opt);
        });
      }
      const msg = [...(data.mensagens || [])];
      const nItens = Array.isArray(data.itens) ? data.itens.length : 0;
      if (nItens > 0) {
        msg.push(
          `${nItens} item(ns) retornado(s) pela NF-e. A tabela de itens sera portada na Etapa 4.`,
        );
      }
      setMensagens(msg);
    } catch (e) {
      setSaveError(apiErrorMessage(e));
    } finally {
      setCarregandoNfe(false);
    }
  };

  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');
"""
src = src.replace(HANDLERS_ANCHOR, HANDLERS_NEW, 1)
print("  ok: handlers")

# ---------- 6. JSX: substituir placeholder por bloco NF-e + placeholder atualizado ----------
OLD_PLACEHOLDER = """      <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
        <p className="font-medium mb-1">Itens e NF-e serao portados nas proximas etapas</p>
        <p>Etapa 3b: busca de NF-e elegivel \u00b7 Etapa 4: tabela de itens \u00b7 Etapa 5: editor</p>
      </div>
"""
NEW_BLOCK = """      <div className="rounded border border-border bg-muted/20 p-3">
        <p className="text-sm font-medium mb-2">NF-e de sa\u00edda vinculada</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-2">
            <label className="erp-label">NF-e de sa\u00edda</label>
            <AsyncAutocomplete<NfeElegivelCqOpcao>
              value={form.nota_fiscal}
              selectedOption={nfeOpcaoSelecionada}
              placeholder="Buscar por n\u00famero da NF-e ou cliente..."
              emptyMessage="Nenhuma NF-e autorizada encontrada."
              minChars={2}
              limit={20}
              disabled={nfeBloqueada}
              search={buscaNfesElegiveis}
              getOptionValue={(o) => o.id}
              getOptionLabel={(o) => o.label_principal}
              renderOption={(o) => (
                <div className="flex flex-col gap-0.5 py-0.5">
                  <span className="font-medium text-sm">{o.label_principal}</span>
                  <span className="text-xs text-muted-foreground flex flex-wrap items-center gap-1">
                    {o.label_secundario}
                    {o.ambiente_badge ? (
                      <span
                        className={
                          o.ambiente_badge === 'Produ\u00e7\u00e3o'
                            ? 'erp-badge-success text-[10px]'
                            : 'erp-badge-warning text-[10px]'
                        }
                      >
                        {o.ambiente_badge}
                      </span>
                    ) : null}
                  </span>
                </div>
              )}
              onChange={selecionarNfe}
            />
            {nfeOpcaoSelecionada && !nfeOpcaoSelecionada.elegivel ? (
              <p className="text-xs text-amber-800 dark:text-amber-300 mt-1">
                {nfeOpcaoSelecionada.ambiente_badge === 'Homologa\u00e7\u00e3o'
                  ? 'Esta NF-e vinculada foi autorizada em homologa\u00e7\u00e3o e n\u00e3o pode ser usada em novo CQ de sa\u00edda. O registro legado \u00e9 preservado; selecione uma NF-e autorizada em produ\u00e7\u00e3o para alterar o v\u00ednculo.'
                  : 'Esta NF-e vinculada n\u00e3o est\u00e1 eleg\u00edvel pelas regras atuais (ex.: rascunho, cancelada ou sem autoriza\u00e7\u00e3o fiscal em produ\u00e7\u00e3o). O registro legado \u00e9 preservado; selecione uma NF-e autorizada em produ\u00e7\u00e3o para alterar o v\u00ednculo.'}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground mt-1">
                Somente NF-e de sa\u00edda autorizadas em produ\u00e7\u00e3o, com n\u00famero e s\u00e9rie fiscais.
              </p>
            )}
          </div>
          <div className="flex items-end">
            <button
              type="button"
              className="erp-btn-outline w-full md:w-auto"
              onClick={() => void carregarPorNFe()}
              disabled={
                carregandoNfe ||
                nfeBloqueada ||
                (!form.nota_fiscal && !form.nota_fiscal_historica)
              }
            >
              {carregandoNfe ? 'Carregando...' : 'Carregar dados da NF-e'}
            </button>
          </div>
        </div>

        {mensagens.length > 0 ? (
          <ul className="mt-2 space-y-1">
            {mensagens.map((m, i) => (
              <li key={i} className="text-xs text-muted-foreground">
                {m}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
        <p className="font-medium mb-1">Itens, prontid\u00e3o t\u00e9cnica e rastreabilidade ser\u00e3o portados nas pr\u00f3ximas etapas</p>
        <p>Etapa 3c: prontid\u00e3o/origem \u00b7 Etapa 4: tabela de itens \u00b7 Etapa 5: editor \u00b7 Etapa 7: rastreabilidade/PDF</p>
      </div>
"""
src = replace_once(src, OLD_PLACEHOLDER, NEW_BLOCK, "jsx-placeholder")

# ---------- 7. backup + write ----------
if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
