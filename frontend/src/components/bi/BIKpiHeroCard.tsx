import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import type { BIKpi } from '@/services/api/dashboard';
import { formatKpiValor } from './biFormat';
import { cn } from '@/lib/utils';

type BIKpiHeroCardProps = {
  kpi: BIKpi;
  className?: string;
};

export function BIKpiHeroCard({ kpi, className = '' }: BIKpiHeroCardProps) {
  const value = formatKpiValor(kpi);
  const inner = (
    <div className={cn('min-w-0', kpi.link ? 'pr-10' : undefined)}>
      <p className="text-sm font-medium text-muted-foreground">{kpi.titulo}</p>
      <p className="mt-3 text-3xl font-bold tracking-tight tabular-nums text-foreground break-words sm:text-4xl lg:text-5xl">
        {value}
      </p>
      {kpi.subtitulo ? <p className="mt-2 text-sm text-muted-foreground">{kpi.subtitulo}</p> : null}
      {kpi.link ? (
        <ArrowUpRight
          className="absolute top-5 right-5 h-5 w-5 shrink-0 text-muted-foreground/50 group-hover:text-primary transition-colors pointer-events-none"
          aria-hidden
        />
      ) : null}
    </div>
  );

  const cls = cn(
    'erp-card relative group block min-w-0 overflow-visible p-6 sm:p-8 min-h-[140px]',
    'bg-gradient-to-br from-primary/5 via-background to-background border-primary/20',
    kpi.link && 'hover:border-primary/50 hover:shadow-md cursor-pointer transition-all',
    className,
  );

  if (kpi.link) {
    return (
      <Link to={kpi.link} className={cls}>
        {inner}
      </Link>
    );
  }
  return <div className={cls}>{inner}</div>;
}
