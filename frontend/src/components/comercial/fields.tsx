import { formatMoneyBRL, formatPercentBR, formatQuantityBR } from '@/lib/numberFields';

type BaseInputProps = {
  value: number;
  onChange: (value: number) => void;
  className?: string;
  readOnly?: boolean;
  min?: number;
  step?: string;
};

export function QuantityInput({ value, onChange, className, readOnly, min = 0.001, step = 'any' }: BaseInputProps) {
  return (
    <input
      type="number"
      step={step}
      min={min}
      readOnly={readOnly}
      className={className || 'erp-input h-9 text-sm w-full mt-1'}
      value={value}
      onChange={(e) => onChange(Number(e.target.value) || 0)}
    />
  );
}

export function QuantityDisplay({ value, unidade, className }: { value: number; unidade?: string; className?: string }) {
  return <span className={className}>{formatQuantityBR(value, unidade)}</span>;
}

export function MoneyInput({ value, onChange, className, readOnly, min = 0, step = '0.01' }: BaseInputProps) {
  return (
    <input
      type="number"
      step={step}
      min={min}
      readOnly={readOnly}
      className={className || 'erp-input h-9 text-sm w-full mt-1'}
      value={value}
      onChange={(e) => onChange(Number(e.target.value) || 0)}
    />
  );
}

export function MoneyDisplay({ value, className }: { value: number; className?: string }) {
  return <span className={className}>{formatMoneyBRL(value)}</span>;
}

export function PercentInput({ value, onChange, className, readOnly, min = 0, step = '0.0001' }: BaseInputProps) {
  return (
    <input
      type="number"
      step={step}
      min={min}
      readOnly={readOnly}
      className={className || 'erp-input h-9 text-sm w-full mt-1'}
      value={value}
      onChange={(e) => onChange(Number(e.target.value) || 0)}
    />
  );
}

export function PercentDisplay({ value, className }: { value: number; className?: string }) {
  return <span className={className}>{formatPercentBR(value)}</span>;
}

export function DiscountInput(props: BaseInputProps) {
  return <MoneyInput {...props} />;
}

export function UnitSelect({
  value,
  options,
  onChange,
  disabled,
  className,
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <select
      className={className || 'erp-input h-9 text-sm w-full mt-1'}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value.toUpperCase())}
    >
      <option value="">Selecione</option>
      {options.map((u) => (
        <option key={u} value={u}>
          {u}
        </option>
      ))}
    </select>
  );
}

export function ReadonlyCalculatedField({ value, className }: { value: string; className?: string }) {
  return (
    <div className={className || 'erp-input h-9 text-sm w-full mt-1 flex items-center justify-end tabular-nums'}>
      {value}
    </div>
  );
}
