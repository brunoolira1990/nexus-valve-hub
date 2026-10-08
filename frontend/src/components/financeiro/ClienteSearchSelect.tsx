import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { labelClienteSelecionado } from '@/lib/comercialAutocomplete';
import { formatCnpjDisplay } from '@/lib/cnpj';
import { PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO } from '@/lib/financeiroUi';
import { clientesService } from '@/services/api/clientes';
import type { Cliente } from '@/types';

export type ClienteSearchSelectProps = {
  valueId: number | null;
  selectedCliente: Cliente | null;
  disabled?: boolean;
  error?: string | null;
  helperText?: string;
  onSelect: (c: Cliente) => void;
  onClear: () => void;
};

function formatDocumentoCliente(doc: string): string {
  const digits = doc.replace(/\D/g, '');
  if (digits.length === 11) {
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
  }
  return formatCnpjDisplay(doc);
}

/** Busca de cliente padronizada — Financeiro e demais fluxos operacionais. */
export function ClienteSearchSelect({
  valueId,
  selectedCliente,
  disabled,
  error,
  helperText,
  onSelect,
  onClear,
}: ClienteSearchSelectProps) {
  const buscar = useCallback((term: string, limit?: number) => clientesService.search(term, limit ?? 25), []);

  return (
    <div className="space-y-1">
      <AsyncAutocomplete<Cliente>
        wrapClassName="w-full"
        value={valueId}
        selectedOption={selectedCliente}
        placeholder={PLACEHOLDER_BUSCA_CLIENTE_FINANCEIRO}
        disabled={disabled}
        minChars={2}
        limit={25}
        emptyMessage="Nenhum cliente encontrado."
        search={buscar}
        getOptionValue={(c) => c.id}
        getOptionLabel={labelClienteSelecionado}
        inputClassName={`erp-input mt-1 w-full${error ? ' border-destructive' : ''}`}
        renderOption={(c) => {
          const fantasia = (c.nome_fantasia || '').trim();
          const doc = (c.cnpj || '').trim();
          return (
            <div>
              <div className="font-medium leading-snug">{c.razao_social}</div>
              {fantasia && fantasia !== (c.razao_social || '').trim() ? (
                <div className="text-xs text-muted-foreground">{fantasia}</div>
              ) : null}
              {doc ? (
                <div className="text-xs text-muted-foreground tabular-nums">{formatDocumentoCliente(doc)}</div>
              ) : null}
            </div>
          );
        }}
        renderListFooter={() => (
          <div className="px-2 py-2">
            <Link
              to="/clientes"
              className="block rounded-md border border-dashed border-primary/40 bg-primary/5 px-2 py-2 text-sm font-medium text-primary hover:bg-primary/10"
              target="_blank"
              rel="noopener noreferrer"
            >
              Cadastrar novo cliente
            </Link>
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
      {helperText ? <p className="text-xs text-muted-foreground">{helperText}</p> : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
