import { Link } from 'react-router-dom';
import type { BIAlert } from '@/services/api/dashboard';
import { BIEmptyState } from './BIEmptyState';

function severityClass(sev: BIAlert['severidade']) {
  if (sev === 'critico') return 'border-destructive/40 bg-destructive/10 text-destructive';
  if (sev === 'aviso') return 'border-amber-500/40 bg-amber-500/10 text-amber-950 dark:text-amber-100';
  return 'border-border bg-muted/40 text-muted-foreground';
}

export function BIAlertList({
  alertas,
  title = 'Alertas',
  compact = false,
}: {
  alertas: BIAlert[];
  title?: string;
  compact?: boolean;
}) {
  if (alertas.length === 0) {
    return (
      <div className="erp-card p-4">
        <h3 className="text-sm font-semibold text-foreground mb-2">{title}</h3>
        <BIEmptyState message="Nenhum alerta no momento." />
      </div>
    );
  }

  return (
    <div className="erp-card p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-foreground mb-3">{title}</h3>
      <ul className={compact ? 'space-y-1.5' : 'space-y-2'}>
        {alertas.map((a, i) => (
          <li
            key={`${a.modulo}-${a.titulo}-${i}`}
            className={`rounded-md border text-sm ${compact ? 'px-2.5 py-2' : 'px-3 py-2.5'} ${severityClass(a.severidade)}`}
          >
            {!compact ? <p className="font-medium text-xs">{a.titulo}</p> : null}
            <Link to={a.link} className={`hover:underline block ${compact ? 'text-xs' : 'mt-0.5 opacity-90'}`}>
              {compact ? `${a.titulo}: ${a.mensagem}` : a.mensagem}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
