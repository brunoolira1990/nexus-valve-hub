import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface FormFieldProps {
  label?: ReactNode;
  htmlFor?: string;
  helperText?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function FormField({ label, htmlFor, helperText, error, required, children, className }: FormFieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label ? (
        <label htmlFor={htmlFor} className="nexus-label">
          {label}
          {required ? <span className="text-destructive ml-0.5">*</span> : null}
        </label>
      ) : null}
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      {!error && helperText ? <p className="nexus-caption">{helperText}</p> : null}
    </div>
  );
}

export function FormSection({ title, description, children }: { title?: string; description?: string; children: ReactNode }) {
  return (
    <section className="space-y-[var(--form-gap)]">
      {(title || description) && (
        <div>
          {title ? <h3 className="nexus-heading-md">{title}</h3> : null}
          {description ? <p className="nexus-caption mt-1">{description}</p> : null}
        </div>
      )}
      <div className="grid gap-[var(--form-gap)]">{children}</div>
    </section>
  );
}
