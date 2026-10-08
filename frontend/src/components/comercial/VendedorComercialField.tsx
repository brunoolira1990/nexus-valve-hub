import { ColaboradorComercialField } from '@/components/comercial/ColaboradorComercialField';
import { colaboradoresService } from '@/services/api/colaboradores';
import type { Colaborador, Vendedor } from '@/types';

export type VendedorComercialFieldProps = {
  valueId: number | null;
  selectedVendedor: Vendedor | null;
  selectedColaborador?: Colaborador | null;
  disabled?: boolean;
  onSelect: (vendedorId: number, colaborador: Colaborador) => void;
  onClear: () => void;
};

export function VendedorComercialField({
  valueId,
  selectedVendedor,
  selectedColaborador = null,
  disabled,
  onSelect,
  onClear,
}: VendedorComercialFieldProps) {
  const colabDisplay = selectedColaborador ?? null;

  if (!colabDisplay && selectedVendedor) {
    return (
      <div className="flex gap-2 items-center">
        <input
          className="erp-input mt-1 flex-1"
          readOnly
          value={selectedVendedor.nome || selectedVendedor.codigo || `Vendedor #${selectedVendedor.id}`}
          title="Vendedor legado (sem colaborador vinculado)"
        />
        {!disabled ? (
          <button type="button" className="erp-btn-outline erp-btn-sm shrink-0 mt-1" onClick={onClear}>
            Limpar
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <ColaboradorComercialField
      funcao="vendedor"
      valueId={colabDisplay?.id ?? null}
      selectedColaborador={colabDisplay}
      disabled={disabled}
      placeholder="Buscar vendedor..."
      onSelect={async (c) => {
        let vendedorId = c.vendedor_id ?? null;
        let colab = c;
        if (!vendedorId) {
          colab = await colaboradoresService.getById(c.id);
          vendedorId = colab.vendedor_id ?? null;
        }
        if (!vendedorId) return;
        onSelect(vendedorId, colab);
      }}
      onClear={onClear}
    />
  );
}
