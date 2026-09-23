import type { ReactNode } from 'react';

type WorkspaceSectionProps = {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

export function WorkspaceSection({ title, description, actions, children, className }: WorkspaceSectionProps) {
  return (
    <section className={`rounded-lg border border-border bg-card/40 p-4 sm:p-5 ${className ?? ''}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            {title && (
              <h3 className="text-sm font-semibold text-foreground tracking-tight">{title}</h3>
            )}
            {description && (
              <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{description}</p>
            )}
          </div>
          {actions && <div className="shrink-0 flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="space-y-4">{children}</div>
    </section>
  );
}
