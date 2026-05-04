import { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { normalizeOperationalInput } from '@/lib/textNormalize';

type Props = React.ComponentPropsWithoutRef<'textarea'> & {
  label: string;
  error?: string;
  operationalUpper?: boolean;
};

export const TextareaField = forwardRef<HTMLTextAreaElement, Props>(
  ({ label, error, className, id, operationalUpper, onChange, ...props }, ref) => {
    const tid = id ?? props.name;
    return (
      <div className="w-full md:col-span-2">
        <label htmlFor={tid} className="erp-label">
          {label}
        </label>
        <textarea
          ref={ref}
          id={tid}
          className={cn('erp-input mt-1 min-h-[120px]', className)}
          {...props}
          onChange={(e) => {
            if (operationalUpper) e.target.value = normalizeOperationalInput(e.target.value);
            onChange?.(e);
          }}
        />
        {error ? <p className="text-sm text-destructive mt-1">{error}</p> : null}
      </div>
    );
  },
);
TextareaField.displayName = 'TextareaField';
