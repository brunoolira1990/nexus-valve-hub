import { formatMoneyBRL } from '@/lib/money';
import type { RelatorioMetrica } from '@/services/api/financeiro';

export type RelatorioCardItem = {
  titulo: string;
  metrica?: RelatorioMetrica | number;
  valor?: string;
  subtitulo?: string;
  tone?: 'receber' | 'pagar' | 'neutro' | 'alerta';
};

function toneClass(tone?: string) {
  if (tone === 'receber') return 'border-emerald-200 bg-emerald-50/60 dark:bg-emerald-950/20';
  if (tone === 'pagar') return 'border-rose-200 bg-rose-50/60 dark:bg-rose-950/20';
  if (tone === 'alerta') return 'border-amber-200 bg-amber-50/60 dark:bg-amber-950/20';
  return 'border-border bg-card';
}

export function RelatorioMetricCards({ cards }: { cards: RelatorioCardItem[] }) {
  if (!cards.length) return null;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3 mb-6">
      {cards.map((c) => {
        const valor =
          c.valor ??
          (typeof c.metrica === 'number'
            ? String(c.metrica)
            : c.metrica
              ? formatMoneyBRL(c.metrica.valor)
              : '—');
        const qtd = typeof c.metrica === 'object' && c.metrica ? c.metrica.quantidade : undefined;
        return (
          <div key={c.titulo} className={`erp-card p-4 border ${toneClass(c.tone)}`}>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">{c.titulo}</p>
            <p className="text-xl font-bold tabular-nums mt-1">{valor}</p>
            {qtd !== undefined && qtd > 0 ? (
              <p className="text-xs text-muted-foreground mt-1">{qtd} título(s)</p>
            ) : null}
            {c.subtitulo ? <p className="text-xs text-muted-foreground mt-1">{c.subtitulo}</p> : null}
          </div>
        );
      })}
    </div>
  );
}
