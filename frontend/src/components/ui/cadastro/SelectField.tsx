import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

export type SelectOption = { value: string; label: string };

type Props = React.ComponentPropsWithoutRef<'select'> & {
  label: string;
  error?: string;
  options: readonly SelectOption[];
  placeholder?: string;
};

export const SelectField = forwardRef<HTMLSelectElement, Props>(
  ({ label, error, className, id, options, placeholder, ...props }, ref) => {
    const selectId = id ?? props.name;
    return (
      <div className="w-full">
        <label htmlFor={selectId} className="erp-label">
          {label}
        </label>
        <select ref={ref} id={selectId} className={cn('erp-select mt-1', className)} {...props}>
          {placeholder != null ? <option value="">{placeholder}</option> : null}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {error ? <p className="text-sm text-destructive mt-1">{error}</p> : null}
      </div>
    );
  },
);
SelectField.displayName = 'SelectField';
