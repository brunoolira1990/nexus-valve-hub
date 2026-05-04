import { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { normalizeOperationalInput, shouldNormalizeOperationalByType } from '@/lib/textNormalize';

type Props = React.ComponentPropsWithoutRef<'input'> & {
  label: string;
  error?: string;
  /** Classes no wrapper (ex.: `md:col-span-2` em grids). */
  inputClassName?: string;
  operationalUpper?: boolean;
};

export const InputField = forwardRef<HTMLInputElement, Props>(
  ({ label, error, className, id, inputClassName, operationalUpper, onChange, ...props }, ref) => {
    const inputId = id ?? props.name;
    const normalize = Boolean(operationalUpper) && shouldNormalizeOperationalByType(props.type);
    return (
      <div className={cn('w-full', className)}>
        <label htmlFor={inputId} className="erp-label">
          {label}
        </label>
        <input
          ref={ref}
          id={inputId}
          className={cn('erp-input mt-1 w-full', inputClassName)}
          {...props}
          onChange={(e) => {
            if (normalize) e.target.value = normalizeOperationalInput(e.target.value);
            onChange?.(e);
          }}
        />
        {error ? <p className="text-sm text-destructive mt-1">{error}</p> : null}
      </div>
    );
  },
);
InputField.displayName = 'InputField';
