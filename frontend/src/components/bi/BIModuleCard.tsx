import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import type { DashboardModuloHome } from '@/services/api/dashboard';
import { formatKpiValor } from './biFormat';
import {
  MODULO_HERO_KPI,
  MODULO_ICONE,
  MODULO_ICONE_COR,
  kpiTom,
  type KpiTom,
} from './dashboardBiConfig';

function alertClass(sev: string) {
  if (sev === 'critico') return 'border-destructive/40 bg-destructive/10 text-destructive';
  if (sev === 'aviso') return 'border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100';
  return 'border-border bg-muted/40 text-muted-foreground';
}

const NUMERO_CLS: Record<KpiTom, string> = {
  neutro: 'text-foreground',
  positivo: 'text-emerald-600',
  alerta: 'text-amber-600',
  erro: 'text-red-600',
};

const BADGE_CLS: Record<KpiTom, string> = {
  neutro: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  positivo: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  alerta: 'bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  erro: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300',
};

export function BIModuleCard({ modulo }: { modulo: DashboardModuloHome }) {
  const alerta = modulo.alerta_principal;
  const heroId = modulo.hero_kpi_id ?? MODULO_HERO_KPI[modulo.modulo as keyof typeof MODULO_HERO_KPI];
  const heroKpi = heroId ? modulo.kpis.find((k) => k.id === heroId) : null;
  const secondaryKpis = modulo.kpis.filter((k) => k.id !== heroId);
  const Icone = MODULO_ICONE[modulo.modulo as keyof typeof MODULO_ICONE];
  const corIcone = MODULO_ICONE_COR[modulo.modulo as keyof typeof MODULO_ICONE_COR];

  return (
    <div className="erp-card p-4 flex flex-col min-h-[260px] hover:border-nexus-blue/30 transition-colors">
      <div className="mb-3 flex items-center gap-1.5">
        {Icone ? (
          <Icone className={`h-4 w-4 shrink-0 ${corIcone ?? ''}`} aria-hidden />
        ) : null}
        <h2 className="text-sm font-semibold text-foreground">{modulo.titulo}</h2>
      </div>

      {heroKpi ? (
        <div className="mb-3 rounded-lg border border-nexus-blue/15 bg-nexus-blue/5 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{heroKpi.titulo}</p>
          <p className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${NUMERO_CLS[kpiTom(heroKpi)]}`}>
            {formatKpiValor(heroKpi)}
          </p>
        </div>
      ) : null}

      {secondaryKpis.length > 0 ? (
        <ul className="space-y-1.5 text-sm flex-1">
          {secondaryKpis.slice(0, 4).map((kpi) => (
            <li
              key={kpi.id}
              className="flex items-baseline justify-between gap-3 border-b border-border/40 pb-1.5 last:border-0"
            >
              <span className="min-w-0 truncate text-muted-foreground">{kpi.titulo}</span>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${BADGE_CLS[kpiTom(kpi)]}`}
              >
                {formatKpiValor(kpi)}
              </span>
            </li>
          ))}
        </ul>
      ) : !heroKpi ? (
        <p className="text-sm text-muted-foreground flex-1">Sem indicadores no período.</p>
      ) : null}

      {alerta ? (
        <div className={`mt-3 rounded-md border px-3 py-1.5 text-xs ${alertClass(alerta.severidade)}`}>
          <span className="font-medium">Alerta: </span>
          <Link to={alerta.link} className="hover:underline">
            {alerta.mensagem}
          </Link>
        </div>
      ) : null}

      <Link
        to={modulo.link_bi}
        className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-nexus-blue hover:underline"
      >
        Ver painel
        <ArrowRight className="h-3.5 w-3.5" aria-hidden />
      </Link>
    </div>
  );
}
