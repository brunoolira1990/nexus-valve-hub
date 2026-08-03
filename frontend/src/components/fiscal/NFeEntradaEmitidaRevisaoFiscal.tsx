import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
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
  _meta?: Record<string, unknown>;
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
    if (key === '_meta') return {};
    const v = raw[key];
    return v && typeof v === 'object' ? { ...(v as ImpostoBloco) } : {};
  };
  const meta = raw._meta;
  return {
    icms: bloco('icms'),
    pis: bloco('pis'),
    cofins: bloco('cofins'),
    ipi: bloco('ipi'),
    _meta: meta && typeof meta === 'object' ? { ...(meta as Record<string, unknown>) } : undefined,
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

function regraDoItem(it: ItemNFe): string {
  const meta = asImpostos(it.impostos_json)._meta;
  const nome = meta?.regra_nome;
  return nome ? String(nome) : '';
}

function itemIncompleto(it: ItemNFe): boolean {
  const imp = asImpostos(it.impostos_json);
  return (
    !(it.cfop || '').trim() ||
    !(imp.icms?.cst || '').trim() ||
    !(imp.pis?.cst || '').trim() ||
    !(imp.cofins?.cst || '').trim()
  );
}

function impostosIguais(a?: Record<string, unknown> | null, b?: Record<string, unknown> | null): boolean {
  const strip = (raw?: Record<string, unknown> | null) => {
    const i = asImpostos(raw);
    return { icms: i.icms, pis: i.pis, cofins: i.cofins, ipi: i.ipi };
  };
  return JSON.stringify(strip(a)) === JSON.stringify(strip(b));
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
  const isDevolucao = (nfe.fin_nfe || '').trim() === '4';
  const [itensDraft, setItensDraft] = useState<ItemNFe[]>(nfe.itens || []);
  const [finDraft, setFinDraft] = useState(nfe.fin_nfe || '');
  const [natDraft, setNatDraft] = useState(nfe.nat_op || '');
  const [chaveRefDraft, setChaveRefDraft] = useState(nfe.chave_nfe_referenciada || '');
  const [saving, setSaving] = useState(false);
  const [aplicandoRegra, setAplicandoRegra] = useState(false);
  const [expandidos, setExpandidos] = useState<Set<number>>(() => new Set());

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
    if (grupo === '_meta') return;
    setItensDraft((prev) =>
      prev.map((it) => {
        if (it.id !== itemId) return it;
        const raw = (it.impostos_json || {}) as Record<string, unknown>;
        const atual = asImpostos(raw);
        const next: Record<string, unknown> = {
          ...raw,
          icms: atual.icms || {},
          pis: atual.pis || {},
          cofins: atual.cofins || {},
          [grupo]: { ...(atual[grupo] || {}), ...patch },
        };
        if (atual.ipi) next.ipi = atual.ipi;
        if (atual._meta) next._meta = atual._meta;
        return { ...it, impostos_json: next };
      }),
    );
  };

  const toggleExpand = (id: number) => {
    setExpandidos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const aplicarRegras = async () => {
    if (!editavel || dirty) {
      if (dirty) toast.error('Salve ou descarte as alterações manuais antes de aplicar a regra.');
      return;
    }
    setAplicandoRegra(true);
    try {
      const res = await nfeEntradasService.aplicarRegrasDevolucao(nfe.id);
      if (!res.ok) {
        toast.error(res.mensagem || res.detail || 'Não foi possível aplicar as regras fiscais.');
        return;
      }
      toast.success(res.mensagem || 'Regras fiscais aplicadas.');
      await onAtualizado();
    } catch (e) {
      toast.error(apiErrorMessage(e, { fallback: 'Não foi possível aplicar as regras fiscais.' }));
    } finally {
      setAplicandoRegra(false);
    }
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Revisão fiscal (antes da emissão)</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Resumo por item. Expanda só o que precisar ajustar (exceção). Em devolução, use a regra
            fiscal <span className="font-medium text-foreground">DEVOLUCAO_VENDA</span>.
          </p>
        </div>
        {editavel && isDevolucao ? (
          <button
            type="button"
            className="erp-btn-secondary erp-btn-sm inline-flex items-center gap-1.5"
            disabled={aplicandoRegra || dirty}
            onClick={() => void aplicarRegras()}
            title={dirty ? 'Salve as alterações manuais antes' : 'Reaplica CFOP/impostos pela regra fiscal'}
          >
            {aplicandoRegra ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {aplicandoRegra ? 'Aplicando…' : 'Aplicar regra fiscal'}
          </button>
        ) : null}
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

      <div className="space-y-2">
        <p className="text-xs font-medium text-muted-foreground">Itens ({itensDraft.length})</p>
        {itensDraft.length === 0 ? (
          <p className="text-sm text-destructive">Nenhum item na entrada própria. Não emita sem itens.</p>
        ) : (
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr className="text-left">
                  <th className="px-2 py-1.5 w-8" />
                  <th className="px-2 py-1.5 font-medium">#</th>
                  <th className="px-2 py-1.5 font-medium">Produto</th>
                  <th className="px-2 py-1.5 font-medium font-mono">CFOP</th>
                  <th className="px-2 py-1.5 font-medium font-mono">NCM</th>
                  <th className="px-2 py-1.5 font-medium">ICMS</th>
                  <th className="px-2 py-1.5 font-medium">PIS</th>
                  <th className="px-2 py-1.5 font-medium">COFINS</th>
                  <th className="px-2 py-1.5 font-medium">Regra</th>
                  <th className="px-2 py-1.5 font-medium text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {itensDraft.map((it, idx) => {
                  const imp = asImpostos(it.impostos_json);
                  const nItem = it.numero_item ?? idx + 1;
                  const aberto = expandidos.has(it.id);
                  const incompleto = itemIncompleto(it);
                  const regra = regraDoItem(it);
                  return (
                    <FragmentRow
                      key={it.id}
                      it={it}
                      nItem={nItem}
                      aberto={aberto}
                      incompleto={incompleto}
                      regra={regra}
                      imp={imp}
                      editavel={editavel}
                      onToggle={() => toggleExpand(it.id)}
                      onAtualizarItem={atualizarItem}
                      onAtualizarImposto={atualizarImposto}
                    />
                  );
                })}
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

function FragmentRow({
  it,
  nItem,
  aberto,
  incompleto,
  regra,
  imp,
  editavel,
  onToggle,
  onAtualizarItem,
  onAtualizarImposto,
}: {
  it: ItemNFe;
  nItem: number;
  aberto: boolean;
  incompleto: boolean;
  regra: string;
  imp: ImpostosShape;
  editavel: boolean;
  onToggle: () => void;
  onAtualizarItem: (id: number, patch: Partial<ItemNFe>) => void;
  onAtualizarImposto: (itemId: number, grupo: keyof ImpostosShape, patch: Partial<ImpostoBloco>) => void;
}) {
  return (
    <>
      <tr
        className={`border-t border-border ${incompleto ? 'bg-destructive/5' : 'hover:bg-muted/20'}`}
      >
        <td className="px-1 py-1.5">
          <button
            type="button"
            className="p-1 text-muted-foreground hover:text-foreground"
            onClick={onToggle}
            aria-label={aberto ? 'Recolher detalhe' : 'Expandir detalhe'}
          >
            {aberto ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </td>
        <td className="px-2 py-1.5 font-mono tabular-nums">{nItem}</td>
        <td className="px-2 py-1.5 max-w-[12rem] truncate" title={it.descricao_xml || it.produto_nome || ''}>
          {it.descricao_xml || it.produto_nome || `#${it.produto_id}`}
          {incompleto ? (
            <span className="ml-1 text-destructive">· pendente</span>
          ) : null}
        </td>
        <td className="px-2 py-1.5 font-mono">{it.cfop || '—'}</td>
        <td className="px-2 py-1.5 font-mono">{it.ncm || '—'}</td>
        <td className="px-2 py-1.5 font-mono">{imp.icms?.cst || '—'}</td>
        <td className="px-2 py-1.5 font-mono">{imp.pis?.cst || '—'}</td>
        <td className="px-2 py-1.5 font-mono">{imp.cofins?.cst || '—'}</td>
        <td className="px-2 py-1.5 text-muted-foreground max-w-[8rem] truncate" title={regra || 'Fallback'}>
          {regra || '—'}
        </td>
        <td className="px-2 py-1.5 text-right tabular-nums">
          {formatMoneyBRL(Number(it.quantidade) * Number(it.valor))}
        </td>
      </tr>
      {aberto ? (
        <tr className="border-t border-border bg-muted/10">
          <td colSpan={10} className="px-3 py-3">
            <div className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-sm font-medium">
                  {it.descricao_xml || it.produto_nome || `Produto #${it.produto_id}`}
                </p>
                <p className="text-xs tabular-nums text-muted-foreground">
                  {formatQuantityBR(Number(it.quantidade))} × {formatMoneyBRL(Number(it.valor))}
                </p>
              </div>
              {regra ? (
                <p className="text-[11px] text-muted-foreground">
                  Regra aplicada: <span className="text-foreground font-medium">{regra}</span>
                </p>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  Sem regra DEVOLUCAO_VENDA — CFOP/impostos por convenção ou espelho da saída.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <CampoImposto
                  label="NCM"
                  value={it.ncm || ''}
                  editavel={editavel}
                  mono
                  wide
                  onChange={(v) => onAtualizarItem(it.id, { ncm: v.replace(/\D/g, '').slice(0, 8) })}
                />
                <CampoImposto
                  label="CFOP"
                  value={it.cfop || ''}
                  editavel={editavel}
                  mono
                  onChange={(v) => onAtualizarItem(it.id, { cfop: v.replace(/\D/g, '').slice(0, 4) })}
                />
                <CampoImposto
                  label="Un."
                  value={it.unidade || ''}
                  editavel={editavel}
                  mono
                  onChange={(v) => onAtualizarItem(it.id, { unidade: v.slice(0, 6) })}
                />
                <CampoImposto
                  label="Qtd"
                  value={strCampo(it.quantidade)}
                  editavel={editavel}
                  onChange={(v) =>
                    onAtualizarItem(it.id, { quantidade: Number(v.replace(',', '.')) || 0 })
                  }
                />
                <CampoImposto
                  label="V. unit."
                  value={strCampo(it.valor)}
                  editavel={editavel}
                  wide
                  onChange={(v) => onAtualizarItem(it.id, { valor: Number(v.replace(',', '.')) || 0 })}
                />
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                <BlocoImposto
                  titulo="ICMS"
                  bloco={imp.icms || {}}
                  editavel={editavel}
                  comOrigem
                  onChange={(patch) => onAtualizarImposto(it.id, 'icms', patch)}
                />
                <BlocoImposto
                  titulo="PIS"
                  bloco={imp.pis || {}}
                  editavel={editavel}
                  onChange={(patch) => onAtualizarImposto(it.id, 'pis', patch)}
                />
                <BlocoImposto
                  titulo="COFINS"
                  bloco={imp.cofins || {}}
                  editavel={editavel}
                  onChange={(patch) => onAtualizarImposto(it.id, 'cofins', patch)}
                />
              </div>
              {(imp.ipi?.cst || imp.ipi?.base || imp.ipi?.valor || editavel) && (
                <BlocoImposto
                  titulo="IPI (se houver)"
                  bloco={imp.ipi || {}}
                  editavel={editavel}
                  onChange={(patch) => onAtualizarImposto(it.id, 'ipi', patch)}
                />
              )}
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
