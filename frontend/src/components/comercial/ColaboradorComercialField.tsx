import { useCallback } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { labelColaboradorSelecionado } from '@/lib/comercialAutocomplete';
import { colaboradoresService } from '@/services/api/colaboradores';
import type { Colaborador, ColaboradorFuncao } from '@/types';

export type ColaboradorComercialFieldProps = {
  funcao: ColaboradorFuncao;
  valueId: number | null;
  selectedColaborador: Colaborador | null;
  disabled?: boolean;
  placeholder?: string;
  onSelect: (c: Colaborador) => void;
  onClear: () => void;
};

export function ColaboradorComercialField({
  funcao,
  valueId,
  selectedColaborador,
  disabled,
  placeholder,
  onSelect,
  onClear,
}: ColaboradorComercialFieldProps) {
  const buscar = useCallback(
    (term: string, limit?: number) => colaboradoresService.search(term, { limit: limit ?? 25, funcao }),
    [funcao],
  );

  return (
    <AsyncAutocomplete<Colaborador>
      wrapClassName="w-full"
      value={valueId}
      selectedOption={selectedColaborador}
      placeholder={placeholder ?? 'Buscar colaborador...'}
      disabled={disabled}
      minChars={1}
      limit={25}
      search={buscar}
      getOptionValue={(c) => c.id}
      getOptionLabel={labelColaboradorSelecionado}
      renderOption={(c) => (
        <div>
          <div className="font-medium leading-snug">{c.nome}</div>
          {(c.codigo || '').trim() ? (
            <div className="text-xs text-muted-foreground">Código: {c.codigo}</div>
          ) : null}
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
  );
}
