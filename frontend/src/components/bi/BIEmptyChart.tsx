type BIEmptyChartProps = {
  title?: string;
  message?: string;
};

export function BIEmptyChart({
  title = 'Sem dados no período',
  message = 'Não há registros para os filtros selecionados.',
}: BIEmptyChartProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/80 bg-muted/20 px-4 py-8 text-center min-h-[120px] max-h-[160px]">
      <p className="text-sm font-medium text-muted-foreground">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground/80 max-w-xs">{message}</p>
    </div>
  );
}
