import { cn } from '@/lib/utils';

type Props = {
  title: string;
  children: React.ReactNode;
  className?: string;
};

/** Cabeçalho + cartão para formulários de cadastro (Cliente / Fornecedor / Transportadora). */
export function CadastroFormShell({ title, children, className }: Props) {
  return (
    <div className={cn('max-w-6xl', className)}>
      <h1 className="text-2xl font-bold text-foreground mb-4 border-b border-border pb-3">{title}</h1>
      <div className="erp-card p-4 md:p-6">{children}</div>
    </div>
  );
}
