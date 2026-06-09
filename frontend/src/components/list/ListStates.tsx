import { LoadingSpinner } from '@/components/nexus/LoadingSpinner';
import { EmptyState as NexusEmptyState } from '@/components/nexus/EmptyState';
import { ErrorState as NexusErrorState } from '@/components/nexus/ErrorState';

export function LoadingState({ message = 'Carregando…' }: { message?: string }) {
  return (
    <div className="flex items-center justify-center py-12">
      <LoadingSpinner label={message} />
    </div>
  );
}

export function EmptyState({
  message = 'Nenhum registro encontrado.',
  title,
  actionLabel,
  onAction,
}: {
  message?: string;
  title?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  if (actionLabel && onAction) {
    return <NexusEmptyState title={title ?? message} actionLabel={actionLabel} onAction={onAction} />;
  }
  return <NexusEmptyState title={title ?? message} message={title ? message : undefined} />;
}

export function ErrorState({
  message = 'Não foi possível carregar os dados. Tente novamente.',
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return <NexusErrorState message={message} onRetry={onRetry} />;
}
