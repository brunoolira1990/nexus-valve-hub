import { Link } from 'react-router-dom';
import type { BIRanking } from '@/services/api/dashboard';
import { formatRankingValor } from './biFormat';
import { BIEmptyState } from './BIEmptyState';

export function BIRankingList({ ranking, valorFormato }: { ranking: BIRanking; valorFormato?: string }) {
  if (!ranking.itens.length) {
    return (
      <div className="erp-card p-5">
        <h3 className="text-sm font-semibold mb-3">{ranking.titulo}</h3>
        <BIEmptyState message="Nenhum item no ranking." />
      </div>
    );
  }

  const max = Math.max(...ranking.itens.map((i) => Number(i.valor) || 0), 1);

  return (
    <div className="erp-card p-5 h-full">
      <h3 className="text-sm font-semibold text-foreground mb-4">{ranking.titulo}</h3>
      <ul className="space-y-3">
        {ranking.itens.map((item, idx) => {
          const pct = Math.min(100, ((Number(item.valor) || 0) / max) * 100);
          const row = (
            <>
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="font-medium text-foreground truncate">{item.label}</span>
                <span className="text-muted-foreground tabular-nums shrink-0">
                  {formatRankingValor(item.valor, valorFormato)}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary/80 transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </>
          );
          return (
            <li key={`${item.label}-${idx}`}>
              {item.link ? (
                <Link to={item.link} className="block hover:opacity-90">
                  {row}
                </Link>
              ) : (
                row
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
