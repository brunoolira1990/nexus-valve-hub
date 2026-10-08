#!/usr/bin/env python3
"""Etapa 5b-1 — cria ItemEditor.tsx e substitui tabela read-only pelo editor."""
import shutil, sys, pathlib, datetime

WORKSPACE = pathlib.Path("src/pages/CertificadosQualidade/CertificadoQualidadeWorkspace.tsx")
ITEM_EDITOR = pathlib.Path("src/pages/CertificadosQualidade/ItemEditor.tsx")

if not WORKSPACE.exists():
    sys.exit(f"nao encontrei {WORKSPACE}")
if ITEM_EDITOR.exists():
    sys.exit(f"{ITEM_EDITOR} ja existe — abortar")

# ---------- 1. Cria ItemEditor.tsx ----------
ITEM_EDITOR_CONTENT = '''/**
 * Editor de item do Certificado de Qualidade.
 *
 * Etapa 5b-1 — subconjunto do editor do modal antigo:
 *  - Inputs basicos (ordem, codigo, descricao, qtd, un, norma, lote, ncm)
 *  - Tipo de dados tecnicos
 *  - Incluir no certificado + motivo/observacao
 *
 * Proximas sub-etapas:
 *  - 5b-2: corrida/lote + rastreabilidade por produto
 *  - 5b-3: composicao + ensaios
 *  - 5b-4: componentes de valvula
 *  - Etapa 6: corridas CF (via modal existente)
 */
import type { ItemCertificadoQualidade } from '@/types';
import {
  LABEL_OBRIGATORIO_EMITIR,
  MOTIVOS_NAO_INCLUSAO,
} from '@/lib/certificadoQualidadeConstants';
import {
  origemFisicaCqBadge,
  origemFisicaCqItem,
  rastreabilidadeCqBadge,
} from '@/lib/certificadoStatusUi';

type Props = {
  item: ItemCertificadoQualidade;
  idx: number;
  disabled?: boolean;
  onChange: (patch: Partial<ItemCertificadoQualidade>) => void;
};

export function ItemEditor({ item: it, idx, disabled, onChange }: Props) {
  const incl = it.incluir_no_certificado !== false;

  return (
    <details
      open
      className={`rounded border p-3 ${!incl ? 'border-amber-300 bg-amber-50/30 dark:border-amber-700 dark:bg-amber-900/10' : 'border-border'}`}
    >
      <summary className="cursor-pointer text-sm font-medium">
        <span className="inline-flex items-center gap-2 flex-wrap">
          <span>
            Item {it.ordem || idx + 1} - {it.codigo_produto || 'Sem codigo'} -{' '}
            {it.descricao_material || 'Sem descricao'}
          </span>
          {!incl ? (
            <span className="erp-badge-warning">Nao incluido</span>
          ) : (
            <span className="erp-badge-success">Incluido</span>
          )}
          {incl && it.rastreabilidade_status ? (
            <span
              className={`${rastreabilidadeCqBadge(it.rastreabilidade_status).className} text-[10px]`}
              title="Prontidao tecnica: dados exigidos para emissao do CQ. Nao comprova a origem fisica do material."
            >
              {it.rastreabilidade_label || rastreabilidadeCqBadge(it.rastreabilidade_status).label}
            </span>
          ) : null}
          {incl ? (
            <span
              className={`${origemFisicaCqBadge(origemFisicaCqItem(it)).className} text-[10px]`}
              title="Origem documental: vinculo com Certificado de Fornecedor e corrida/lote registrados."
            >
              {origemFisicaCqBadge(origemFisicaCqItem(it)).label}
            </span>
          ) : null}
        </span>
      </summary>

      {incl && (it.rastreabilidade_avisos?.length ?? 0) > 0 ? (
        <ul className="text-[11px] text-sky-800 dark:text-sky-300 mt-1 mb-2 list-disc pl-5">
          {it.rastreabilidade_avisos!.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      ) : null}

      {incl && (it.rastreabilidade_mensagens?.length ?? 0) > 0 ? (
        <ul className="text-[11px] text-amber-800 dark:text-amber-300 mt-1 mb-2 list-disc pl-5">
          {it.rastreabilidade_mensagens!.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-6 gap-2 mt-3">
        <div>
          <label className="erp-label">Ordem</label>
          <input
            className="erp-input mt-1"
            value={it.ordem}
            disabled={disabled}
            onChange={(e) => onChange({ ordem: +e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Codigo</label>
          <input
            className="erp-input mt-1"
            value={it.codigo_produto}
            disabled={disabled}
            onChange={(e) => onChange({ codigo_produto: e.target.value })}
          />
        </div>
        <div className="md:col-span-2">
          <label className="erp-label">Descricao{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.descricao_material}
            disabled={disabled}
            onChange={(e) => onChange({ descricao_material: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Qtd</label>
          <input
            className="erp-input mt-1"
            value={it.quantidade}
            disabled={disabled}
            onChange={(e) => onChange({ quantidade: +e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Un</label>
          <input
            className="erp-input mt-1"
            value={it.unidade}
            disabled={disabled}
            onChange={(e) => onChange({ unidade: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Norma{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.norma}
            disabled={disabled}
            onChange={(e) => onChange({ norma: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">Lote{LABEL_OBRIGATORIO_EMITIR}</label>
          <input
            className="erp-input mt-1"
            value={it.lote || ''}
            disabled={disabled}
            onChange={(e) => onChange({ lote: e.target.value })}
          />
        </div>
        <div>
          <label className="erp-label">NCM</label>
          <input
            className="erp-input mt-1"
            value={it.ncm || ''}
            disabled={disabled}
            onChange={(e) => onChange({ ncm: e.target.value })}
          />
        </div>
        <div className="md:col-span-3">
          <label className="erp-label">Tipo de dados tecnicos</label>
          <select
            className="erp-select mt-1 w-full"
            value={it.tipo_dados_tecnicos || 'PADRAO_ITEM'}
            disabled={disabled}
            onChange={(e) =>
              onChange({
                tipo_dados_tecnicos: e.target.value as 'PADRAO_ITEM' | 'VALVULA_COMPONENTES',
              })
            }
          >
            <option value="PADRAO_ITEM">Dados por item</option>
            <option value="VALVULA_COMPONENTES">Dados por componentes de valvula</option>
          </select>
        </div>
        <div className="md:col-span-6 rounded border border-border p-2">
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={incl}
              disabled={disabled}
              onChange={(e) => onChange({ incluir_no_certificado: e.target.checked })}
            />
            Incluir no certificado
          </label>
          {!incl ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
              <div>
                <label className="erp-label">Motivo da nao inclusao</label>
                <select
                  className="erp-select mt-1 w-full"
                  value={it.motivo_nao_inclusao || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ motivo_nao_inclusao: e.target.value })}
                >
                  <option value="">Selecione...</option>
                  {MOTIVOS_NAO_INCLUSAO.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="erp-label">Observacao interna</label>
                <input
                  className="erp-input mt-1"
                  value={it.observacao_nao_inclusao || ''}
                  disabled={disabled}
                  onChange={(e) => onChange({ observacao_nao_inclusao: e.target.value })}
                />
              </div>
              <div className="md:col-span-2 text-xs text-amber-700 dark:text-amber-300">
                Nao incluido
                {it.motivo_nao_inclusao ? ` - Motivo: ${it.motivo_nao_inclusao}` : ''}.
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </details>
  );
}
'''
ITEM_EDITOR.write_text(ITEM_EDITOR_CONTENT, encoding="utf-8")
print(f"  criado: {ITEM_EDITOR} ({len(ITEM_EDITOR_CONTENT)} bytes)")

# ---------- 2. Patch no Workspace ----------
src = WORKSPACE.read_text(encoding="utf-8")
orig = src

def replace_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        sys.exit(f"[{tag}] esperava 1 ocorrencia, achei {n}")
    print(f"  ok: {tag}")
    return text.replace(old, new, 1)

# 2a. import do ItemEditor
src = replace_once(
    src,
    "import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';\n",
    "import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';\n"
    "import { ItemEditor } from './ItemEditor';\n",
    "import-item-editor",
)

# 2b. import do tipo ItemCertificadoQualidade
src = replace_once(
    src,
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "} from '@/types';\n",
    "import type {\n"
    "  CertificadoQualidade,\n"
    "  CertificadoQualidadeStatus,\n"
    "  ItemCertificadoQualidade,\n"
    "} from '@/types';\n",
    "import-tipo-item",
)

# 2c. handler updateItem
src = replace_once(
    src,
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n",
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n"
    "\n"
    "  const updateItem = (idx: number, patch: Partial<ItemCertificadoQualidade>) =>\n"
    "    setForm((p) => ({\n"
    "      ...p,\n"
    "      itens: p.itens.map((it, i) => (i === idx ? { ...it, ...patch } : it)),\n"
    "    }));\n",
    "updateItem",
)

# 2d. substitui tabela por map de ItemEditor
OLD_TABLE = '''            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th className="text-left py-1 pr-2">#</th>
                    <th className="text-left py-1 pr-2">C\u00f3digo</th>
                    <th className="text-left py-1 pr-2">Descri\u00e7\u00e3o</th>
                    <th className="text-right py-1 pr-2">Qtd</th>
                    <th className="text-left py-1 pr-2">Un</th>
                    <th className="text-left py-1 pr-2">Norma</th>
                    <th className="text-left py-1 pr-2">Lote</th>
                    <th className="text-left py-1 pr-2">Rastreab.</th>
                    <th className="text-left py-1">Incl.</th>
                  </tr>
                </thead>
                <tbody>
                  {form.itens.map((it, idx) => (
                    <tr
                      key={it.id ?? idx}
                      className={
                        it.incluir_no_certificado === false
                          ? 'border-b border-border/50 bg-amber-50/30 dark:bg-amber-900/10'
                          : 'border-b border-border/50'
                      }
                    >
                      <td className="py-1 pr-2 tabular-nums">{it.ordem}</td>
                      <td className="py-1 pr-2 font-mono">{it.codigo_produto}</td>
                      <td className="py-1 pr-2">{it.descricao_material}</td>
                      <td className="py-1 pr-2 text-right tabular-nums">{it.quantidade}</td>
                      <td className="py-1 pr-2">{it.unidade}</td>
                      <td className="py-1 pr-2">{it.norma}</td>
                      <td className="py-1 pr-2">{it.lote || ''}</td>
                      <td className="py-1 pr-2">
                        {it.incluir_no_certificado !== false && it.rastreabilidade_status ? (
                          <span
                            className={
                              it.rastreabilidade_status === 'COMPLETA'
                                ? 'erp-badge-success text-[10px]'
                                : it.rastreabilidade_status === 'PARCIAL'
                                  ? 'erp-badge-warning text-[10px]'
                                  : 'erp-badge-danger text-[10px]'
                            }
                          >
                            {it.rastreabilidade_label || it.rastreabilidade_status}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">\u2014</span>
                        )}
                      </td>
                      <td className="py-1">
                        {it.incluir_no_certificado === false ? (
                          <span className="text-amber-700 dark:text-amber-300">N\u00e3o</span>
                        ) : (
                          <span className="text-emerald-700 dark:text-emerald-400">Sim</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
'''
NEW_EDITOR_LIST = '''            <div className="space-y-2">
              {form.itens.map((it, idx) => (
                <ItemEditor
                  key={it.id ?? idx}
                  item={it}
                  idx={idx}
                  disabled={nfeBloqueada || saving}
                  onChange={(patch) => updateItem(idx, patch)}
                />
              ))}
            </div>
'''
src = replace_once(src, OLD_TABLE, NEW_EDITOR_LIST, "substitui-tabela")

# 2e. atualiza placeholder cinza
src = replace_once(
    src,
    "        <p className=\"font-medium mb-1\">Editor de item, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5: editor \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>\n",
    "        <p className=\"font-medium mb-1\">Corrida/lote, composi\u00e7\u00e3o, componentes, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>\n"
    "        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5b-2/3/4: corrida/composi\u00e7\u00e3o/componentes \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>\n",
    "placeholder-atualizado",
)

# ---------- 3. backup + write ----------
if src == orig:
    sys.exit("nada mudou no Workspace — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = WORKSPACE.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(WORKSPACE, backup)
WORKSPACE.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {WORKSPACE} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
