export function BIErrorState({
  message = 'Não foi possível carregar os indicadores.',
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="erp-card border-destructive/30 bg-destructive/5 p-6 text-center">
      <p className="text-sm text-destructive mb-4">{message}</p>
      {onRetry ? (
        <button type="button" className="erp-btn-outline erp-btn-sm" onClick={onRetry}>
          Tentar novamente
        </button>
      ) : null}
    </div>
  );
}
