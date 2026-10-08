import type { ReactNode } from 'react';
import { CalendarRange } from 'lucide-react';
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
              <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <CalendarRange className="h-3.5 w-3.5" aria-hidden />
                {label}
              </p>
            ) : null}
          </div>
          {filters ? (
            <div className="shrink-0 w-full xl:w-auto xl:min-w-[320px] lg:mb-0">
              {filters}
            </div>
          ) : null}
        </div>
        {nav}
      </header>
      {children}
    </div>
  );
}
