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

type ImpostoBloco = {
  cst?: string;
  orig?: string;
  base?: string | number | null;
  aliquota?: string | number | null;
  valor?: string | number | null;
};

type ImpostosShape = {
  icms?: ImpostoBloco;
  pis?: ImpostoBloco;
  cofins?: ImpostoBloco;
  ipi?: ImpostoBloco;
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

function podeEditarItens(nfe: NFeEntrada): boolean {
  const st = (nfe.status_emissao_sefaz || '').toUpperCase();
  if (st.includes('AUTORIZADA')) return false;
  return (nfe.status_operacional || '').toUpperCase() === 'RASCUNHO';
}

function asImpostos(raw?: Record<string, unknown> | null): ImpostosShape {
  if (!raw || typeof raw !== 'object') {
    return { icms: {}, pis: {}, cofins: {} };
  }
  const bloco = (key: keyof ImpostosShape): ImpostoBloco => {
    const v = raw[key];
    return v && typeof v === 'object' ? { ...(v as ImpostoBloco) } : {};
  };
  return {
    icms: bloco('icms'),
    pis: bloco('pis'),
    cofins: bloco('cofins'),
    ipi: bloco('ipi'),
  };
}

function fmtNum(val: unknown): string {
  if (val === null || val === undefined || val === '') return '—';
  const n = Number(String(val).replace(',', '.'));
  if (!Number.isFinite(n)) return String(val);
  return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function strCampo(val: unknown): string {
  if (val === null || val === undefined) return '';
  return String(val);
}

function impostosIguais(a?: Record<string, unknown> | null, b?: Record<string, unknown> | null): boolean {
  return JSON.stringify(asImpostos(a)) === JSON.stringify(asImpostos(b));
}

function CampoImposto({
  label,
  value,
  editavel,
  onChange,
  mono,
  wide,
}: {
  label: string;
  value: string;
  editavel: boolean;
  onChange?: (v: string) => void;
  mono?: boolean;
  wide?: boolean;
}) {
  return (
    <div className={wide ? 'min-w-[5.5rem]' : 'min-w-[4.5rem]'}>
      <label className="text-[10px] text-muted-foreground block mb-0.5">{label}</label>
      {editavel ? (
        <input
          className={`erp-input h-7 text-xs px-1.5 py-0.5 w-full ${mono ? 'font-mono' : ''}`}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
        />
      ) : (
        <p className={`text-xs ${mono ? 'font-mono' : ''} tabular-nums`}>{value || '—'}</p>
      )}
    </div>
  );
}

function BlocoImposto({
  titulo,
  bloco,
  editavel,
  comOrigem,
  onChange,
}: {
  titulo: string;
  bloco: ImpostoBloco;
  editavel: boolean;
  comOrigem?: boolean;
  onChange: (patch: Partial<ImpostoBloco>) => void;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-2.5 space-y-2">
      <p className="text-[11px] font-semibold tracking-wide uppercase text-muted-foreground">{titulo}</p>
      <div className="flex flex-wrap gap-2">
        <CampoImposto
          label="CST"
          value={strCampo(bloco.cst)}
          editavel={editavel}
          mono
          onChange={(v) => onChange({ cst: v.replace(/\D/g, '').slice(0, 3) })}
        />
        {comOrigem ? (
          <CampoImposto
            label="Orig"
            value={strCampo(bloco.orig)}
            editavel={editavel}
            mono
            onChange={(v) => onChange({ orig: v.replace(/\D/g, '').slice(0, 1) })}
          />
        ) : null}
        <CampoImposto
          label="Base"
          value={editavel ? strCampo(bloco.base) : fmtNum(bloco.base)}
          editavel={editavel}
          wide
          onChange={(v) => onChange({ base: v })}
        />
        <CampoImposto
          label="Alíq. %"
          value={editavel ? strCampo(bloco.aliquota) : fmtNum(bloco.aliquota)}
          editavel={editavel}
          onChange={(v) => onChange({ aliquota: v })}
        />
        <CampoImposto
          label="Valor"
          value={editavel ? strCampo(bloco.valor) : fmtNum(bloco.valor)}
          editavel={editavel}
          wide
          onChange={(v) => onChange({ valor: v })}
        />
      </div>
    </div>
  );
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
        (it.unidade || '') !== (o.unidade || '') ||
        Number(it.quantidade) !== Number(o.quantidade) ||
        Number(it.valor) !== Number(o.valor) ||
        !impostosIguais(it.impostos_json, o.impostos_json)
      );
    });
  }, [editavel, finDraft, natDraft, chaveRefDraft, itensDraft, nfe]);

  const atualizarItem = (id: number, patch: Partial<ItemNFe>) => {
    setItensDraft((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));
  };

  const atualizarImposto = (
    itemId: number,
    grupo: keyof ImpostosShape,
    patch: Partial<ImpostoBloco>,
  ) => {
    setItensDraft((prev) =>
      prev.map((it) => {
        if (it.id !== itemId) return it;
        const atual = asImpostos(it.impostos_json);
        const next: ImpostosShape = {
          ...atual,
          [grupo]: { ...(atual[grupo] || {}), ...patch },
        };
        return { ...it, impostos_json: next as Record<string, unknown> };
      }),
    );
  };

  const salvar = async () => {
    if (!editavel) return;
    for (const it of itensDraft) {
      const nItem = it.numero_item ?? it.id;
      if (!(it.cfop || '').trim()) {
        toast.error(`Informe o CFOP do item ${nItem}.`);
        return;
      }
      if (!(it.ncm || '').trim()) {
        toast.error(`Informe o NCM do item ${nItem}.`);
        return;
      }
      const imp = asImpostos(it.impostos_json);
      if (!(imp.icms?.cst || '').trim()) {
        toast.error(`Informe o CST ICMS do item ${nItem}.`);
        return;
      }
      if (!(imp.pis?.cst || '').trim()) {
        toast.error(`Informe o CST PIS do item ${nItem}.`);
        return;
      }
      if (!(imp.cofins?.cst || '').trim()) {
        toast.error(`Informe o CST COFINS do item ${nItem}.`);
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
          Confira finalidade, natureza, chave referenciada, CFOP/NCM e impostos (ICMS, PIS, COFINS)
          de cada item — é o que vai no XML para a SEFAZ.
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

      <div className="space-y-3">
        <p className="text-xs font-medium text-muted-foreground">
          Itens ({itensDraft.length}) — identificação, CFOP e impostos
        </p>
        {itensDraft.length === 0 ? (
          <p className="text-sm text-destructive">Nenhum item na entrada própria. Não emita sem itens.</p>
        ) : (
          itensDraft.map((it, idx) => {
            const imp = asImpostos(it.impostos_json);
            const nItem = it.numero_item ?? idx + 1;
            return (
              <div key={it.id} className="border border-border rounded-lg p-3 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-xs text-muted-foreground">Item {nItem}</p>
                    <p className="text-sm font-medium">
                      {it.descricao_xml || it.produto_nome || `Produto #${it.produto_id}`}
                    </p>
                  </div>
                  <p className="text-xs tabular-nums text-muted-foreground">
                    {formatQuantityBR(Number(it.quantidade))} × {formatMoneyBRL(Number(it.valor))} ={' '}
                    <span className="font-semibold text-foreground">
                      {formatMoneyBRL(Number(it.quantidade) * Number(it.valor))}
                    </span>
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <CampoImposto
                    label="NCM"
                    value={it.ncm || ''}
                    editavel={editavel}
                    mono
                    wide
                    onChange={(v) => atualizarItem(it.id, { ncm: v.replace(/\D/g, '').slice(0, 8) })}
                  />
                  <CampoImposto
                    label="CFOP"
                    value={it.cfop || ''}
                    editavel={editavel}
                    mono
                    onChange={(v) => atualizarItem(it.id, { cfop: v.replace(/\D/g, '').slice(0, 4) })}
                  />
                  <CampoImposto
                    label="Un."
                    value={it.unidade || ''}
                    editavel={editavel}
                    mono
                    onChange={(v) => atualizarItem(it.id, { unidade: v.slice(0, 6) })}
                  />
                  <CampoImposto
                    label="Qtd"
                    value={strCampo(it.quantidade)}
                    editavel={editavel}
                    onChange={(v) => atualizarItem(it.id, { quantidade: Number(v.replace(',', '.')) || 0 })}
                  />
                  <CampoImposto
                    label="V. unit."
                    value={strCampo(it.valor)}
                    editavel={editavel}
                    wide
                    onChange={(v) => atualizarItem(it.id, { valor: Number(v.replace(',', '.')) || 0 })}
                  />
                </div>

                <div className="grid gap-2 md:grid-cols-3">
                  <BlocoImposto
                    titulo="ICMS"
                    bloco={imp.icms || {}}
                    editavel={editavel}
                    comOrigem
                    onChange={(patch) => atualizarImposto(it.id, 'icms', patch)}
                  />
                  <BlocoImposto
                    titulo="PIS"
                    bloco={imp.pis || {}}
                    editavel={editavel}
                    onChange={(patch) => atualizarImposto(it.id, 'pis', patch)}
                  />
                  <BlocoImposto
                    titulo="COFINS"
                    bloco={imp.cofins || {}}
                    editavel={editavel}
                    onChange={(patch) => atualizarImposto(it.id, 'cofins', patch)}
                  />
                </div>

                {(imp.ipi?.cst || imp.ipi?.base || imp.ipi?.valor || editavel) && (
                  <BlocoImposto
                    titulo="IPI (se houver)"
                    bloco={imp.ipi || {}}
                    editavel={editavel}
                    onChange={(patch) => atualizarImposto(it.id, 'ipi', patch)}
                  />
                )}
              </div>
            );
          })
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
