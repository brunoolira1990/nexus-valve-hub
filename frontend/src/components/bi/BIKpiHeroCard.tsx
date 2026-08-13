import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import type { BIKpi } from '@/services/api/dashboard';
import { formatKpiValor } from './biFormat';
import { kpiLinkIcon } from './BIKpiCard';

type BIKpiHeroCardProps = {
  kpi: BIKpi;
  className?: string;
};

/**
 * Card de destaque (hero) do painel BI.
 * Em vez de uma seta solta no canto, o card usa um ícone grande de domínio
 * (vendas, fiscal, financeiro…) que comunica visualmente a que área a métrica pertence.
 */
export function BIKpiHeroCard({ kpi, className = '' }: BIKpiHeroCardProps) {
  const value = formatKpiValor(kpi);
  const Icon = kpiLinkIcon(kpi.link ?? null);

  const inner = (
    <div className="flex min-w-0 items-center gap-5 sm:gap-6">
      <div
        className={cn(
          'flex h-14 w-14 shrink-0 items-center justify-center rounded-xl',
          'bg-primary/10 text-primary',
          'sm:h-16 sm:w-16',
        )}
        aria-hidden
      >
        <Icon className="h-7 w-7 sm:h-8 sm:w-8" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-muted-foreground">{kpi.titulo}</p>
        <p className="mt-3 text-3xl font-bold tracking-tight tabular-nums text-foreground break-words sm:text-4xl lg:text-5xl">
          {value}
        </p>
        {kpi.subtitulo ? <p className="mt-2 text-sm text-muted-foreground">{kpi.subtitulo}</p> : null}
      </div>
    </div>
  );

  const cls = cn(
    'erp-card relative group block min-w-0 p-6 sm:p-8 min-h-[140px]',
    'bg-gradient-to-br from-primary/5 via-background to-background border-primary/20',
    kpi.link && 'hover:border-primary/50 hover:shadow-md cursor-pointer transition-all',
    className,
  );

  if (kpi.link) {
    return (
      <Link to={kpi.link} className={cls} title={`Abrir: ${kpi.titulo}`}>
        {inner}
      </Link>
    );
  }
  return <div className={cls}>{inner}</div>;
}
