import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { formatMoneyBRL } from '@/lib/money';
import { formatQuantityBR } from '@/lib/numberFields';
import { nfeEntradasService } from '@/services/api/fiscal';
import { apiErrorMessage } from '@/services/api/config';
import type { ItemNFe, NFeEntrada } from '@/types';

type Props = {
  nfe: NFeEntrada;
  onAtualizado: () => void | Promise<void>;
};

function labelFinNfe(fin?: string | null): string {
  const v = (fin || '').trim();
  if (v === '1') return '1 — Normal';
  if (v === '2') return '2 — Complementar';
  if (v === '3') return '3 — Ajuste';
  if (v === '4') return '4 — Devolução';
  return v || '—';
}

function labelAmbiente(amb?: string | null): string {
  const v = (amb || '').trim().toLowerCase();
  if (v === 'homologacao') return 'Homologação';
  if (v === 'producao') return 'Produção';
  return amb || '—';
}

function cstIcms(impostos?: Record<string, unknown> | null): string {
  if (!impostos || typeof impostos !== 'object') return '—';
  const icms = impostos.icms;
  if (!icms || typeof icms !== 'object') return '—';
  const cst = String((icms as Record<string, unknown>).cst || '').trim();
  return cst || '—';
}

function podeEditarItens(nfe: NFeEntrada): boolean {
  const st = (nfe.status_emissao_sefaz || '').toUpperCase();
  if (st.includes('AUTORIZADA')) return false;
  return (nfe.status_operacional || '').toUpperCase() === 'RASCUNHO';
}

export function NFeEntradaEmitidaRevisaoFiscal({ nfe, onAtualizado }: Props) {
  const editavel = podeEditarItens(nfe);
  const [itensDraft, setItensDraft] = useState<ItemNFe[]>(nfe.itens || []);
  const [finDraft, setFinDraft] = useState(nfe.fin_nfe || '');
  const [natDraft, setNatDraft] = useState(nfe.nat_op || '');
  const [chaveRefDraft, setChaveRefDraft] = useState(nfe.chave_nfe_referenciada || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setItensDraft(nfe.itens || []);
    setFinDraft(nfe.fin_nfe || '');
    setNatDraft(nfe.nat_op || '');
    setChaveRefDraft(nfe.chave_nfe_referenciada || '');
  }, [nfe]);

  const dirty = useMemo(() => {
    if (!editavel) return false;
    if ((finDraft || '') !== (nfe.fin_nfe || '')) return true;
    if ((natDraft || '') !== (nfe.nat_op || '')) return true;
    if ((chaveRefDraft || '') !== (nfe.chave_nfe_referenciada || '')) return true;
    const orig = nfe.itens || [];
    if (itensDraft.length !== orig.length) return true;
    return itensDraft.some((it, i) => {
      const o = orig[i];
      if (!o) return true;
      return (
        (it.cfop || '') !== (o.cfop || '') ||
        (it.ncm || '') !== (o.ncm || '') ||
        (it.unidade || '') !== (o.unidade || '')
      );
    });
  }, [editavel, finDraft, natDraft, chaveRefDraft, itensDraft, nfe]);

  const atualizarItem = (id: number, patch: Partial<ItemNFe>) => {
    setItensDraft((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  };

  const salvar = async () => {
    if (!editavel) return;
    for (const it of itensDraft) {
      if (!(it.cfop || '').trim()) {
        toast.error(`Informe o CFOP do item ${it.numero_item ?? it.id}.`);
        return;
      }
      if (!(it.ncm || '').trim()) {
        toast.error(`Informe o NCM do item ${it.numero_item ?? it.id}.`);
        return;
      }
    }
    setSaving(true);
    try {
      await nfeEntradasService.update(nfe.id, {
        fin_nfe: finDraft,
        nat_op: natDraft,
        chave_nfe_referenciada: chaveRefDraft,
        empresa_emitente_id: nfe.empresa_emitente_id,
        cliente_destinatario_id: nfe.cliente_destinatario_id,
        fornecedor_id: nfe.fornecedor_id,
        data: nfe.data,
        ambiente_emissao: nfe.ambiente_emissao,
        itens: itensDraft,
      });
      toast.success('Dados fiscais da entrada própria atualizados.');
      await onAtualizado();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível salvar os dados fiscais.' }));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="nexus-card p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold">Revisão fiscal (antes da emissão)</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Confira finalidade, natureza, NF-e referenciada e o CFOP de cada item — é o que irá no XML.
        </p>
      </div>

      <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-3">
        <div>
          <dt className="text-xs text-muted-foreground">Finalidade (finNFe)</dt>
          <dd className="mt-0.5">
            {editavel ? (
              <select
                className="erp-input w-full text-sm"
                value={finDraft}
                onChange={(e) => setFinDraft(e.target.value)}
              >
                <option value="1">1 — Normal</option>
                <option value="2">2 — Complementar</option>
                <option value="3">3 — Ajuste</option>
                <option value="4">4 — Devolução</option>
              </select>
            ) : (
              <span className="font-medium">{labelFinNfe(nfe.fin_nfe)}</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Ambiente</dt>
          <dd className="font-medium mt-0.5">{labelAmbiente(nfe.ambiente_emissao)}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted-foreground">Natureza da operação</dt>
          <dd className="mt-0.5">
            {editavel ? (
              <input
                className="erp-input w-full text-sm"
                value={natDraft}
                maxLength={60}
                onChange={(e) => setNatDraft(e.target.value)}
              />
            ) : (
              <span className="font-medium">{nfe.nat_op || '—'}</span>
            )}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted-foreground">Chave NF-e referenciada</dt>
          <dd className="mt-0.5">
            {editavel ? (
              <input
                className="erp-input w-full font-mono text-xs"
                value={chaveRefDraft}
                maxLength={44}
                onChange={(e) => setChaveRefDraft(e.target.value.replace(/\D/g, '').slice(0, 44))}
              />
            ) : (
              <span className="font-mono text-xs break-all">{nfe.chave_nfe_referenciada || '—'}</span>
            )}
          </dd>
        </div>
      </dl>

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">
          Itens ({itensDraft.length}) — CFOP / NCM que vão para a SEFAZ
        </p>
        {itensDraft.length === 0 ? (
          <p className="text-sm text-destructive">Nenhum item na entrada própria. Não emita sem itens.</p>
        ) : (
          <div className="border border-border rounded-md overflow-x-auto">
            <table className="erp-table text-xs w-full">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Produto</th>
                  <th>NCM</th>
                  <th>CFOP</th>
                  <th>CST</th>
                  <th>Un.</th>
                  <th className="text-right">Qtd</th>
                  <th className="text-right">V. unit.</th>
                  <th className="text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {itensDraft.map((it, idx) => (
                  <tr key={it.id}>
                    <td className="nexus-numeric">{it.numero_item ?? idx + 1}</td>
                    <td className="max-w-[14rem]">
                      {it.descricao_xml || it.produto_nome || `Produto #${it.produto_id}`}
                    </td>
                    <td>
                      {editavel ? (
                        <input
                          className="erp-input w-[5.5rem] font-mono text-xs px-1 py-0.5"
                          value={it.ncm || ''}
                          maxLength={8}
                          onChange={(e) =>
                            atualizarItem(it.id, { ncm: e.target.value.replace(/\D/g, '').slice(0, 8) })
                          }
                        />
                      ) : (
                        <span className="font-mono">{it.ncm || '—'}</span>
                      )}
                    </td>
                    <td>
                      {editavel ? (
                        <input
                          className="erp-input w-[4.5rem] font-mono text-xs px-1 py-0.5 font-semibold"
                          value={it.cfop || ''}
                          maxLength={4}
                          onChange={(e) =>
                            atualizarItem(it.id, { cfop: e.target.value.replace(/\D/g, '').slice(0, 4) })
                          }
                          aria-label={`CFOP item ${it.numero_item ?? idx + 1}`}
                        />
                      ) : (
                        <span className="font-mono font-semibold">{it.cfop || '—'}</span>
                      )}
                    </td>
                    <td className="font-mono">{cstIcms(it.impostos_json)}</td>
                    <td>
                      {editavel ? (
                        <input
                          className="erp-input w-12 font-mono text-xs px-1 py-0.5"
                          value={it.unidade || ''}
                          maxLength={6}
                          onChange={(e) => atualizarItem(it.id, { unidade: e.target.value.slice(0, 6) })}
                        />
                      ) : (
                        it.unidade || '—'
                      )}
                    </td>
                    <td className="text-right nexus-numeric whitespace-nowrap">
                      {formatQuantityBR(Number(it.quantidade))}
                    </td>
                    <td className="text-right nexus-numeric whitespace-nowrap">
                      {formatMoneyBRL(Number(it.valor))}
                    </td>
                    <td className="text-right nexus-numeric whitespace-nowrap">
                      {formatMoneyBRL(Number(it.quantidade) * Number(it.valor))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editavel ? (
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-3">
          <button
            type="button"
            className="erp-btn-primary erp-btn-sm inline-flex items-center gap-1.5"
            disabled={!dirty || saving}
            onClick={() => void salvar()}
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {saving ? 'Salvando…' : 'Salvar dados fiscais'}
          </button>
        </div>
      ) : null}
    </div>
  );
}
