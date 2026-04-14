import { cn } from '@/lib/utils';

type Variant = 'primary' | 'outline' | 'secondary';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
};

export function CadastroButton({ variant = 'primary', className, type = 'button', ...props }: Props) {
  const base =
    variant === 'primary'
      ? 'erp-btn-primary'
      : variant === 'outline'
        ? 'erp-btn-outline'
        : 'erp-btn-ghost border border-border';
  return <button type={type} className={cn(base, className)} {...props} />;
}
