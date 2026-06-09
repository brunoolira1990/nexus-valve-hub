import type { ReactNode } from 'react';

type Props = {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
};

export function ComercialModalSection({ title, description, children, className }: Props) {
  return (
    <section className={`rounded-md border border-border bg-card/50 p-4 space-y-3 ${className ?? ''}`}>
      <div>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {description ? <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
