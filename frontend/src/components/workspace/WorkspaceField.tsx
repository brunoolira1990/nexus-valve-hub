import type { ReactNode } from 'react';

type WorkspaceFieldProps = {
  label: string;
  required?: boolean;
  help?: string;
  error?: string;
  children: ReactNode;
  className?: string;
};

export function WorkspaceField({ label, required, help, error, children, className }: WorkspaceFieldProps) {
  return (
    <div className={`flex flex-col gap-1 ${className ?? ''}`}>
      <label className="erp-label">
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </label>
      {children}
      {help && !error && <p className="text-[11px] text-muted-foreground leading-snug">{help}</p>}
      {error && <p className="text-[11px] text-destructive leading-snug">{error}</p>}
    </div>
  );
}
