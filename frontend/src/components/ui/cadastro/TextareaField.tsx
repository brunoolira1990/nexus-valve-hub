import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

type Props = React.ComponentPropsWithoutRef<'textarea'> & {
  label: string;
  error?: string;
};

export const TextareaField = forwardRef<HTMLTextAreaElement, Props>(
  ({ label, error, className, id, ...props }, ref) => {
    const tid = id ?? props.name;
    return (
      <div className="w-full md:col-span-2">
        <label htmlFor={tid} className="erp-label">
          {label}
        </label>
        <textarea ref={ref} id={tid} className={cn('erp-input mt-1 min-h-[120px]', className)} {...props} />
        {error ? <p className="text-sm text-destructive mt-1">{error}</p> : null}
      </div>
    );
  },
);
TextareaField.displayName = 'TextareaField';
