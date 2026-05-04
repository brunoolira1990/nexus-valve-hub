import { cn } from '@/lib/utils';

type Props = {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
};

/** Seção com título e borda (conteúdo em grid 1 / 2 colunas no desktop). */
export function CadastroSection({ title, description, children, className, contentClassName }: Props) {
  return (
    <section className={cn('rounded-lg border border-border bg-card/20', className)}>
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
      </div>
      <div className={cn('grid grid-cols-1 gap-4 p-4 md:grid-cols-2', contentClassName)}>{children}</div>
    </section>
  );
}
