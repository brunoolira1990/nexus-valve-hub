import { useCallback, useState } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { Modal } from '@/components/Modal';
import { apiErrorMessage } from '@/services/api/config';
import { transportadorasService } from '@/services/api/transportadoras';
import { formatCnpjDisplay } from '@/lib/cnpj';
import {
  labelTransportadoraSelecionada,
  transportadoraStub,
} from '@/lib/nfeSaidaConferenciaUx';
import type { Transportadora } from '@/types';

type QuickForm = {
  razao_social: string;
  cnpj: string;
  ie: string;
  telefone: string;
  email: string;
  cidade: string;
  uf: string;
  observacoes: string;
};

const emptyQuick = (): QuickForm => ({
  razao_social: '',
  cnpj: '',
  ie: '',
  telefone: '',
  email: '',
  cidade: '',
  uf: '',
  observacoes: '',
});

function digitsOnly(s: string): string {
  return (s || '').replace(/\D/g, '');
}

function quickToPayload(q: QuickForm): Omit<Transportadora, 'id'> {
  const doc = digitsOnly(q.cnpj);
  const cnpj =
    doc.length >= 11
      ? doc
      : `9${String(Date.now()).slice(-13).padStart(13, '0')}`;
  return {
    ...transportadoraStub(0, q.razao_social.trim(), cnpj),
    nome_fantasia: '',
    ie: q.ie.trim(),
    telefone: q.telefone.trim(),
    email: q.email.trim(),
    cidade: q.cidade.trim(),
    uf: q.uf.trim().toUpperCase().slice(0, 2),
    observacoes: q.observacoes.trim(),
    ativo: true,
  };
}

export type TransportadoraNFeFieldProps = {
  valueId: number | null;
  selected: Transportadora | null;
  disabled?: boolean;
  onSelect: (t: Transportadora) => void;
  onClear: () => void;
};

export function TransportadoraNFeField({
  valueId,
  selected,
  disabled,
  onSelect,
  onClear,
}: TransportadoraNFeFieldProps) {
  const [quickOpen, setQuickOpen] = useState(false);
  const [quick, setQuick] = useState<QuickForm>(emptyQuick);
  const [quickSaving, setQuickSaving] = useState(false);
  const [quickError, setQuickError] = useState<string | null>(null);

  const buscar = useCallback(
    (term: string, limit?: number) => transportadorasService.search(term, limit ?? 25),
    [],
  );

  const abrirCadastro = (prefill?: string) => {
    setQuick({ ...emptyQuick(), razao_social: prefill || '' });
    setQuickError(null);
    setQuickOpen(true);
  };

  const salvarQuick = async () => {
    if (!quick.razao_social.trim()) {
      setQuickError('Informe a razão social.');
      return;
    }
    setQuickSaving(true);
    setQuickError(null);
    try {
      const created = await transportadorasService.create(quickToPayload(quick));
      onSelect(created);
      setQuickOpen(false);
      setQuick(emptyQuick());
    } catch (err) {
      setQuickError(apiErrorMessage(err));
    } finally {
      setQuickSaving(false);
    }
  };

  return (
    <>
      <AsyncAutocomplete<Transportadora>
        wrapClassName="w-full"
        value={valueId}
        selectedOption={selected}
        placeholder="Buscar transportadora por nome ou CNPJ…"
        disabled={disabled}
        minChars={2}
        limit={25}
        search={buscar}
        getOptionValue={(t) => t.id}
        getOptionLabel={labelTransportadoraSelecionada}
        listBoxClassName="absolute z-[60] mt-1 max-h-72 w-full min-w-[20rem] overflow-auto rounded-md border border-border bg-background shadow-lg"
        renderOption={(t) => (
          <div>
            <div className="font-medium leading-snug">{(t.razao_social || '').toUpperCase()}</div>
            {(t.cnpj || '').trim() ? (
              <div className="text-xs text-muted-foreground tabular-nums">{formatCnpjDisplay(t.cnpj)}</div>
            ) : null}
            {(t.cidade || t.uf) ? (
              <div className="text-xs text-muted-foreground">
                {[t.cidade, t.uf].filter(Boolean).join(' / ')}
              </div>
            ) : null}
          </div>
        )}
        renderListFooter={({ term, options }) => (
          <div className="px-2 py-2">
            <button
              type="button"
              className="w-full rounded-md border border-dashed border-primary/40 bg-primary/5 px-2 py-2 text-left text-sm font-medium text-primary hover:bg-primary/10"
              disabled={disabled}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => abrirCadastro(term)}
            >
              + Cadastrar nova transportadora
            </button>
          </div>
        )}
        onChange={(id, opt) => {
          if (id == null || !opt) {
            onClear();
            return;
          }
          onSelect(opt);
        }}
      />
      {!disabled ? (
        <button
          type="button"
          className="text-sm font-medium text-primary hover:underline mt-1"
          onClick={() => abrirCadastro()}
        >
          + Cadastrar nova transportadora
        </button>
      ) : null}

      <Modal
        isOpen={quickOpen}
        onClose={() => !quickSaving && setQuickOpen(false)}
        title="Cadastro rápido — Transportadora"
        size="sm"
      >
        <div className="space-y-3 text-sm">
          {quickError ? <p className="text-destructive text-sm">{quickError}</p> : null}
          <div>
            <label className="erp-label">Razão social *</label>
            <input
              className="erp-input mt-1 w-full"
              value={quick.razao_social}
              onChange={(e) => setQuick((p) => ({ ...p, razao_social: e.target.value }))}
              disabled={quickSaving}
            />
          </div>
          <div>
            <label className="erp-label">CNPJ (recomendado)</label>
            <input
              className="erp-input mt-1 w-full"
              value={quick.cnpj}
              onChange={(e) => setQuick((p) => ({ ...p, cnpj: e.target.value }))}
              disabled={quickSaving}
              placeholder="Opcional — gerado internamente se vazio"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="erp-label">IE</label>
              <input className="erp-input mt-1 w-full" value={quick.ie} onChange={(e) => setQuick((p) => ({ ...p, ie: e.target.value }))} disabled={quickSaving} />
            </div>
            <div>
              <label className="erp-label">Telefone</label>
              <input className="erp-input mt-1 w-full" value={quick.telefone} onChange={(e) => setQuick((p) => ({ ...p, telefone: e.target.value }))} disabled={quickSaving} />
            </div>
          </div>
          <div>
            <label className="erp-label">E-mail</label>
            <input className="erp-input mt-1 w-full" value={quick.email} onChange={(e) => setQuick((p) => ({ ...p, email: e.target.value }))} disabled={quickSaving} />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <label className="erp-label">Cidade</label>
              <input className="erp-input mt-1 w-full" value={quick.cidade} onChange={(e) => setQuick((p) => ({ ...p, cidade: e.target.value }))} disabled={quickSaving} />
            </div>
            <div>
              <label className="erp-label">UF</label>
              <input className="erp-input mt-1 w-full" maxLength={2} value={quick.uf} onChange={(e) => setQuick((p) => ({ ...p, uf: e.target.value }))} disabled={quickSaving} />
            </div>
          </div>
          <div>
            <label className="erp-label">Observações</label>
            <textarea className="erp-input mt-1 w-full min-h-[56px]" value={quick.observacoes} onChange={(e) => setQuick((p) => ({ ...p, observacoes: e.target.value }))} disabled={quickSaving} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="erp-btn-outline" disabled={quickSaving} onClick={() => setQuickOpen(false)}>
              Cancelar
            </button>
            <button type="button" className="erp-btn-primary" disabled={quickSaving} onClick={() => void salvarQuick()}>
              {quickSaving ? 'Salvando…' : 'Salvar e usar na NF-e'}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
