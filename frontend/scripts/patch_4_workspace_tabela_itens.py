#!/usr/bin/env python3
"""Etapa 4 — tabela read-only de itens + contadores no Workspace."""
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

# 1. contadores derivados (logo apos nfeBloqueada)
src = replace_once(
    src,
    "  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');\n",
    "  const nfeBloqueada = Boolean(editing && editing.status !== 'rascunho');\n"
    "  const incluidosCount = form.itens.filter((it) => it.incluir_no_certificado !== false).length;\n"
    "  const naoIncluidosCount = form.itens.length - incluidosCount;\n",
    "counters",
)

# 2. substitui placeholder por bloco de tabela + placeholder atualizado
OLD = """      <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
        <p className="font-medium mb-1">Itens, prontid\u00e3o t\u00e9cnica e rastreabilidade ser\u00e3o portados nas pr\u00f3ximas etapas</p>
        <p>Etapa 3c: prontid\u00e3o/origem \u00b7 Etapa 4: tabela de itens \u00b7 Etapa 5: editor \u00b7 Etapa 7: rastreabilidade/PDF</p>
      </div>
"""
NEW = """      <div className="rounded border border-border bg-muted/10 p-3">
        <p className="text-sm font-medium mb-2">Itens do certificado</p>
        {form.itens.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Nenhum item carregado. Vincule uma NF-e acima e clique em \u00abCarregar dados da NF-e\u00bb.
          </p>
        ) : (
          <>
            <div className="mb-2 text-xs">
              <span className="text-muted-foreground">
                Itens: {form.itens.length} total | {incluidosCount} inclu\u00eddos
                {naoIncluidosCount > 0
                  ? ` | ${naoIncluidosCount} n\u00e3o inclu\u00eddo${naoIncluidosCount > 1 ? 's' : ''}`
                  : ''}
              </span>
              {incluidosCount === 0 ? (
                <p className="mt-1 text-amber-700 dark:text-amber-300">
                  Nenhum item inclu\u00eddo no certificado. Para emitir, inclua pelo menos um item.
                </p>
              ) : null}
            </div>
            <div className="overflow-x-auto">
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
          </>
        )}
      </div>

      <div className="rounded border border-dashed p-4 text-center text-xs text-muted-foreground">
        <p className="font-medium mb-1">Editor de item, corridas CF e rastreabilidade/PDF ser\u00e3o portados nas pr\u00f3ximas etapas</p>
        <p>Etapa 3c-2: prontid\u00e3o/origem \u00b7 Etapa 5: editor \u00b7 Etapa 6: corridas CF \u00b7 Etapa 7: rastreabilidade/PDF</p>
      </div>
"""
src = replace_once(src, OLD, NEW, "tabela-itens")

# 3. backup + write
if src == orig:
    sys.exit("nada mudou — abortar")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".tsx.bak_{stamp}")
shutil.copyfile(TARGET, backup)
TARGET.write_text(src, encoding="utf-8")
print(f"\nbackup: {backup}")
print(f"escrito: {TARGET} ({len(src)} bytes, {src.count(chr(10))+1} linhas)")
print("\nAGORA rode: npx tsc --noEmit")
