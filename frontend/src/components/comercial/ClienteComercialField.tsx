import { useCallback } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { labelClienteSelecionado } from '@/lib/comercialAutocomplete';
import { formatCnpjDisplay } from '@/lib/cnpj';
import { clientesService } from '@/services/api/clientes';
import type { Cliente } from '@/types';

export type ClienteComercialFieldProps = {
  valueId: number | null;
  selectedCliente: Cliente | null;
  disabled?: boolean;
  onSelect: (c: Cliente) => void;
  onClear: () => void;
};

/** Seleção de cliente comercial — autocomplete estável (cadastro rápido suspenso na 4.0.13.6.1). */
export function ClienteComercialField({
  valueId,
  selectedCliente,
  disabled,
  onSelect,
  onClear,
}: ClienteComercialFieldProps) {
  const buscar = useCallback((term: string, limit?: number) => clientesService.search(term, limit ?? 25), []);

  return (
    <AsyncAutocomplete<Cliente>
      wrapClassName="w-full"
      value={valueId}
      selectedOption={selectedCliente}
      placeholder="Buscar cliente por nome, razão social ou documento..."
      disabled={disabled}
      minChars={2}
      limit={25}
      search={buscar}
      getOptionValue={(c) => c.id}
      getOptionLabel={labelClienteSelecionado}
      renderOption={(c) => {
        const doc = (c.cnpj || '').trim();
        return (
          <div>
            <div className="font-medium leading-snug">{c.razao_social}</div>
            {(c.nome_fantasia || '').trim() ? (
              <div className="text-xs text-muted-foreground">{c.nome_fantasia}</div>
            ) : null}
            {doc ? (
              <div className="text-xs text-muted-foreground tabular-nums">{formatCnpjDisplay(doc)}</div>
            ) : null}
          </div>
        );
      }}
      onChange={(id, opt) => {
        if (id == null || !opt) {
          onClear();
          return;
        }
        onSelect(opt);
      }}
    />
  );
}
