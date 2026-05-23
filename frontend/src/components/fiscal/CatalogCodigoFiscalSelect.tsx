import type { OpcaoCatalogo } from '@/lib/catalogosFiscais';
import { OPCAO_VAZIA, opcoesComValorAtual } from '@/lib/catalogosFiscais';

type Props = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  opcoes: OpcaoCatalogo[];
  className?: string;
  allowEmpty?: boolean;
  emptyLabel?: string;
};

export const CatalogCodigoFiscalSelect = ({
  label,
  value,
  onChange,
  opcoes,
  className = 'erp-select mt-1',
  allowEmpty = true,
  emptyLabel,
}: Props) => {
  const lista = opcoesComValorAtual(value, opcoes);
  return (
    <div>
      <label className="erp-label">{label}</label>
      <select className={className} value={value} onChange={(e) => onChange(e.target.value)}>
        {allowEmpty ? (
          <option value="">{emptyLabel ?? OPCAO_VAZIA.label}</option>
        ) : null}
        {lista.map((o) => (
          <option key={`${o.value}-${o.label}`} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
};
