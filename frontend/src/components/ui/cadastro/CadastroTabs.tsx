import { cn } from '@/lib/utils';

export type CadastroTabItem = {
  id: string;
  label: string;
};

type Props = {
  tabs: readonly CadastroTabItem[];
  value: string;
  onValueChange: (id: string) => void;
  children: React.ReactNode;
};

/** Abas horizontais com borda inferior no item ativo. */
export function CadastroTabs({ tabs, value, onValueChange, children }: Props) {
  return (
    <div className="w-full">
      <div className="flex flex-wrap gap-1 border-b border-border mb-4">
        {tabs.map((t) => {
          const active = value === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onValueChange(t.id)}
              className={cn(
                'px-3 py-2 text-sm font-medium rounded-t-md border-b-2 -mb-px transition-colors',
                active
                  ? 'border-primary text-foreground bg-muted/40'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/20',
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      {children}
    </div>
  );
}
