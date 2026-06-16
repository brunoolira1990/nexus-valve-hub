import { useEffect, useState } from 'react';
import {
  formatMoneyBRL,
  formatQuantityBR,
  parseMoneyInputToDecimal,
  parseQuantityInputToDecimal,
} from '@/lib/numberFields';

type BaseInputProps = {
  value: number;
  onChange: (value: number) => void;
  className?: string;
  readOnly?: boolean;
  min?: number;
  step?: string;
};

type EditableDecimalProps = BaseInputProps & {
  inputMode?: 'decimal' | 'numeric';
  formatDisplay: (value: number) => string;
  parseInput: (raw: string) => number;
  allowEmpty?: boolean;
};

function formatEditableDecimal(value: number): string {
  if (!Number.isFinite(value) || value === 0) return '';
  const isInt = Math.abs(value - Math.round(value)) < 1e-9;
  if (isInt) return String(Math.round(value));
  return value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

function EditableDecimalInput({
  value,
  onChange,
  className,
  readOnly,
  min = 0,
  inputMode = 'decimal',
  formatDisplay,
  parseInput,
  allowEmpty = true,
}: EditableDecimalProps) {
  const [text, setText] = useState('');
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) {
      if (allowEmpty && (value === 0 || !Number.isFinite(value))) {
        setText('');
      } else {
        setText(formatDisplay(value));
      }
    }
  }, [value, focused, formatDisplay, allowEmpty]);

  return (
    <input
      type="text"
      inputMode={inputMode}
      readOnly={readOnly}
      className={className || 'erp-input h-9 text-sm w-full mt-1'}
      value={text}
      onFocus={(e) => {
        setFocused(true);
        e.target.select();
      }}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        setFocused(false);
        const raw = text.trim();
        if (!raw) {
          onChange(allowEmpty ? 0 : Math.max(min, 0));
          return;
        }
        const parsed = parseInput(raw);
        const safe = Number.isFinite(parsed) ? Math.max(min, parsed) : 0;
        onChange(safe);
      }}
    />
  );
}

export function QuantityInput({ value, onChange, className, readOnly, min = 0.001 }: BaseInputProps) {
  return (
    <EditableDecimalInput
      value={value}
      onChange={onChange}
      className={className}
      readOnly={readOnly}
      min={min}
      inputMode="decimal"
      formatDisplay={(n) => (n ? formatEditableDecimal(n) : '')}
      parseInput={parseQuantityInputToDecimal}
    />
  );
}

export function QuantityDisplay({ value, unidade, className }: { value: number; unidade?: string; className?: string }) {
  return <span className={className}>{formatQuantityBR(value, unidade)}</span>;
}

export function MoneyInput({ value, onChange, className, readOnly, min = 0 }: BaseInputProps) {
  return (
    <EditableDecimalInput
      value={value}
      onChange={onChange}
      className={className}
      readOnly={readOnly}
      min={min}
      inputMode="decimal"
      formatDisplay={formatEditableDecimal}
      parseInput={parseMoneyInputToDecimal}
    />
  );
}

export function MoneyDisplay({ value, className }: { value: number; className?: string }) {
  return <span className={className}>{formatMoneyBRL(value)}</span>;
}

export function PercentInput({ value, onChange, className, readOnly, min = 0 }: BaseInputProps) {
  return (
    <EditableDecimalInput
      value={value}
      onChange={onChange}
      className={className}
      readOnly={readOnly}
      min={min}
      inputMode="decimal"
      formatDisplay={formatEditableDecimal}
      parseInput={parseMoneyInputToDecimal}
    />
  );
}

export function PercentDisplay({ value, className }: { value: number; className?: string }) {
  const n = Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  return <span className={className}>{`${safe.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}%`}</span>;
}

export function DiscountInput(props: BaseInputProps) {
  return <MoneyInput {...props} />;
}

export function IntegerInput({
  value,
  onChange,
  className,
  readOnly,
  min = 1,
}: {
  value: number;
  onChange: (value: number) => void;
  className?: string;
  readOnly?: boolean;
  min?: number;
}) {
  return (
    <EditableDecimalInput
      value={value}
      onChange={onChange}
      className={className}
      readOnly={readOnly}
      min={min}
      inputMode="numeric"
      formatDisplay={(n) => (n > 0 ? String(Math.round(n)) : '')}
      parseInput={(raw) => Math.round(parseQuantityInputToDecimal(raw))}
      allowEmpty
    />
  );
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
