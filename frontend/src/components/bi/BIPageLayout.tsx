import type { ReactNode } from 'react';
import { CalendarRange } from 'lucide-react';
import { useAppContexto } from '@/hooks/useAppContexto';
import { AmbienteBadge } from '@/components/header/AmbienteBadge';
import { EmpresaAtualBadge } from '@/components/header/EmpresaAtualBadge';
import { formatPeriodoLabel } from './dashboardBiConfig';
import type { DashboardPeriodo } from '@/services/api/dashboard';

type BIPageLayoutProps = {
  title: string;
  /**
   * `false` = o h1 existe só para leitores de tela (`sr-only`). Usado no Dashboard
   * e nos painéis BI, onde o breadcrumb do shell e a barra de abas já nomeiam a
   * página — o título repetido na tela era ruído.
   */
  titleVisible?: boolean;
  subtitle?: string;
  periodo?: DashboardPeriodo | null;
  periodLabel?: string;
  filters?: ReactNode;
  nav?: ReactNode;
  children: ReactNode;
};

export function BIPageLayout({
  title,
  titleVisible = true,
  subtitle,
  periodo,
  periodLabel,
  filters,
  nav,
  children,
}: BIPageLayoutProps) {
  const label = formatPeriodoLabel(periodo) || periodLabel;
  const { contexto } = useAppContexto();

  return (
    <div className="space-y-4">
      <header className="flex flex-col gap-4 border-b border-border/60 pb-6">
        {/* O shell compacto (Header h-9) deixou de mostrar empresa e ambiente; em
            BI eles passam a viver aqui, no topo do conteúdo. */}
        <div className="flex items-center gap-1.5">
          <EmpresaAtualBadge empresa={contexto.empresa} />
          <AmbienteBadge label={contexto.ambiente_label} />
        </div>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className={titleVisible ? 'nexus-heading-xl' : 'sr-only'}>{title}</h1>
            {subtitle ? <p className="mt-1.5 text-sm text-muted-foreground max-w-2xl">{subtitle}</p> : null}
            {label ? (
              <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <CalendarRange className="h-3.5 w-3.5" aria-hidden />
                {label}
              </p>
            ) : null}
          </div>
          {filters ? <div className="w-full shrink-0 xl:w-auto">{filters}</div> : null}
        </div>
        {nav}
      </header>
      {children}
    </div>
  );
}
