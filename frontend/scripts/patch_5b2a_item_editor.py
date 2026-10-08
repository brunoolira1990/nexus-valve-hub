#!/usr/bin/env python3
"""Etapa 5b-2a (A) — adiciona bloco corrida/lote ao ItemEditor."""
import shutil, sys, pathlib, datetime

TARGET = pathlib.Path("src/pages/CertificadosQualidade/ItemEditor.tsx")
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

# 1. imports adicionais
src = replace_once(
    src,
    "import type { ItemCertificadoQualidade } from '@/types';\n",
    "import type {\n"
    "  CorridaDisponivelCertificadoQualidade,\n"
    "  ItemCertificadoQualidade,\n"
    "  Produto,\n"
    "} from '@/types';\n",
    "imports-types",
)

src = replace_once(
    src,
    "import {\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "  MOTIVOS_NAO_INCLUSAO,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "import {\n"
    "  LABEL_OBRIGATORIO_EMITIR,\n"
    "  MOTIVOS_NAO_INCLUSAO,\n"
    "  coerceProdutoItemId,\n"
    "} from '@/lib/certificadoQualidadeConstants';\n",
    "imports-constants",
)

# 2. tipo CorridasProps + campo nas Props
src = replace_once(
    src,
    "type Props = {\n"
    "  item: ItemCertificadoQualidade;\n"
    "  idx: number;\n"
    "  disabled?: boolean;\n"
    "  onChange: (patch: Partial<ItemCertificadoQualidade>) => void;\n"
    "};\n",
    "export type CorridasProps = {\n"
    "  produtoBusca?: string;\n"
    "  produtoResultados: Produto[];\n"
    "  corridasDisponiveis: CorridaDisponivelCertificadoQualidade[];\n"
    "  onBuscarProdutos: (term: string) => void;\n"
    "  onVincularProduto: (p: Produto) => void;\n"
    "  onCarregarCorridas: () => void;\n"
    "  onAplicarCorrida: (valorSelecao: string) => void;\n"
    "};\n"
    "\n"
    "type Props = {\n"
    "  item: ItemCertificadoQualidade;\n"
    "  idx: number;\n"
    "  disabled?: boolean;\n"
    "  onChange: (patch: Partial<ItemCertificadoQualidade>) => void;\n"
    "  corridas?: CorridasProps;\n"
    "};\n",
    "props-corridas",
)

src = replace_once(
    src,
    "export function ItemEditor({ item: it, idx, disabled, onChange }: Props) {\n",
    "export function ItemEditor({ item: it, idx, disabled, onChange, corridas }: Props) {\n",
    "destructure-corridas",
)

# 3. bloco JSX corridas (entre select tipo_dados_tecnicos e incluir_no_certificado)
OLD = (
    "            <option value=\"VALVULA_COMPONENTES\">Dados por componentes de valvula</option>\n"
    "          </select>\n"
    "        </div>\n"
    "        <div className=\"md:col-span-6 rounded border border-border p-2\">\n"
)
NEW = (
    "            <option value=\"VALVULA_COMPONENTES\">Dados por componentes de valvula</option>\n"
    "          </select>\n"
    "        </div>\n"
    "\n"
    "        {corridas ? (\n"
    "          <div className=\"md:col-span-6 rounded border border-border p-2 bg-muted/10\">\n"
    "            <p className=\"text-xs font-semibold mb-2\">Rastreabilidade por produto cadastrado + Corrida/Lote</p>\n"
    "            {it.produto ? (\n"
    "              <div className=\"text-xs mb-2\">\n"
    "                <p>\n"
    "                  Produto cadastrado: {it.produto_codigo || '\u2014'} - {it.produto_descricao || '\u2014'}\n"
    "                  {it.produto_ncm_efetivo ? ` | NCM efetivo: ${it.produto_ncm_efetivo}` : ''}\n"
    "                </p>\n"
    "              </div>\n"
    "            ) : (\n"
    "              <p className=\"text-xs text-amber-700 dark:text-amber-300 mb-2\">\n"
    "                Este item da NF-e ainda nao esta vinculado a um produto cadastrado. Vincule o produto para listar corridas disponiveis.\n"
    "              </p>\n"
    "            )}\n"
    "            <div className=\"grid grid-cols-1 md:grid-cols-3 gap-2\">\n"
    "              <div className=\"md:col-span-2\">\n"
    "                <label className=\"erp-label\">Selecionar produto cadastrado (autocomplete)</label>\n"
    "                <input\n"
    "                  className=\"erp-input mt-1\"\n"
    "                  placeholder=\"Digite codigo ou descricao\"\n"
    "                  value={\n"
    "                    corridas.produtoBusca ??\n"
    "                    (it.produto ? `${it.produto_codigo || ''} - ${it.produto_descricao || ''}` : '')\n"
    "                  }\n"
    "                  disabled={disabled}\n"
    "                  onChange={(e) => corridas.onBuscarProdutos(e.target.value)}\n"
    "                />\n"
    "                {corridas.produtoResultados.length > 0 ? (\n"
    "                  <div className=\"mt-1 rounded border border-border max-h-32 overflow-auto bg-background\">\n"
    "                    {corridas.produtoResultados.map((p) => (\n"
    "                      <button\n"
    "                        key={p.id}\n"
    "                        type=\"button\"\n"
    "                        className=\"w-full text-left px-2 py-1 text-xs hover:bg-muted\"\n"
    "                        onClick={() => corridas.onVincularProduto(p)}\n"
    "                      >\n"
    "                        {p.codigo_completo} - {p.descricao}\n"
    "                      </button>\n"
    "                    ))}\n"
    "                  </div>\n"
    "                ) : null}\n"
    "              </div>\n"
    "              <div className=\"flex items-end\">\n"
    "                <button\n"
    "                  type=\"button\"\n"
    "                  className=\"erp-btn-outline w-full\"\n"
    "                  disabled={!it.produto || disabled}\n"
    "                  onClick={corridas.onCarregarCorridas}\n"
    "                >\n"
    "                  Listar corridas\n"
    "                </button>\n"
    "              </div>\n"
    "            </div>\n"
    "            <div className=\"mt-2\">\n"
    "              <label className=\"erp-label\">Corrida/Lote disponivel</label>\n"
    "              <select\n"
    "                className=\"erp-select mt-1 w-full\"\n"
    "                disabled={!coerceProdutoItemId(it.produto) || disabled}\n"
    "                value={(() => {\n"
    "                  const list = corridas.corridasDisponiveis || [];\n"
    "                  const corrEff = it.corrida || it.corrida_snapshot || '';\n"
    "                  const loteEff = it.lote || it.lote_snapshot || '';\n"
    "                  const match = list.find(\n"
    "                    (c) => c.corrida === corrEff && (c.lote || '') === (loteEff || ''),\n"
    "                  );\n"
    "                  return match?.valor_selecao || `${corrEff}||${loteEff}`;\n"
    "                })()}\n"
    "                onChange={(e) => {\n"
    "                  const selected = e.target.value;\n"
    "                  if (!selected) {\n"
    "                    onChange({ corrida: '', lote: '' });\n"
    "                    return;\n"
    "                  }\n"
    "                  const [cPart, lPart] = selected.split('||');\n"
    "                  onChange({ corrida: cPart || '', lote: lPart || '' });\n"
    "                  corridas.onAplicarCorrida(selected);\n"
    "                }}\n"
    "              >\n"
    "                <option value=\"\">Selecione a corrida disponivel...</option>\n"
    "                {(() => {\n"
    "                  const list = corridas.corridasDisponiveis || [];\n"
    "                  const corrEff = it.corrida || it.corrida_snapshot || '';\n"
    "                  const loteEff = it.lote || it.lote_snapshot || '';\n"
    "                  const manualVal = `${corrEff}||${loteEff}`;\n"
    "                  const inList = list.some(\n"
    "                    (c) => (c.valor_selecao || `${c.corrida}||${c.lote || ''}`) === manualVal,\n"
    "                  );\n"
    "                  const extra =\n"
    "                    (corrEff || loteEff) && !inList && manualVal !== '||' ? (\n"
    "                      <option key={`__manual_cq__-${idx}`} value={manualVal}>\n"
    "                        Corrida/lote manual: {corrEff}\n"
    "                        {loteEff ? ` / ${loteEff}` : ''}\n"
    "                      </option>\n"
    "                    ) : null;\n"
    "                  return (\n"
    "                    <>\n"
    "                      {extra}\n"
    "                      {list.map((c) => (\n"
    "                        <option\n"
    "                          key={c.valor_selecao || `${c.corrida}-${c.lote || ''}`}\n"
    "                          value={c.valor_selecao || `${c.corrida}||${c.lote || ''}`}\n"
    "                        >\n"
    "                          {c.corrida}\n"
    "                          {c.lote ? `/${c.lote}` : ''}\n"
    "                          {c.saldo ? ` - Saldo: ${c.saldo} ${c.unidade || ''}` : ''}\n"
    "                          {c.fornecedor ? ` - ${c.fornecedor}` : ''}\n"
    "                        </option>\n"
    "                      ))}\n"
    "                    </>\n"
    "                  );\n"
    "                })()}\n"
    "              </select>\n"
    "              {coerceProdutoItemId(it.produto) &&\n"
    "              (corridas.corridasDisponiveis || []).length === 0 ? (\n"
    "                <p className=\"text-xs text-amber-700 dark:text-amber-300 mt-1\">\n"
    "                  Nenhuma corrida/lote disponivel encontrada para este produto cadastrado.\n"
    "                </p>\n"
    "              ) : null}\n"
    "            </div>\n"
    "            <div className=\"flex flex-col sm:flex-row gap-2 mt-2\">\n"
    "              <div className=\"flex-1\">\n"
    "                <label className=\"erp-label\">Corrida manual{LABEL_OBRIGATORIO_EMITIR}</label>\n"
    "                <input\n"
    "                  className=\"erp-input mt-1\"\n"
    "                  placeholder=\"Ex.: HEN-001\"\n"
    "                  value={it.corrida || it.corrida_snapshot || ''}\n"
    "                  disabled={disabled}\n"
    "                  onChange={(e) => {\n"
    "                    const v = e.target.value;\n"
    "                    onChange({\n"
    "                      corrida: v,\n"
    "                      origem_rastreabilidade_tipo: 'manual',\n"
    "                      ...(v.trim() === '' ? { corrida_snapshot: '' } : {}),\n"
    "                    });\n"
    "                  }}\n"
    "                />\n"
    "              </div>\n"
    "              <div className=\"flex-1\">\n"
    "                <label className=\"erp-label\">Lote manual</label>\n"
    "                <input\n"
    "                  className=\"erp-input mt-1\"\n"
    "                  value={it.lote || it.lote_snapshot || ''}\n"
    "                  disabled={disabled}\n"
    "                  onChange={(e) => onChange({ lote: e.target.value })}\n"
    "                />\n"
    "              </div>\n"
    "            </div>\n"
    "          </div>\n"
    "        ) : null}\n"
    "\n"
    "        <div className=\"md:col-span-6 rounded border border-border p-2\">\n"
)
src = replace_once(src, OLD, NEW, "bloco-corridas")

if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
