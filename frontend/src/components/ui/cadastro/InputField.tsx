import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

type Props = React.ComponentPropsWithoutRef<'input'> & {
  label: string;
  error?: string;
  /** Classes no wrapper (ex.: `md:col-span-2` em grids). */
  inputClassName?: string;
};

export const InputField = forwardRef<HTMLInputElement, Props>(
  ({ label, error, className, id, inputClassName, ...props }, ref) => {
    const inputId = id ?? props.name;
    return (
      <div className={cn('w-full', className)}>
        <label htmlFor={inputId} className="erp-label">
          {label}
        </label>
        <input ref={ref} id={inputId} className={cn('erp-input mt-1 w-full', inputClassName)} {...props} />
        {error ? <p className="text-sm text-destructive mt-1">{error}</p> : null}
      </div>
    );
  },
);
InputField.displayName = 'InputField';
