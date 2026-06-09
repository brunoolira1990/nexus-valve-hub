import { useCallback } from 'react';
import { AsyncAutocomplete } from '@/components/ui/AsyncAutocomplete';
import { ncmExibicaoProduto, tituloProdutoLinha } from '@/lib/comercialAutocomplete';
import { produtosService } from '@/services/api/produtos';
import type { Produto } from '@/types';

export type ProdutoComercialFieldProps = {
  valueId: number | null;
  selectedProduto: Produto | null;
  disabled?: boolean;
  compact?: boolean;
  onSelect: (p: Produto) => void;
  onClear: () => void;
};

/** Seleção de produto comercial — autocomplete estável (cadastro rápido suspenso na 4.0.13.6.1). */
export function ProdutoComercialField({
  valueId,
  selectedProduto,
  disabled,
  compact = false,
  onSelect,
  onClear,
}: ProdutoComercialFieldProps) {
  const buscar = useCallback((term: string, limit?: number) => produtosService.search(term, limit ?? 50), []);

  return (
    <AsyncAutocomplete<Produto>
      wrapClassName="w-full"
      value={valueId}
      selectedOption={selectedProduto}
      placeholder="Buscar produto por código ou descrição..."
      disabled={disabled}
      minChars={1}
      limit={50}
      search={buscar}
      getOptionValue={(p) => p.id}
      getOptionLabel={(p) => tituloProdutoLinha(p)}
      inputClassName={compact ? 'erp-input h-9 text-sm mt-1' : 'erp-input mt-1'}
      listBoxClassName="absolute z-50 mt-1 max-h-80 min-w-[min(100vw-2rem,36rem)] w-max max-w-[min(100vw-2rem,48rem)] overflow-auto rounded-md border border-border bg-background shadow"
      renderOption={(p) => (
        <div className="space-y-0.5 py-0.5 text-left">
          <div className="font-medium text-foreground break-words">{(p.codigo_completo || '').trim() || '—'}</div>
          <div className="text-muted-foreground break-words">{p.descricao}</div>
          <div className="text-xs text-muted-foreground">
            Un.: {(p.unidade_efetiva || p.unidade || '—').toUpperCase()} · NCM: {ncmExibicaoProduto(p)}
          </div>
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
