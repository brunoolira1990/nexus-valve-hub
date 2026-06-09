import type { ReactNode } from 'react';
import { formatPeriodoLabel } from './dashboardBiConfig';
import type { DashboardPeriodo } from '@/services/api/dashboard';

type BIPageLayoutProps = {
  title: string;
  subtitle?: string;
  periodo?: DashboardPeriodo | null;
  periodLabel?: string;
  filters?: ReactNode;
  nav?: ReactNode;
  children: ReactNode;
};

export function BIPageLayout({
  title,
  subtitle,
  periodo,
  periodLabel,
  filters,
  nav,
  children,
}: BIPageLayoutProps) {
  const label = formatPeriodoLabel(periodo) || periodLabel;

  return (
    <div className="space-y-[var(--section-gap)]">
      <header className="flex flex-col gap-4 border-b border-border/60 pb-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="nexus-heading-xl">{title}</h1>
            {subtitle ? <p className="mt-1.5 text-sm text-muted-foreground max-w-2xl">{subtitle}</p> : null}
            {label ? (
              <p className="mt-3 inline-flex items-center rounded-md bg-muted px-3 py-1 text-sm font-medium text-foreground">
                Período: {label}
              </p>
            ) : null}
          </div>
          {filters ? <div className="shrink-0 w-full xl:w-auto xl:min-w-[320px]">{filters}</div> : null}
        </div>
        {nav}
      </header>
      {children}
    </div>
  );
}
