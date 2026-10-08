import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { labelFornecedorSelecionado } from '@/lib/comercialAutocomplete';
import { formatCnpjDisplay } from '@/lib/cnpj';
import { PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO } from '@/lib/financeiroUi';
import { fornecedoresService } from '@/services/api/fornecedores';
import type { Fornecedor } from '@/types';

export type FornecedorSearchSelectProps = {
  valueId: number | null;
  selectedFornecedor: Fornecedor | null;
  disabled?: boolean;
  required?: boolean;
  error?: string | null;
  helperText?: string;
  onSelect: (f: Fornecedor) => void;
  onClear: () => void;
};

/** Busca de fornecedor padronizada — Financeiro e demais fluxos operacionais. */
export function FornecedorSearchSelect({
  valueId,
  selectedFornecedor,
  disabled,
  error,
  helperText,
  onSelect,
  onClear,
}: FornecedorSearchSelectProps) {
  const buscar = useCallback((term: string, limit?: number) => fornecedoresService.search(term, limit ?? 25), []);

  return (
    <div className="space-y-1">
      <AsyncAutocomplete<Fornecedor>
        wrapClassName="w-full"
        value={valueId}
        selectedOption={selectedFornecedor}
        placeholder={PLACEHOLDER_BUSCA_FORNECEDOR_FINANCEIRO}
        disabled={disabled}
        minChars={2}
        limit={25}
        emptyMessage="Nenhum fornecedor encontrado."
        search={buscar}
        getOptionValue={(f) => f.id}
        getOptionLabel={labelFornecedorSelecionado}
        inputClassName={`erp-input mt-1 w-full${error ? ' border-destructive' : ''}`}
        renderOption={(f) => {
          const fantasia = (f.nome_fantasia || '').trim();
          const cnpj = (f.cnpj || '').trim();
          return (
            <div>
              <div className="font-medium leading-snug">{f.razao_social}</div>
              {fantasia && fantasia !== (f.razao_social || '').trim() ? (
                <div className="text-xs text-muted-foreground">{fantasia}</div>
              ) : null}
              {cnpj ? (
                <div className="text-xs text-muted-foreground tabular-nums">{formatCnpjDisplay(cnpj)}</div>
              ) : null}
            </div>
          );
        }}
        renderListFooter={() => (
          <div className="px-2 py-2">
            <Link
              to="/fornecedores"
              className="block rounded-md border border-dashed border-primary/40 bg-primary/5 px-2 py-2 text-sm font-medium text-primary hover:bg-primary/10"
              target="_blank"
              rel="noopener noreferrer"
            >
              Cadastrar novo fornecedor
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
