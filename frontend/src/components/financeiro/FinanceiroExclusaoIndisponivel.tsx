type Props = {
  motivo?: string | null;
  className?: string;
};

export function FinanceiroExclusaoIndisponivel({ motivo, className = '' }: Props) {
  if (!motivo?.trim()) return null;

  return (
    <p className={`text-xs text-muted-foreground rounded-md border border-border bg-muted/30 px-3 py-2 ${className}`}>
      Exclusão indisponível: {motivo.trim()}
    </p>
  );
}
