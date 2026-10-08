import { Construction } from 'lucide-react';

type BIPreparationStateProps = {
  title?: string;
  message?: string;
  compact?: boolean;
};

export function BIPreparationState({
  title = 'Financeiro em preparação',
  message = 'Contas a receber serão geradas pela NF-e de saída autorizada em produção. Contas a pagar serão geradas pela NF-e de entrada do fornecedor.',
  compact = false,
}: BIPreparationStateProps) {
  if (compact) {
    return (
      <div className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 px-4 py-3">
        <p className="text-sm font-semibold text-amber-950 dark:text-amber-100">{title}</p>
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{message}</p>
      </div>
    );
  }

  return (
    <div className="erp-card border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-background p-8 text-center">
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-200">
        <Construction className="h-7 w-7" />
      </div>
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <p className="mt-3 text-sm text-muted-foreground max-w-xl mx-auto leading-relaxed">{message}</p>
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-2xl mx-auto opacity-50 pointer-events-none">
        {['A receber', 'A pagar', 'Fluxo de caixa', 'Recebimentos'].map((label) => (
          <div key={label} className="rounded-lg border border-dashed border-border px-3 py-4">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">—</p>
          </div>
        ))}
      </div>
    </div>
  );
}
