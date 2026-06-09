import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import type { BIKpi } from '@/services/api/dashboard';
import { formatKpiValor } from './biFormat';

export function BIKpiCard({ kpi }: { kpi: BIKpi }) {
  const value = formatKpiValor(kpi);
  const inner = (
    <div className={kpi.link ? 'min-w-0 pr-8' : 'min-w-0'}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground line-clamp-2">{kpi.titulo}</p>
      <p className="mt-2 text-xl font-bold tabular-nums text-foreground break-words sm:text-2xl">{value}</p>
      {kpi.subtitulo ? <p className="mt-1 text-xs text-muted-foreground">{kpi.subtitulo}</p> : null}
      {kpi.link ? (
        <ArrowUpRight className="absolute top-4 right-4 h-4 w-4 text-muted-foreground/60 group-hover:text-primary transition-colors" />
      ) : null}
    </div>
  );

  const className =
    'erp-card relative group min-w-0 overflow-visible p-4 sm:p-5 min-h-[100px] transition-colors ' +
    (kpi.link ? ' hover:border-primary/40 hover:shadow-sm cursor-pointer' : '');

  if (kpi.link) {
    return (
      <Link to={kpi.link} className={className}>
        {inner}
      </Link>
    );
  }

  return <div className={className}>{inner}</div>;
}
