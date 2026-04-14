import { cn } from '@/lib/utils';

type Props = {
  title: string;
  children: React.ReactNode;
  className?: string;
};

/** Seção com título e borda (conteúdo em grid 1 / 2 colunas no desktop). */
export function CadastroSection({ title, children, className }: Props) {
  return (
    <section className={cn('rounded-lg border border-border bg-card/20', className)}>
      <div className="px-4 py-3 border-b border-border text-sm font-semibold text-foreground">{title}</div>
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
    </section>
  );
}
