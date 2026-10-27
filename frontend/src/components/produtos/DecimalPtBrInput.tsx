import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { formatDecimalPtBr, parseDecimalPtBr } from '@/lib/decimalPtBr';

type Props = {
  value: number | null | undefined;
  /** null quando o campo é esvaziado; quem usa decide o vazio de cada campo. */
  onChange: (value: number | null) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
};

/**
 * Input decimal que aceita vírgula pt-BR. O texto digitado vive em buffer local até o blur:
 * sem isso, «12,» não é um número parseável e o campo voltava vazio, engolindo o que o
 * operador ainda ia digitar.
 */
export function DecimalPtBrInput({ value, onChange, disabled, placeholder, className }: Props) {
  const [bruto, setBruto] = useState<string | null>(null);
  const canonico = formatDecimalPtBr(value);

  return (
    <Input
      type="text"
      inputMode="decimal"
      className={className}
      placeholder={placeholder}
      disabled={disabled}
      value={bruto ?? canonico}
      onChange={(e) => {
        const raw = e.target.value;
        setBruto(raw);
        if (raw.trim() === '') {
          onChange(null);
          return;
        }
        const n = parseDecimalPtBr(raw);
        if (n !== null) onChange(n);
      }}
      onBlur={() => setBruto(null)}
    />
  );
}
