import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import type { DashboardModuloHome } from '@/services/api/dashboard';
import { formatKpiValor } from './biFormat';
import { MODULO_HERO_KPI } from './dashboardBiConfig';
function alertClass(sev: string) {
  if (sev === 'critico') return 'border-destructive/40 bg-destructive/10 text-destructive';
  if (sev === 'aviso') return 'border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100';
  return 'border-border bg-muted/40 text-muted-foreground';
}

export function BIModuleCard({ modulo }: { modulo: DashboardModuloHome }) {
  const alerta = modulo.alerta_principal;
  const heroId = modulo.hero_kpi_id ?? MODULO_HERO_KPI[modulo.modulo as keyof typeof MODULO_HERO_KPI];
  const heroKpi = heroId ? modulo.kpis.find((k) => k.id === heroId) : null;
  const secondaryKpis = modulo.kpis.filter((k) => k.id !== heroId);

  return (
    <div className="erp-card p-6 flex flex-col min-h-[280px] hover:border-primary/30 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-5">
        <h2 className="text-lg font-semibold text-foreground">{modulo.titulo}</h2>
        <Link
          to={modulo.link_bi}
          className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/20 transition-colors shrink-0"
        >
          Ver painel
          <ChevronRight className="h-4 w-4" />
        </Link>
      </div>

      {heroKpi ? (
        <div className="mb-5 rounded-xl border border-primary/15 bg-primary/5 px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{heroKpi.titulo}</p>
          <p className="mt-2 text-3xl font-bold tabular-nums tracking-tight">{formatKpiValor(heroKpi)}</p>
        </div>
      ) : null}

      {secondaryKpis.length > 0 ? (
        <ul className="space-y-2 text-sm flex-1">
          {secondaryKpis.slice(0, 4).map((kpi) => (
            <li key={kpi.id} className="flex justify-between gap-3 border-b border-border/40 pb-2 last:border-0">
              <span className="text-muted-foreground">{kpi.titulo}</span>
              <span className="font-semibold tabular-nums text-foreground">{formatKpiValor(kpi)}</span>
            </li>
          ))}
        </ul>
      ) : !heroKpi ? (
        <p className="text-sm text-muted-foreground flex-1">Sem indicadores no período.</p>
      ) : null}

      {alerta ? (
        <div className={`mt-4 rounded-md border px-3 py-2 text-xs ${alertClass(alerta.severidade)}`}>
          <span className="font-medium">Alerta: </span>
          <Link to={alerta.link} className="hover:underline">
            {alerta.mensagem}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
