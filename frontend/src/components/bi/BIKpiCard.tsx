import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  BadgeCent,
  Boxes,
  CalendarClock,
  ClipboardCheck,
  FileSearch,
  PackageSearch,
  Truck,
  type LucideIcon,
} from 'lucide-react';
import type { BIKpi } from '@/services/api/dashboard';
import { formatKpiValor } from './biFormat';

/**
 * Deriva um ícone de contexto a partir do link de destino do KPI.
 * O ícone comunica o domínio da métrica (vendas, fiscal, estoque etc.),
 * substituindo o visual "órfão" da seta genérica.
 */
export function kpiLinkIcon(link: string | null | undefined): LucideIcon {
  if (!link) return ArrowUpRight;
  if (link.startsWith('/pedidos-venda')) return ClipboardCheck;
  if (link.startsWith('/propostas')) return FileSearch;
  if (link.startsWith('/nfe-saida')) return CalendarClock;
  if (link.startsWith('/central-dfe') || link.startsWith('/nfe-entrada') || link.startsWith('/cte-entrada'))
    return FileSearch;
  if (link.startsWith('/produtos') || link.startsWith('/estoque')) return Boxes;
  if (link.startsWith('/pedidos-compra') || link.startsWith('/pc-')) return PackageSearch;
  if (link.startsWith('/expedicao') || link.startsWith('/romaneio')) return Truck;
  if (link.startsWith('/certificados') || link.startsWith('/certificado')) return ClipboardCheck;
  if (link.startsWith('/financeiro') || link.startsWith('/contas-a-') || link.startsWith('/titulos'))
    return BadgeCent;
  return ArrowUpRight;
}

export function BIKpiCard({ kpi }: { kpi: BIKpi }) {
  const value = formatKpiValor(kpi);
  const Icon = kpiLinkIcon(kpi.link ?? null);

  const inner = (
    <div className="flex min-w-0 items-start gap-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/70" aria-hidden />
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground line-clamp-2">{kpi.titulo}</p>
        <p className="mt-2 text-xl font-bold tabular-nums text-foreground break-words sm:text-2xl">{value}</p>
        {kpi.subtitulo ? <p className="mt-1 text-xs text-muted-foreground">{kpi.subtitulo}</p> : null}
      </div>
    </div>
  );

  const className =
    'erp-card group min-w-0 p-4 sm:p-5 min-h-[100px] transition-colors ' +
    (kpi.link ? ' hover:border-primary/40 hover:shadow-sm cursor-pointer' : '');

  if (kpi.link) {
    return (
      <Link to={kpi.link} className={className} title={`Abrir: ${kpi.titulo}`}>
        {inner}
      </Link>
    );
  }

  return <div className={className}>{inner}</div>;
}
